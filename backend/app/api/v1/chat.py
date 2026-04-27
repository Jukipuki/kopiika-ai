"""Chat streaming API — Story 10.5.

# SCOPE (Story 10.5):
#   (1) Three FastAPI routes:
#         POST   /api/v1/chat/sessions                       — create session
#         POST   /api/v1/chat/sessions/{id}/turns/stream     — SSE streaming turn
#         DELETE /api/v1/chat/sessions/{id}                  — terminate session
#   (2) SSE token-by-token streaming via ChatSessionHandler.send_turn_stream
#       with Bedrock Guardrails attached at invoke time.
#   (3) CHAT_REFUSED envelope translation from every typed handler exception
#       + rate-limit placeholder (Story 10.11 plugs in).
#   (4) chat.stream.* structured-log observability (Story 10.9 metricifies).
#
# SSE contract invariants (AC #14):
#   (1) chat-open is always the first frame.
#   (2) Exactly one of chat-complete / chat-refused is always the LAST frame.
#   (3) chat-refused translation is a typed-exception switch — no string matching.
#   (4) Heartbeats are `: heartbeat\n\n` comment frames every 15s.
#   (5) All payload keys are camelCase (via repo's to_camel alias convention).
#   (6) correlation_id is ALWAYS populated on every SSE frame metadata + logs.
#
# Non-goals (sibling/downstream, do NOT add here — they ship in later stories):
#   - Rate-limit enforcement (60/hr, 10 concurrent)       → Story 10.11
#   - Citation payload in SSE frames                      → Story 10.6b (DONE — see docs/chat-sse-contract.md §chat-citations).
#   - Contextual-grounding threshold tuning               → Story 10.6a (DONE — see docs/decisions/chat-grounding-threshold-2026-04.md)
#   - Chat UI / Vercel AI SDK wiring                      → Story 10.7
#   - Chat history listing / bulk-delete endpoints        → Story 10.10
#   - Safety-metric publishing (CloudWatch EMF, alarms)   → Story 10.9
#   - New tools / prompt changes / canary updates         → 10.4b/c (unchanged)
#   - AgentCore runtime swap (Phase B)                    → story 10.4a-runtime
#   - Red-team corpus authoring                           → Story 10.8a
"""

from __future__ import annotations

import asyncio
import base64
import binascii
import json
import logging
import time
import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel
from sqlalchemy import delete as sa_delete
from sqlalchemy import func
from sqlalchemy import select as sa_select
from sqlalchemy import update as sa_update
from sqlmodel.ext.asyncio.session import AsyncSession as SQLModelAsyncSession

from app.agents.chat.canary_detector import ChatPromptLeakDetectedError
from app.agents.chat.citations import citation_to_json_dict
from app.agents.chat.chat_backend import (
    ChatConfigurationError,
    ChatGuardrailInterventionError,
    ChatProviderNotSupportedError,
    ChatSessionCreationError,
    ChatSessionTerminationFailed,
    ChatTransientError,
)
from app.agents.chat.input_validator import ChatInputBlockedError
from app.agents.chat.rate_limit_errors import ChatRateLimitedError
from app.agents.chat.session_handler import (
    ChatSessionHandle,
    ChatSessionHandler,
    _hash_user_id,
    get_chat_session_handler,
)
from app.agents.chat.stream_events import (
    ChatCitationsAttached,
    ChatStreamCompleted,
    ChatStreamStarted,
    ChatTokenDelta,
    ChatToolHopCompleted,
    ChatToolHopStarted,
)
from app.agents.chat.tools.tool_errors import (
    ChatToolAuthorizationError,
    ChatToolLoopExceededError,
    ChatToolNotAllowedError,
)
from app.api.deps import get_current_user, get_current_user_id, get_db
from app.api.v1._sse import SSE_RESPONSE_HEADERS, get_user_id_from_token
from app.core.config import settings
from app.models.chat_message import ChatMessage
from app.models.chat_session import ChatSession
from app.models.user import User
from app.services.chat_session_service import (
    ChatConsentRequiredError,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])


CHAT_SSE_HEARTBEAT_INTERVAL = 15
"""Heartbeat interval in seconds — mirrors ``jobs.py:22`` SSE_HEARTBEAT_INTERVAL.
ALB idle timeout is 60s; 15s heartbeats comfortably clear that. Not
env-overridable — operational invariant."""

# Input length cap enforced at the FastAPI layer BEFORE the handler's input
# validator. A 422 here is a client-shape failure (distinct from a
# CHAT_REFUSED.guardrail_blocked which the validator raises for jailbreaks /
# disallowed characters). Sourced from the SAME settings var the validator
# uses so there is no drift between the two layers.
CHAT_MAX_INPUT_CHARS = settings.CHAT_INPUT_MAX_CHARS


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _camel_model() -> ConfigDict:
    return ConfigDict(alias_generator=to_camel, populate_by_name=True)


# ----------------------------------------------------------------------
# Request / response schemas
# ----------------------------------------------------------------------


class CreateSessionResponse(BaseModel):
    model_config = _camel_model()
    session_id: str
    created_at: str
    consent_version_at_creation: str


class StreamTurnRequest(BaseModel):
    model_config = _camel_model()
    message: str = Field(..., min_length=1)


# ----------------------------------------------------------------------
# CHAT_REFUSED envelope translator (AC #4)
# ----------------------------------------------------------------------


def _refused_payload(
    *,
    reason: str,
    correlation_id: str,
    retry_after_seconds: int | None = None,
) -> dict[str, Any]:
    return {
        "error": "CHAT_REFUSED",
        "reason": reason,
        "correlationId": correlation_id,
        "retryAfterSeconds": retry_after_seconds,
    }


def _translate_exception(
    exc: Exception, *, correlation_id: str
) -> tuple[str, dict[str, Any], str, int]:
    """Typed-exception → ``(reason, payload, exception_class, log_level)`` switch.

    ``log_level`` is the ``logging`` numeric level at which
    ``chat.stream.refused`` should fire. WARN for capacity signals
    (``transient_error``), INFO for user-facing blocks of hostile input.
    """
    exc_class = type(exc).__name__
    if isinstance(exc, ChatInputBlockedError):
        return (
            "guardrail_blocked",
            _refused_payload(reason="guardrail_blocked", correlation_id=correlation_id),
            exc_class,
            logging.INFO,
        )
    if isinstance(exc, ChatPromptLeakDetectedError):
        return (
            "prompt_leak_detected",
            _refused_payload(
                reason="prompt_leak_detected", correlation_id=correlation_id
            ),
            exc_class,
            logging.INFO,
        )
    if isinstance(
        exc,
        (
            ChatToolLoopExceededError,
            ChatToolNotAllowedError,
            ChatToolAuthorizationError,
        ),
    ):
        return (
            "tool_blocked",
            _refused_payload(reason="tool_blocked", correlation_id=correlation_id),
            exc_class,
            logging.INFO,
        )
    if isinstance(exc, ChatGuardrailInterventionError):
        reason = (
            "ungrounded" if exc.intervention_kind == "grounding" else "guardrail_blocked"
        )
        return (
            reason,
            _refused_payload(reason=reason, correlation_id=correlation_id),
            exc_class,
            logging.INFO,
        )
    if isinstance(exc, ChatRateLimitedError):
        return (
            "rate_limited",
            _refused_payload(
                reason="rate_limited",
                correlation_id=correlation_id,
                retry_after_seconds=exc.retry_after_seconds,
            ),
            exc_class,
            logging.INFO,
        )
    if isinstance(exc, ChatConsentRequiredError):
        # Per AC #4 — should never fire at turn time. Log ERROR, translate
        # as guardrail_blocked so the user sees a neutral refusal while
        # operators chase the drift via the chat.stream.consent_drift event.
        logger.error(
            "chat.stream.consent_drift",
            extra={
                "correlation_id": correlation_id,
                "exception_class": exc_class,
            },
        )
        return (
            "guardrail_blocked",
            _refused_payload(reason="guardrail_blocked", correlation_id=correlation_id),
            exc_class,
            logging.ERROR,
        )
    if isinstance(exc, ChatTransientError):
        return (
            "transient_error",
            _refused_payload(reason="transient_error", correlation_id=correlation_id),
            exc_class,
            logging.WARNING,
        )
    # Not-mapped → the caller raises 500; no chat-refused frame.
    raise exc


# ----------------------------------------------------------------------
# POST /chat/sessions
# ----------------------------------------------------------------------


@router.post(
    "/sessions",
    response_model=CreateSessionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_session_endpoint(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[SQLModelAsyncSession, Depends(get_db)],
    handler: Annotated[ChatSessionHandler, Depends(get_chat_session_handler)],
) -> CreateSessionResponse:
    """Create a new chat session.

    AC #1. Auth: Cognito bearer (header). Failure mapping:
      - ChatConsentRequiredError             → 403 CHAT_CONSENT_REQUIRED
      - ChatSessionCreationError             → 503 CHAT_BACKEND_UNAVAILABLE
      - ChatProviderNotSupportedError /
        ChatConfigurationError               → 503 CHAT_UNAVAILABLE
    """
    correlation_id = str(uuid.uuid4())
    try:
        handle = await handler.create_session(db, user)
    except ChatConsentRequiredError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": {
                    "code": "CHAT_CONSENT_REQUIRED",
                    "message": "Chat processing consent is required.",
                    "correlationId": correlation_id,
                }
            },
        ) from exc
    except ChatSessionCreationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": {
                    "code": "CHAT_BACKEND_UNAVAILABLE",
                    "message": "Chat backend is temporarily unavailable.",
                    "correlationId": correlation_id,
                }
            },
        ) from exc
    except (ChatProviderNotSupportedError, ChatConfigurationError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": {
                    "code": "CHAT_UNAVAILABLE",
                    "message": "Chat is not available in this deployment.",
                    "correlationId": correlation_id,
                }
            },
        ) from exc

    return CreateSessionResponse(
        session_id=str(handle.db_session_id),
        created_at=handle.created_at.isoformat(),
        consent_version_at_creation=(
            await _load_consent_version(db, handle.db_session_id)
        ),
    )


async def _load_consent_version(
    db: SQLModelAsyncSession, session_id: uuid.UUID
) -> str:
    row = await db.get(ChatSession, session_id)
    return row.consent_version_at_creation if row else ""


# ----------------------------------------------------------------------
# DELETE /chat/sessions/{id}
# ----------------------------------------------------------------------


@router.delete(
    "/sessions/{session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_session_endpoint(
    session_id: uuid.UUID,
    user_id: Annotated[uuid.UUID, Depends(get_current_user_id)],
    db: Annotated[SQLModelAsyncSession, Depends(get_db)],
    handler: Annotated[ChatSessionHandler, Depends(get_chat_session_handler)],
) -> None:
    """Terminate a chat session.

    AC #1. Auth: Cognito bearer. Per-row authorization via ``user_id`` FK;
    a cross-user id returns 404 (enumeration-safe). 503 on
    ``ChatSessionTerminationFailed``.
    """
    correlation_id = str(uuid.uuid4())
    chat_session = await db.get(ChatSession, session_id)
    if chat_session is None or chat_session.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": "CHAT_SESSION_NOT_FOUND",
                    "message": "Chat session not found.",
                    "correlationId": correlation_id,
                }
            },
        )
    handle = ChatSessionHandle(
        db_session_id=chat_session.id,
        agentcore_session_id=str(chat_session.id),
        created_at=chat_session.created_at,
        user_id=user_id,
    )
    try:
        await handler.terminate_session(handle)
    except ChatSessionTerminationFailed as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": {
                    "code": "CHAT_BACKEND_UNAVAILABLE",
                    "message": "Chat backend is temporarily unavailable.",
                    "correlationId": correlation_id,
                }
            },
        ) from exc
    # Bump last_active_at so the admin/forensic query can see when the
    # termination happened; returning 204 regardless of further state.
    await db.exec(
        sa_update(ChatSession)
        .where(ChatSession.id == session_id)
        .values(last_active_at=_now())
    )
    await db.commit()


# ----------------------------------------------------------------------
# Chat history surfaces (Story 10.10)
# ----------------------------------------------------------------------
#
# Scope (Story 10.10) — what these routes are AND ARE NOT:
#   IN:  GET /chat/sessions                 — list user's sessions (cursor-paged)
#        GET /chat/sessions/{id}/messages   — paged transcript (excludes role='tool')
#        DELETE /chat/sessions              — bulk delete (no path id, idempotent 204)
#   OUT: No new chat-runtime / tools / prompts (10.4a/b/c own).
#        No chat_processing consent UX (10.1a/b own).
#        No write-path mutations to messages (no edit / per-message redact).
#        No download/export endpoint (Epic 5 follow-up if requested).
#        No rate-limit envelope (10.11 owns).
#        No new observability metric filters/alarms in Terraform (10.9 owns —
#        events emitted here are filter-ready but not yet matched).
#        No `tool` role in transcript GET (privacy regression — see AC #3).
#        No migration / no schema changes (10.1b owns the schema).


class ChatSessionSummary(BaseModel):
    model_config = _camel_model()
    session_id: str
    created_at: str
    last_active_at: str
    consent_version_at_creation: str
    message_count: int


class ListChatSessionsResponse(BaseModel):
    model_config = _camel_model()
    sessions: list[ChatSessionSummary]
    next_cursor: str | None = None


class ChatMessageView(BaseModel):
    model_config = _camel_model()
    id: str
    role: str  # "user" | "assistant" | "system" — `tool` excluded by query.
    content: str
    guardrail_action: str
    redaction_flags: dict[str, Any]
    created_at: str


class ListChatMessagesResponse(BaseModel):
    model_config = _camel_model()
    messages: list[ChatMessageView]
    next_cursor: str | None = None


def _encode_cursor(ts: datetime, row_id: uuid.UUID) -> str:
    raw = f"{ts.isoformat()}|{row_id}"
    return base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=")


def _decode_cursor(token: str) -> tuple[datetime, uuid.UUID]:
    try:
        padded = token + "=" * (-len(token) % 4)
        raw = base64.urlsafe_b64decode(padded).decode()
        ts_iso, id_str = raw.split("|", 1)
        ts = datetime.fromisoformat(ts_iso)
        # Normalize to naive UTC so comparison against the column (naive in
        # this codebase) never raises offset-aware-vs-naive TypeError if the
        # client (or a future schema flip) hands us a tz-aware ISO string.
        if ts.tzinfo is not None:
            ts = ts.astimezone(UTC).replace(tzinfo=None)
        return ts, uuid.UUID(id_str)
    except (ValueError, binascii.Error) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": {
                    "code": "CHAT_HISTORY_BAD_CURSOR",
                    "message": "Cursor is malformed or expired.",
                }
            },
        ) from exc


@router.get("/sessions", response_model=ListChatSessionsResponse)
async def list_chat_sessions(
    user_id: Annotated[uuid.UUID, Depends(get_current_user_id)],
    db: Annotated[SQLModelAsyncSession, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
    cursor: str | None = None,
) -> ListChatSessionsResponse:
    """List the caller's chat sessions, paged via opaque ``(last_active_at, id)``
    keyset cursor. Cross-tenant rows never surface (per-row WHERE on ``user_id``).
    `messageCount` includes ``tool``-role rows so it matches `data-summary`.
    """
    correlation_id = str(uuid.uuid4())

    # Defensive: AC #2 says limit > 50 is silently clamped. FastAPI Query(le=50)
    # already enforces 1..50, so the only thing left is to honour the default.
    page_size = min(max(limit, 1), 50)

    msg_count = func.count(ChatMessage.id).label("message_count")
    stmt = (
        sa_select(
            ChatSession.id,
            ChatSession.created_at,
            ChatSession.last_active_at,
            ChatSession.consent_version_at_creation,
            msg_count,
        )
        .select_from(ChatSession)
        .outerjoin(ChatMessage, ChatMessage.session_id == ChatSession.id)
        .where(ChatSession.user_id == user_id)
        .group_by(
            ChatSession.id,
            ChatSession.created_at,
            ChatSession.last_active_at,
            ChatSession.consent_version_at_creation,
        )
        .order_by(ChatSession.last_active_at.desc(), ChatSession.id.desc())
        .limit(page_size + 1)
    )

    if cursor:
        cur_ts, cur_id = _decode_cursor(cursor)
        # Keyset: rows strictly after the cursor under (last_active_at DESC, id DESC).
        stmt = stmt.where(
            (ChatSession.last_active_at < cur_ts)
            | ((ChatSession.last_active_at == cur_ts) & (ChatSession.id < cur_id))
        )

    result = await db.exec(stmt)
    rows = list(result.all())

    next_cursor: str | None = None
    if len(rows) > page_size:
        rows = rows[:page_size]
        last = rows[-1]
        next_cursor = _encode_cursor(last.last_active_at, last.id)

    summaries = [
        ChatSessionSummary(
            session_id=str(r.id),
            created_at=r.created_at.isoformat(),
            last_active_at=r.last_active_at.isoformat(),
            consent_version_at_creation=r.consent_version_at_creation,
            message_count=int(r.message_count or 0),
        )
        for r in rows
    ]

    logger.info(
        "chat.history.listed",
        extra={
            "correlation_id": correlation_id,
            "user_id_hash": _hash_user_id(user_id),
            "session_count": len(summaries),
        },
    )

    return ListChatSessionsResponse(sessions=summaries, next_cursor=next_cursor)


@router.get(
    "/sessions/{session_id}/messages",
    response_model=ListChatMessagesResponse,
)
async def list_chat_messages(
    session_id: uuid.UUID,
    user_id: Annotated[uuid.UUID, Depends(get_current_user_id)],
    db: Annotated[SQLModelAsyncSession, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    cursor: str | None = None,
) -> ListChatMessagesResponse:
    """Page the transcript for a chat session.

    `tool`-role rows are excluded — they hold raw tool-call payloads that
    can echo PII (privacy footgun if surfaced). `messageCount` on the
    listing endpoint still includes them (FR35 honesty).

    404 (not 403) on cross-user access — enumeration-safe.
    """
    correlation_id = str(uuid.uuid4())

    chat_session = await db.get(ChatSession, session_id)
    if chat_session is None or chat_session.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": "CHAT_SESSION_NOT_FOUND",
                    "message": "Chat session not found.",
                    "correlationId": correlation_id,
                }
            },
        )

    page_size = min(max(limit, 1), 100)

    stmt = (
        sa_select(ChatMessage)
        .where(
            ChatMessage.session_id == session_id,
            ChatMessage.role != "tool",
        )
        .order_by(ChatMessage.created_at.asc(), ChatMessage.id.asc())
        .limit(page_size + 1)
    )
    if cursor:
        cur_ts, cur_id = _decode_cursor(cursor)
        stmt = stmt.where(
            (ChatMessage.created_at > cur_ts)
            | ((ChatMessage.created_at == cur_ts) & (ChatMessage.id > cur_id))
        )

    result = await db.exec(stmt)
    rows = list(result.scalars().all())

    next_cursor: str | None = None
    if len(rows) > page_size:
        rows = rows[:page_size]
        last = rows[-1]
        next_cursor = _encode_cursor(last.created_at, last.id)

    views = [
        ChatMessageView(
            id=str(m.id),
            role=m.role,
            content=m.content,
            guardrail_action=m.guardrail_action,
            redaction_flags=m.redaction_flags or {},
            created_at=m.created_at.isoformat(),
        )
        for m in rows
    ]

    logger.info(
        "chat.history.transcript_listed",
        extra={
            "correlation_id": correlation_id,
            "user_id_hash": _hash_user_id(user_id),
            "session_id": str(session_id),
            "message_count": len(views),
        },
    )

    return ListChatMessagesResponse(messages=views, next_cursor=next_cursor)


@router.delete("/sessions", status_code=status.HTTP_204_NO_CONTENT)
async def bulk_delete_chat_sessions(
    user_id: Annotated[uuid.UUID, Depends(get_current_user_id)],
    db: Annotated[SQLModelAsyncSession, Depends(get_db)],
    handler: Annotated[ChatSessionHandler, Depends(get_chat_session_handler)],
) -> None:
    """Bulk-delete every chat session belonging to the caller.

    NOTE: distinct path from ``DELETE /chat/sessions/{session_id}``. FastAPI
    matches exact paths before path-parameter paths so the no-id route is
    unambiguous; the 1-char path difference is easy to miss in review.

    Order of operations (per AC #4):
      1) Iterate the user's sessions and call ``handler.terminate_session``
         on each so any in-flight stream is cancelled before its row goes.
         Any ``ChatSessionTerminationFailed`` aborts the whole op (no partial
         DB deletion). The DB delete only fires after every terminate succeeds.
      2) Pre-count messages (for the structured-log audit field).
      3) Single ``DELETE FROM chat_sessions WHERE user_id = $1`` — the FK
         cascade on chat_messages.session_id removes messages atomically.
      4) Returns 204 even when the user had zero sessions (idempotent).

    NOTE on the AC #4 "all-or-nothing runtime termination" guarantee: the
    DB half is genuinely atomic (single DELETE in one transaction). The
    runtime half is best-effort — ``terminate_session`` is not transactional
    across AgentCore, so if session N fails after sessions 1..N-1 succeeded,
    those earlier runtimes are already gone while DB rows for all sessions
    remain. ``terminate_session`` is expected to be idempotent (re-calling
    on an already-terminated handle no-ops), so a retry of the bulk-delete
    is safe and converges to the desired end state.
    """
    correlation_id = str(uuid.uuid4())

    # (1) Load sessions and terminate runtime handles. Series, not parallel —
    # mirrors terminate_all_user_sessions's reasoning re: per-user tier limits.
    sessions_result = await db.exec(
        sa_select(ChatSession.id, ChatSession.created_at).where(
            ChatSession.user_id == user_id
        )
    )
    session_rows = list(sessions_result.all())

    for row in session_rows:
        handle = ChatSessionHandle(
            db_session_id=row.id,
            agentcore_session_id=str(row.id),
            created_at=row.created_at,
            user_id=user_id,
        )
        try:
            await handler.terminate_session(handle)
        except ChatSessionTerminationFailed as exc:
            logger.error(
                "chat.history.bulk_delete_failed",
                extra={
                    "correlation_id": correlation_id,
                    "user_id_hash": _hash_user_id(user_id),
                    "failure_stage": "agentcore_terminate",
                },
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "error": {
                        "code": "CHAT_BACKEND_UNAVAILABLE",
                        "message": "Chat backend is temporarily unavailable.",
                        "correlationId": correlation_id,
                    }
                },
            ) from exc

    # (2) Pre-delete COUNT for the audit log — same query AC #5 uses on
    # the data-summary endpoint, kept consistent with the actual destruction.
    msg_count_result = await db.exec(
        sa_select(func.count(ChatMessage.id))
        .select_from(ChatMessage)
        .join(ChatSession, ChatMessage.session_id == ChatSession.id)
        .where(ChatSession.user_id == user_id)
    )
    messages_to_delete = int(msg_count_result.scalar_one() or 0)

    # (3) Bulk delete. FK cascade fans messages out.
    try:
        await db.exec(
            sa_delete(ChatSession).where(ChatSession.user_id == user_id)
        )
        await db.commit()
    except Exception as exc:  # noqa: BLE001
        await db.rollback()
        logger.error(
            "chat.history.bulk_delete_failed",
            extra={
                "correlation_id": correlation_id,
                "user_id_hash": _hash_user_id(user_id),
                "failure_stage": "db_delete",
            },
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": {
                    "code": "CHAT_BACKEND_UNAVAILABLE",
                    "message": "Chat backend is temporarily unavailable.",
                    "correlationId": correlation_id,
                }
            },
        ) from exc

    logger.warning(
        "chat.history.bulk_deleted",
        extra={
            "correlation_id": correlation_id,
            "user_id_hash": _hash_user_id(user_id),
            "sessions_deleted": len(session_rows),
            "messages_deleted": messages_to_delete,
        },
    )


# ----------------------------------------------------------------------
# POST /chat/sessions/{id}/turns/stream
# ----------------------------------------------------------------------


def _sse_event(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def _camelify_keys(value: Any) -> Any:
    """Recursive snake_case → camelCase converter for nested dict/list payloads.

    Used by the ``chat-citations`` SSE arm so the wire payload matches the
    repo's camelCase convention without each citation model having to declare
    its own alias generator. Values pass through unchanged.
    """
    if isinstance(value, dict):
        return {to_camel(str(k)): _camelify_keys(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_camelify_keys(v) for v in value]
    return value


@router.post("/sessions/{session_id}/turns/stream")
async def stream_chat_turn(
    session_id: uuid.UUID,
    request: Request,
    token: str,
    payload: StreamTurnRequest,
    db: Annotated[SQLModelAsyncSession, Depends(get_db)],
    handler: Annotated[ChatSessionHandler, Depends(get_chat_session_handler)],
) -> StreamingResponse:
    """SSE streaming endpoint for a single chat turn.

    AC #1, #4, #5. Auth: ``?token=<JWT>`` query-string (EventSource can't
    send headers). Request body: ``{message: str}`` (length capped at
    ``CHAT_MAX_INPUT_CHARS``; 422 on overflow — NOT a ``chat-refused``
    frame, this is a client-shape failure before the stream opens).
    """
    # Auth first — a bad token must never open the stream.
    user_id = await get_user_id_from_token(token, db)

    # Session ownership — 404 (not 403) on cross-user access to prevent
    # enumeration of other users' session ids.
    chat_session = await db.get(ChatSession, session_id)
    if chat_session is None or chat_session.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": "CHAT_SESSION_NOT_FOUND",
                    "message": "Chat session not found.",
                }
            },
        )

    # Input length cap. A 422 before the stream opens is a client-shape
    # failure (distinct from CHAT_REFUSED.guardrail_blocked).
    if len(payload.message) > CHAT_MAX_INPUT_CHARS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": {
                    "code": "CHAT_INPUT_TOO_LONG",
                    "message": (
                        f"Input is {len(payload.message)} chars; max is "
                        f"{CHAT_MAX_INPUT_CHARS}."
                    ),
                }
            },
        )

    correlation_id = str(uuid.uuid4())
    handle = ChatSessionHandle(
        db_session_id=chat_session.id,
        agentcore_session_id=str(chat_session.id),
        created_at=chat_session.created_at,
        user_id=user_id,
    )

    # Resolve Guardrail config now so a misconfiguration fails BEFORE the
    # stream opens (AC #4 — ChatConfigurationError → 500, not chat-refused).
    guardrail_arn = settings.BEDROCK_GUARDRAIL_ARN
    guardrail_id: str | None = None
    guardrail_version: str | None = None
    if guardrail_arn:
        # ARN pattern: arn:aws:bedrock:<region>:<acct>:guardrail/<id>
        tail = guardrail_arn.rsplit("/", 1)[-1]
        if ":" in tail:
            guardrail_id, guardrail_version = tail.split(":", 1)
        else:
            guardrail_id = tail
            guardrail_version = "DRAFT"

    start_ts = time.monotonic()

    async def event_generator() -> AsyncGenerator[str, None]:
        logger.info(
            "chat.stream.opened",
            extra={
                "correlation_id": correlation_id,
                "db_session_id": str(handle.db_session_id),
                "user_id_hash": _hash_user_id(user_id),
                "input_char_len": len(payload.message),
                "input_prefix_hash": _input_prefix_hash(payload.message),
            },
        )

        token_count = 0
        phase = "before_first_token"
        first_token_logged = False
        last_yield_at = time.monotonic()

        # Emit chat-open first, before any handler work — confirms the API
        # layer passed auth + owned the session before streaming begins.
        yield _sse_event(
            "chat-open",
            {
                "correlationId": correlation_id,
                "sessionId": str(handle.db_session_id),
            },
        )

        agen = handler.send_turn_stream(
            db,
            handle,
            payload.message,
            correlation_id=correlation_id,
            guardrail_id=guardrail_id,
            guardrail_version=guardrail_version,
        )
        # Persistent anext task + asyncio.shield is the canonical way to
        # drive a heartbeat without poisoning the producer: ``wait_for``
        # cancels the coroutine it waits on, which would cancel mid-await
        # inside the handler (DB commit, backend stream). Keeping one task
        # alive across timeouts lets the handler make progress between
        # heartbeats.
        anext_task: asyncio.Task | None = None
        try:
            anext_task = asyncio.ensure_future(agen.__anext__())
            while True:
                if await request.is_disconnected():
                    logger.info(
                        "chat.stream.disconnected",
                        extra={
                            "correlation_id": correlation_id,
                            "db_session_id": str(handle.db_session_id),
                            "total_ms": int(
                                (time.monotonic() - start_ts) * 1000
                            ),
                            "token_count": token_count,
                            "phase": phase,
                        },
                    )
                    return

                try:
                    remaining = CHAT_SSE_HEARTBEAT_INTERVAL - (
                        time.monotonic() - last_yield_at
                    )
                    if remaining <= 0:
                        remaining = 0.01
                    event = await asyncio.wait_for(
                        asyncio.shield(anext_task), timeout=remaining
                    )
                except asyncio.TimeoutError:
                    yield ": heartbeat\n\n"
                    last_yield_at = time.monotonic()
                    continue
                except StopAsyncIteration:
                    return

                # Event received — queue the next pull before yielding so
                # the handler keeps producing while the client drains.
                anext_task = asyncio.ensure_future(agen.__anext__())

                last_yield_at = time.monotonic()
                if isinstance(event, ChatStreamStarted):
                    # chat-open already emitted above; the handler's Started
                    # event is internal-only (produces no wire frame).
                    continue
                if isinstance(event, ChatToolHopStarted):
                    yield _sse_event(
                        "chat-thinking",
                        {
                            "toolName": event.tool_name,
                            "hopIndex": event.hop_index,
                        },
                    )
                    continue
                if isinstance(event, ChatToolHopCompleted):
                    # Collapsed — not surfaced to the client (AC #5).
                    continue
                if isinstance(event, ChatCitationsAttached):
                    yield _sse_event(
                        "chat-citations",
                        {
                            "citations": [
                                _camelify_keys(citation_to_json_dict(c))
                                for c in event.citations
                            ],
                        },
                    )
                    continue
                if isinstance(event, ChatTokenDelta):
                    if not first_token_logged:
                        logger.info(
                            "chat.stream.first_token",
                            extra={
                                "correlation_id": correlation_id,
                                "db_session_id": str(handle.db_session_id),
                                "ttfb_ms": int(
                                    (time.monotonic() - start_ts) * 1000
                                ),
                            },
                        )
                        first_token_logged = True
                        phase = "during_stream"
                    token_count += 1
                    yield _sse_event("chat-token", {"delta": event.text})
                    continue
                if isinstance(event, ChatStreamCompleted):
                    yield _sse_event(
                        "chat-complete",
                        {
                            "inputTokens": event.input_tokens,
                            "outputTokens": event.output_tokens,
                            "sessionTurnCount": event.session_turn_count,
                            "summarizationApplied": event.summarization_applied,
                            "tokenSource": event.token_source,
                            "toolCallCount": event.tool_call_count,
                        },
                    )
                    logger.info(
                        "chat.stream.completed",
                        extra={
                            "correlation_id": correlation_id,
                            "db_session_id": str(handle.db_session_id),
                            "total_ms": int(
                                (time.monotonic() - start_ts) * 1000
                            ),
                            "token_count": token_count,
                            "input_tokens": event.input_tokens,
                            "output_tokens": event.output_tokens,
                            "tool_call_count": event.tool_call_count,
                            "token_source": event.token_source,
                        },
                    )
                    return
        except (
            ChatInputBlockedError,
            ChatPromptLeakDetectedError,
            ChatToolLoopExceededError,
            ChatToolNotAllowedError,
            ChatToolAuthorizationError,
            ChatGuardrailInterventionError,
            ChatRateLimitedError,
            ChatConsentRequiredError,
            ChatTransientError,
        ) as exc:
            reason, refused_payload, exc_class, log_level = _translate_exception(
                exc, correlation_id=correlation_id
            )
            logger.log(
                log_level,
                "chat.stream.refused",
                extra={
                    "correlation_id": correlation_id,
                    "db_session_id": str(handle.db_session_id),
                    "reason": reason,
                    "exception_class": exc_class,
                },
            )
            yield _sse_event("chat-refused", refused_payload)
            return
        except ChatConfigurationError as exc:
            # Deployment misconfiguration (missing Guardrail ARN, IAM gap,
            # canary-load failure, tool bind failure). Operators get paged
            # via the ERROR log + Story 10.9 alarms, but because chat-open
            # has already flushed we still owe the client a terminal frame
            # per AC #5 / AC #14 invariant 2 — emit ``transient_error`` so
            # the UI surfaces "try again in a moment" and unlocks the
            # composer instead of hanging in a half-open stream.
            logger.error(
                "chat.stream.configuration_error",
                extra={
                    "correlation_id": correlation_id,
                    "db_session_id": str(handle.db_session_id),
                    "exception_class": type(exc).__name__,
                },
            )
            yield _sse_event(
                "chat-refused",
                _refused_payload(
                    reason="transient_error", correlation_id=correlation_id
                ),
            )
            return
        except asyncio.CancelledError:
            # Client disconnect / server shutdown — logged above in the
            # is_disconnected branch when the API layer notices. We must
            # NOT emit a frame here (the peer is already gone); propagate
            # so FastAPI's StreamingResponse finalizes cleanly.
            raise
        except Exception as exc:  # noqa: BLE001
            # Unmapped exception after chat-open has flushed — SSE contract
            # (AC #5 / AC #14 invariant 2) demands a terminal frame. Log as
            # ERROR so operators can triage; surface ``transient_error`` to
            # the client so the UI state machine can exit ``streaming``.
            logger.exception(
                "chat.stream.internal_error",
                extra={
                    "correlation_id": correlation_id,
                    "db_session_id": str(handle.db_session_id),
                    "exception_class": type(exc).__name__,
                },
            )
            yield _sse_event(
                "chat-refused",
                _refused_payload(
                    reason="transient_error", correlation_id=correlation_id
                ),
            )
            return
        finally:
            # Cancel any outstanding anext task + close the generator so
            # the handler's finally blocks fire (canary scan, partial row
            # persistence). Without this, a disconnect / exception leaves
            # the handler suspended and its finalizer never runs.
            if anext_task is not None and not anext_task.done():
                anext_task.cancel()
                try:
                    await anext_task
                except (asyncio.CancelledError, StopAsyncIteration, Exception):
                    pass
            try:
                await agen.aclose()
            except Exception:  # noqa: BLE001
                pass

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers=SSE_RESPONSE_HEADERS,
    )


def _input_prefix_hash(s: str) -> str:
    """Blake2b-8 prefix hash — same shape as ``input_validator._prefix_hash``."""
    import hashlib

    return hashlib.blake2b(s[:64].encode("utf-8"), digest_size=8).hexdigest()


__all__ = [
    "CHAT_MAX_INPUT_CHARS",
    "CHAT_SSE_HEARTBEAT_INTERVAL",
    "router",
]
