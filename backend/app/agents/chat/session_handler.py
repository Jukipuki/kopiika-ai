"""Chat session handler — the 4-method public API for Epic 10 chat.

Story 10.4a (Phase A per ADR-0004 — direct ``bedrock-runtime:InvokeModel``
via ``llm.py``). Phase B (story ``10.4a-runtime``) swaps the backend to
AgentCore Runtime without changing this file.

## Contract surface

- ``create_session(db, user) -> ChatSessionHandle``
- ``send_turn(handle, user_message) -> ChatTurnResponse``
- ``terminate_session(handle) -> None``
- ``terminate_all_user_sessions(db, user) -> None``

## Deferrals by scope (do NOT add here — sibling/downstream stories own them)

- Tool manifest + tool-use loop              → Story 10.4c
- System-prompt hardening + canary tokens    → Story 10.4b
- SSE streaming + CHAT_REFUSED envelope      → Story 10.5
- Bedrock Guardrails attach at invoke        → Story 10.5
- Contextual-grounding threshold tuning      → Story 10.6a
- Rate-limit envelope (60/hr, 10 concurrent) → Story 10.11
- Chat UI / UX states                        → Stories 10.7 + 10.3a/b
- Cross-session memory / long-term memory    → TD-040 (explicitly deferred)

## Model split (AC #9)

The chat turn itself runs on ``chat_default`` (Sonnet) via the backend for
conversational quality. **Summarization runs on ``agent_default`` (Haiku)**
via ``get_llm_client()`` — a reduction operation where cost/latency beats
quality. A future cost-optimization pass must keep this split.

# Downstream: 10.4b adds system-prompt + canary injection at send_turn boundary; 10.4c adds tool manifest; 10.5 wraps send_turn in an SSE streaming wrapper + CHAT_REFUSED envelope; 10.6a tunes grounding at Guardrail attach time.
# ADR: docs/adr/0004-chat-runtime-phasing.md (Phase A vs B split — handler API stable across phases).
"""

from __future__ import annotations

import hashlib
import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import update as sa_update
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession as SQLModelAsyncSession

from app.agents.chat.chat_backend import (
    ChatBackend,
    ChatProviderNotSupportedError,
    ChatSessionCreationError,
    ChatSessionTerminationFailed,
    build_backend,
)
from app.agents.chat.memory_bounds import (
    count_turns,
    estimate_tokens,
    should_summarize,
    split_for_summarization,
)
from app.core.config import settings
from app.models.chat_message import ChatMessage
from app.models.chat_session import ChatSession
from app.models.user import User

logger = logging.getLogger(__name__)


def _now() -> datetime:
    # Match the ChatSession model convention — tz-naive UTC.
    return datetime.now(UTC).replace(tzinfo=None)


def _hash_user_id(user_id: uuid.UUID) -> str:
    """64-bit prefix of blake2b(user_id.bytes). Per AC #12 — keeps logs
    joinable across events without exposing the raw UUID.
    """
    return hashlib.blake2b(user_id.bytes, digest_size=8).hexdigest()


@dataclass(frozen=True)
class ChatSessionHandle:
    """Returned by ``create_session`` — opaque to callers.

    ``agentcore_session_id`` is the backend-assigned session id. In Phase A
    it equals ``str(db_session_id)`` (no remote state); in Phase B it is
    the AWS-assigned session id from ``CreateSession``.
    """

    db_session_id: uuid.UUID
    agentcore_session_id: str
    created_at: datetime
    user_id: uuid.UUID


@dataclass(frozen=True)
class ChatTurnResponse:
    assistant_message: str
    input_tokens: int
    output_tokens: int
    session_turn_count: int
    summarization_applied: bool
    token_source: str  # "model" | "tiktoken"


class ChatSessionHandler:
    """Ties together: (1) consent + DB persistence, (2) memory bounds +
    summarization, (3) the concrete ``ChatBackend`` (Phase A direct / Phase B
    AgentCore).

    This module ships **intra-session memory only**. Cross-session (per-user
    long-term) memory is explicitly out of scope — see TD-040.
    """

    def __init__(self, backend: ChatBackend) -> None:
        self._backend = backend
        self._correlation_id_factory = lambda: str(uuid.uuid4())

    # ------------------------------------------------------------------
    # create_session (AC #7 + AC #12)
    # ------------------------------------------------------------------

    async def create_session(
        self, db: SQLModelAsyncSession, user: User
    ) -> ChatSessionHandle:
        correlation_id = self._correlation_id_factory()
        # DB-first: consent check + row insert happen inside chat_session_service.
        # Failure here raises ChatConsentRequiredError, cheap and idempotent.
        from app.services.chat_session_service import create_chat_session

        chat_session = await create_chat_session(db, user)
        try:
            agentcore_session_id = await self._backend.create_remote_session(
                chat_session.id
            )
        except Exception as exc:  # noqa: BLE001 — compensating delete pattern
            # Compensating delete of the orphan DB row. Per AC #7:
            # "a chat_sessions row without a corresponding AgentCore session
            # is worse than a raised exception".
            from sqlalchemy import delete as sa_delete

            await db.exec(
                sa_delete(ChatSession).where(ChatSession.id == chat_session.id)
            )
            await db.commit()
            logger.error(
                "chat.session.creation_failed",
                extra={
                    "correlation_id": correlation_id,
                    "db_session_id": str(chat_session.id),
                    "user_id_hash": _hash_user_id(user.id),
                    "consent_version_at_creation": chat_session.consent_version_at_creation,
                    "error_class": type(exc).__name__,
                    "error_message": str(exc)[:200],
                },
            )
            raise ChatSessionCreationError(
                f"Backend session creation failed: {type(exc).__name__}"
            ) from exc

        logger.info(
            "chat.session.created",
            extra={
                "correlation_id": correlation_id,
                "db_session_id": str(chat_session.id),
                "agentcore_session_id": agentcore_session_id,
                "user_id_hash": _hash_user_id(user.id),
                "consent_version_at_creation": chat_session.consent_version_at_creation,
            },
        )
        return ChatSessionHandle(
            db_session_id=chat_session.id,
            agentcore_session_id=agentcore_session_id,
            created_at=chat_session.created_at,
            user_id=user.id,
        )

    # ------------------------------------------------------------------
    # send_turn (AC #7, #9, #10, #12)
    # ------------------------------------------------------------------

    async def send_turn(
        self,
        db: SQLModelAsyncSession,
        handle: ChatSessionHandle,
        user_message: str,
    ) -> ChatTurnResponse:
        """Persist user turn → (maybe summarize) → invoke model → persist assistant turn.

        Transaction topology (per AC #7):
        - User message is committed first (own txn) so a mid-flight crash
          still leaves an audit trail.
        - Assistant message + ``last_active_at`` update commit together
          (one txn) so a half-written turn is impossible.
        """
        correlation_id = self._correlation_id_factory()
        history = await self._load_history(db, handle.db_session_id)

        # 1. Persist the user turn eagerly (separate txn).
        user_row = ChatMessage(
            session_id=handle.db_session_id, role="user", content=user_message
        )
        db.add(user_row)
        await db.commit()
        history.append(user_row)

        # 2. Apply memory bounds BEFORE model invocation (AC #9 "trim before invoke").
        # NOTE on consent drift: consent is verified at create_session only.
        # A synchronous send_turn after a mid-session revoke will still
        # invoke the model; the revoke cascade will clean up rows afterwards.
        # Stream-level cancellation (the "in-flight turn" half of Consent
        # Drift Policy) is Story 10.5's SSE concern, not 10.4a's.
        summarization_applied = False
        turns = count_turns(history)
        tokens = estimate_tokens(history)
        if should_summarize(
            turns,
            tokens,
            settings.CHAT_SESSION_MAX_TURNS,
            settings.CHAT_SESSION_MAX_TOKENS,
        ):
            history, summarization_applied = await self._summarize_and_rebuild_context(
                db=db,
                handle=handle,
                full_history=history,
                correlation_id=correlation_id,
            )

        # 3. Invoke backend. Context messages are history MINUS the trailing
        #    user row (the backend appends it as the prompt separately).
        context_messages = history[:-1]
        try:
            result = await self._backend.invoke(
                db_session_id=handle.db_session_id,
                context_messages=context_messages,
                user_message=user_message,
            )
        except Exception:
            # Backend already translated to ChatConfigurationError / ChatTransientError.
            # Caller (10.5's SSE route) owns the user-facing envelope. Do not
            # swallow here — the user turn is already persisted as audit trail.
            raise

        # 4. Persist assistant turn + bump last_active_at atomically.
        assistant_row = ChatMessage(
            session_id=handle.db_session_id,
            role="assistant",
            content=result.text,
        )
        db.add(assistant_row)
        await db.exec(
            sa_update(ChatSession)
            .where(ChatSession.id == handle.db_session_id)
            .values(last_active_at=_now())
        )
        await db.commit()

        logger.info(
            "chat.turn.completed",
            extra={
                "correlation_id": correlation_id,
                "db_session_id": str(handle.db_session_id),
                "input_tokens": result.input_tokens,
                "output_tokens": result.output_tokens,
                "session_turn_count": count_turns(history),
                "summarization_applied": summarization_applied,
                "token_source": result.token_source,
            },
        )
        return ChatTurnResponse(
            assistant_message=result.text,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            session_turn_count=count_turns(history),
            summarization_applied=summarization_applied,
            token_source=result.token_source,
        )

    # ------------------------------------------------------------------
    # Summarization (AC #9)
    # ------------------------------------------------------------------

    async def _summarize_and_rebuild_context(
        self,
        *,
        db: SQLModelAsyncSession,
        handle: ChatSessionHandle,
        full_history: list[ChatMessage],
        correlation_id: str,
    ) -> tuple[list[ChatMessage], bool]:
        """Summarize older turns, persist the summary, return ``(history, did_summarize)``.

        ``did_summarize`` is ``False`` when the policy decided no summarization
        was needed (e.g. token bound hit but fewer than ``keep_recent`` turns
        exist — the context can't be compacted further). Callers use the flag
        to drive ``chat.turn.completed`` telemetry accurately — setting the
        flag unconditionally would inflate Story 10.9's summarization-rate
        metric with phantom triggers.

        Failure path: on any summarization LLM error, fall back to dropping
        the older turns AND emit ``chat.summarization.failed`` at ERROR. This
        still counts as ``did_summarize=True`` — the compaction happened,
        just via drop rather than summarize. Rationale at AC #9 ("a chat
        turn that blocks because summarization failed is worse UX than a
        turn that proceeds with truncated context").
        """
        keep_recent = settings.CHAT_SUMMARIZATION_KEEP_RECENT_TURNS
        older, recent = split_for_summarization(full_history, keep_recent)
        if not older:
            # Nothing to compact (history shorter than keep_recent threshold).
            # Report honestly: no summarization occurred this turn.
            return full_history, False

        # Exclude prior `role='system'` summary rows from the summarizer
        # input — feeding summaries back into a new summary compounds lossy
        # compression ("summary-of-summary-of-summary..."). The new summary
        # replaces all prior summaries in the returned context.
        older_to_summarize = [m for m in older if m.role != "system"]

        logger.info(
            "chat.summarization.triggered",
            extra={
                "correlation_id": correlation_id,
                "db_session_id": str(handle.db_session_id),
                "older_messages_count": len(older_to_summarize),
                "recent_messages_count": len(recent),
            },
        )

        try:
            summary_text = await self._call_summarizer(older_to_summarize)
        except Exception as exc:  # noqa: BLE001 — fallback-drop is the spec
            logger.error(
                "chat.summarization.failed",
                extra={
                    "correlation_id": correlation_id,
                    "db_session_id": str(handle.db_session_id),
                    "dropped_turns_count": count_turns(older_to_summarize),
                    "error_class": type(exc).__name__,
                },
            )
            # Fallback: drop older turns silently-but-logged. The returned
            # history is the recent tail only (plus nothing for older).
            return list(recent), True

        # Persist the summary as a role='system' ChatMessage.
        summary_row = ChatMessage(
            session_id=handle.db_session_id,
            role="system",
            content=summary_text,
        )
        db.add(summary_row)
        await db.commit()
        return [summary_row, *recent], True

    async def _call_summarizer(self, older: list[ChatMessage]) -> str:
        # Haiku-class via llm.py (NOT chat_default Sonnet) — see module
        # docstring "Model split". Summarization is NOT guardrail-subject
        # (internal compression step, not a user-facing turn).
        from langchain_core.messages import HumanMessage

        from app.agents.chat.summarization_prompt import render
        from app.agents.llm import get_llm_client, record_failure, record_success

        prompt = render(older)
        client = get_llm_client()
        try:
            response = await client.ainvoke([HumanMessage(content=prompt)])
        except Exception:
            record_failure(settings.LLM_PROVIDER)
            raise
        else:
            record_success(settings.LLM_PROVIDER)
        content = response.content
        if isinstance(content, list):
            return "".join(
                part.get("text", "") if isinstance(part, dict) else str(part)
                for part in content
            )
        return str(content)

    async def _load_history(
        self, db: SQLModelAsyncSession, session_id: uuid.UUID
    ) -> list[ChatMessage]:
        stmt = (
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at)
        )
        result = await db.exec(stmt)
        return list(result.all())

    # ------------------------------------------------------------------
    # terminate_session (AC #7, #12)
    # ------------------------------------------------------------------

    async def terminate_session(self, handle: ChatSessionHandle) -> None:
        correlation_id = self._correlation_id_factory()
        try:
            await self._backend.terminate_remote_session(handle.agentcore_session_id)
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "chat.session.termination_failed",
                extra={
                    "correlation_id": correlation_id,
                    "db_session_id": str(handle.db_session_id),
                    "error_class": type(exc).__name__,
                    "error_message": str(exc)[:200],
                },
            )
            raise ChatSessionTerminationFailed(
                f"Backend terminate failed: {type(exc).__name__}"
            ) from exc
        logger.info(
            "chat.session.terminated",
            extra={
                "correlation_id": correlation_id,
                "db_session_id": str(handle.db_session_id),
                "agentcore_session_id": handle.agentcore_session_id,
            },
        )

    # ------------------------------------------------------------------
    # terminate_all_user_sessions (AC #11, #14)
    # ------------------------------------------------------------------

    async def terminate_all_user_sessions(
        self, db: SQLModelAsyncSession, user: User
    ) -> None:
        """Series-iterate user's active sessions, call backend terminate on
        each. Fail-open: backend errors are logged, not propagated — consent
        revocation must not be blocked by termination failures (AC #11).

        Series not parallel: AgentCore per-user tier limits are not well
        documented, so we err on the side of not fanning out.
        """
        correlation_id = self._correlation_id_factory()
        stmt = select(ChatSession).where(ChatSession.user_id == user.id)
        result = await db.exec(stmt)
        sessions = list(result.all())

        for session in sessions:
            try:
                # Phase A: agentcore_session_id == str(db_session_id).
                # Phase B: caller would need to look up the remote session id.
                await self._backend.terminate_remote_session(str(session.id))
            except Exception as exc:  # noqa: BLE001 — fail-open per AC #11
                logger.error(
                    "chat.session.termination_failed",
                    extra={
                        "correlation_id": correlation_id,
                        "db_session_id": str(session.id),
                        "error_class": type(exc).__name__,
                        "error_message": str(exc)[:200],
                    },
                )


# ----------------------------------------------------------------------
# Module-level singleton factory
# ----------------------------------------------------------------------

_HANDLER: ChatSessionHandler | None = None


def get_chat_session_handler() -> ChatSessionHandler:
    """Return the process-wide ``ChatSessionHandler``.

    First-call semantics (AC #14):
    - Instantiates ``DirectBedrockBackend`` (Phase A) or raises
      ``ChatProviderNotSupportedError`` if ``LLM_PROVIDER != "bedrock"``.
    - Importing this module does NOT hit AWS — the backend constructor is
      the only place ``settings.LLM_PROVIDER`` is asserted.
    """
    global _HANDLER
    if _HANDLER is None:
        _HANDLER = ChatSessionHandler(build_backend())
    return _HANDLER


def _reset_singleton_for_tests() -> None:
    """Test helper — do NOT call in production. Clears the cached handler so
    tests can re-exercise the import-time guard under varied settings.
    """
    global _HANDLER
    _HANDLER = None


async def terminate_all_user_sessions_fail_open(
    db: SQLModelAsyncSession, user: User
) -> None:
    """Wrapper called by ``consent_service.revoke_chat_consent`` (AC #11 + #14).

    On non-bedrock deployments (e.g., local dev with ``LLM_PROVIDER=anthropic``),
    the handler's backend constructor raises ``ChatProviderNotSupportedError``
    — caught here and treated as "nothing to terminate". Revocation proceeds.
    """
    try:
        handler = get_chat_session_handler()
    except ChatProviderNotSupportedError:
        logger.info(
            "chat.session.termination_skipped_nonbedrock",
            extra={"user_id_hash": _hash_user_id(user.id)},
        )
        return
    await handler.terminate_all_user_sessions(db, user)
