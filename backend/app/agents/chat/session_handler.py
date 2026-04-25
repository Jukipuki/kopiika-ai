"""Chat session handler — the 4-method public API for Epic 10 chat.

Story 10.4a (Phase A per ADR-0004 — direct ``bedrock-runtime:InvokeModel``
via ``llm.py``). Phase B (story ``10.4a-runtime``) swaps the backend to
AgentCore Runtime without changing this file.

## Contract surface

- ``create_session(db, user) -> ChatSessionHandle``
- ``send_turn(handle, user_message) -> ChatTurnResponse`` — non-streaming; used by
  Story 10.8b's safety-harness runner which wants the single final string.
- ``send_turn_stream(handle, user_message, *, correlation_id) -> AsyncIterator[ChatStreamEvent]``
  — streaming variant (Story 10.5); used by the FastAPI SSE route.
- ``terminate_session(handle) -> None``
- ``terminate_all_user_sessions(db, user) -> None``

## Deferrals by scope (do NOT add here — sibling/downstream stories own them)

- Tool manifest + tool-use loop              → Story 10.4c
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

# 10.4b landed: system prompt + input validator + canary scan ship here.
# 10.4c landed: tool manifest + dispatcher + tool-loop in DirectBedrockBackend + role='tool' persistence.
# Downstream: 10.6a tunes grounding at Guardrail attach time; 10.6b reads role='tool' rows for citation assembly.
# ADR: docs/adr/0004-chat-runtime-phasing.md (Phase A vs B split — handler API stable across phases).
"""

from __future__ import annotations

import hashlib
import logging
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import update as sa_update
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession as SQLModelAsyncSession

from app.agents.chat.canaries import CanaryLoadError, get_canary_set
from app.agents.chat.canary_detector import (
    ChatPromptLeakDetectedError,
    scan_for_canaries,
)
from app.agents.chat.chat_backend import (
    BackendStreamDone,
    BackendTokenDelta,
    BackendToolHop,
    ChatBackend,
    ChatConfigurationError,
    ChatGuardrailInterventionError,
    ChatProviderNotSupportedError,
    ChatSessionCreationError,
    ChatSessionTerminationFailed,
    build_backend,
)
from app.agents.chat.stream_events import (
    ChatStreamCompleted,
    ChatStreamEvent,
    ChatStreamStarted,
    ChatTokenDelta,
    ChatToolHopCompleted,
    ChatToolHopStarted,
)
from app.agents.chat.input_validator import (
    INPUT_VALIDATOR_VERSION,
    ChatInputBlockedError,
    _prefix_hash,
    validate_input,
)
from app.agents.chat.memory_bounds import (
    count_turns,
    estimate_tokens,
    should_summarize,
    split_for_summarization,
)
from app.agents.chat.system_prompt import (
    CHAT_SYSTEM_PROMPT_VERSION,
    render_system_prompt,
)
from app.agents.chat.tools import CHAT_TOOL_MANIFEST_VERSION
from app.agents.chat.tools.tool_errors import (
    ChatToolAuthorizationError,
    ChatToolLoopExceededError,
    ChatToolNotAllowedError,
)
from app.core.config import settings
from app.models.chat_message import ChatMessage
from app.models.chat_session import ChatSession
from app.models.user import User

logger = logging.getLogger(__name__)


def _now() -> datetime:
    # Match the ChatSession model convention — tz-naive UTC.
    return datetime.now(UTC).replace(tzinfo=None)


def _serialize_tool_call(tc: object) -> str:
    """Serialize a ``ToolResult`` for persistence as ``ChatMessage.content``.

    The resulting JSON string is what Story 10.6b's citation assembler
    deserializes when building per-message citations.
    """
    import json as _json

    return _json.dumps(
        {
            "tool_name": getattr(tc, "tool_name", None),
            "ok": getattr(tc, "ok", None),
            "payload": getattr(tc, "payload", None),
            "error_kind": getattr(tc, "error_kind", None),
            "elapsed_ms": getattr(tc, "elapsed_ms", None),
        },
        default=str,
    )


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
        """Persist user turn → validate → (maybe summarize) → invoke → scan → persist assistant turn.

        Story 10.4b six-step pipeline (order = threat model; reversing steps
        defeats the layers):
          Step 0 — persist user message (audit-trail invariant from 10.4a)
          Step 1 — input validator  (Story 10.4b AC #4, defense layer 1)
          Step 2 — load canaries + render hardened system prompt (AC #1 + #2)
          Step 3 — memory bounds / summarization (unchanged from 10.4a)
          Step 4 — backend invoke with system_prompt kwarg (AC #5)
          Step 5 — canary scan on model output (AC #3, defense layer "canary")
          Step 6 — persist assistant + bump last_active_at (unchanged from 10.4a)

        Transaction topology (per 10.4a AC #7):
        - User message is committed first (own txn) so a mid-flight crash
          still leaves an audit trail.
        - Assistant message + ``last_active_at`` update commit together
          (one txn) so a half-written turn is impossible.
        """
        correlation_id = self._correlation_id_factory()
        history = await self._load_history(db, handle.db_session_id)

        # Step 0 — persist the user turn eagerly (separate txn).
        user_row = ChatMessage(
            session_id=handle.db_session_id, role="user", content=user_message
        )
        db.add(user_row)
        await db.commit()
        history.append(user_row)

        # Step 1 — input validator (Story 10.4b AC #4). Runs AFTER the user
        # row is persisted (preserves audit-trail invariant) but BEFORE
        # memory-bounds evaluation and model invocation.
        try:
            validate_input(user_message)
        except ChatInputBlockedError as exc:
            user_row.guardrail_action = "blocked"
            user_row.redaction_flags = {
                "filter_source": "input_validator",
                "reason": exc.reason,
                "pattern_id": exc.pattern_id,
            }
            db.add(user_row)
            await db.commit()
            logger.info(
                "chat.input.blocked",
                extra={
                    "correlation_id": correlation_id,
                    "db_session_id": str(handle.db_session_id),
                    "reason": exc.reason,
                    "pattern_id": exc.pattern_id,
                    "input_char_len": len(user_message),
                    "input_prefix_hash": _prefix_hash(user_message),
                },
            )
            raise

        # Step 2 — load canaries + render the hardened system prompt. A
        # CanaryLoadError hard-fails the turn (non-recoverable — chat cannot
        # safely invoke a model without its leak detector primed).
        try:
            canaries = await get_canary_set()
        except CanaryLoadError as exc:
            logger.error(
                "chat.canary.load_failed",
                extra={
                    "correlation_id": correlation_id,
                    "db_session_id": str(handle.db_session_id),
                    "error_class": type(exc).__name__,
                    "error_message": str(exc)[:200],
                },
            )
            raise ChatConfigurationError(
                f"Chat canary load failed: {type(exc).__name__}"
            ) from exc
        rendered = render_system_prompt(canaries)

        # Step 3 — apply memory bounds (unchanged from 10.4a).
        # NOTE on consent drift: consent is verified at create_session only.
        # Stream-level cancellation is Story 10.5's SSE concern.
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

        # Step 4 — invoke backend with hardened system prompt + tool context.
        context_messages = history[:-1]
        try:
            result = await self._backend.invoke(
                db_session_id=handle.db_session_id,
                context_messages=context_messages,
                user_message=user_message,
                system_prompt=rendered.text,
                user_id=handle.user_id,
                db=db,
            )
        except (
            ChatToolLoopExceededError,
            ChatToolNotAllowedError,
            ChatToolAuthorizationError,
        ) as exc:
            # Step 4.5 — tool-loop hard failure. Persist the forensic tool
            # rows that DID execute (they carry value — the loop got stuck
            # somewhere concrete), bump last_active_at, emit the right
            # observability event, and re-raise for 10.5's SSE translator
            # to convert into CHAT_REFUSED(reason=tool_blocked).
            partial_calls = getattr(exc, "tool_calls_so_far", ()) or ()
            for tc in partial_calls:
                db.add(
                    ChatMessage(
                        session_id=handle.db_session_id,
                        role="tool",
                        content=_serialize_tool_call(tc),
                        guardrail_action="none" if tc.ok else "blocked",
                        redaction_flags={
                            "filter_source": "tool_dispatcher",
                            "tool_name": tc.tool_name,
                            "error_kind": tc.error_kind,
                        },
                    )
                )
            await db.exec(
                sa_update(ChatSession)
                .where(ChatSession.id == handle.db_session_id)
                .values(last_active_at=_now())
            )
            await db.commit()
            if isinstance(exc, ChatToolLoopExceededError):
                logger.error(
                    "chat.tool.loop_exceeded",
                    extra={
                        "correlation_id": correlation_id,
                        "db_session_id": str(handle.db_session_id),
                        "hops": exc.hops,
                        "last_tool_name": exc.last_tool_name,
                    },
                )
            elif isinstance(exc, ChatToolAuthorizationError):
                # The dispatcher already logged chat.tool.authorization_failed
                # with the per-tool detail. We add a session-level breadcrumb
                # so the handler slice of the pipeline shows the refusal.
                logger.error(
                    "chat.turn.aborted_authorization",
                    extra={
                        "correlation_id": correlation_id,
                        "db_session_id": str(handle.db_session_id),
                        "tool_name": exc.tool_name,
                    },
                )
            else:  # ChatToolNotAllowedError at the loop-level guard
                logger.error(
                    "chat.turn.aborted_tool_not_allowed",
                    extra={
                        "correlation_id": correlation_id,
                        "db_session_id": str(handle.db_session_id),
                        "tool_name": exc.tool_name,
                    },
                )
            raise
        except Exception:
            # Backend already translated to ChatConfigurationError / ChatTransientError.
            raise

        # Step 5 — canary scan on model output (Story 10.4b AC #3). Runs
        # BEFORE persisting the assistant row so a leaked-canary response
        # is stored explicitly as blocked, never silently as a normal turn.
        try:
            scan_for_canaries(result.text, canaries)
        except ChatPromptLeakDetectedError as exc:
            assistant_row = ChatMessage(
                session_id=handle.db_session_id,
                role="assistant",
                content=result.text,
                guardrail_action="blocked",
                redaction_flags={
                    "filter_source": "canary_detector",
                    "canary_slot": exc._matched_position_slot,
                    "canary_prefix": exc.matched_canary_prefix,
                },
            )
            db.add(assistant_row)
            await db.exec(
                sa_update(ChatSession)
                .where(ChatSession.id == handle.db_session_id)
                .values(last_active_at=_now())
            )
            await db.commit()
            logger.error(
                "chat.canary.leaked",
                extra={
                    "correlation_id": correlation_id,
                    "db_session_id": str(handle.db_session_id),
                    "canary_slot": exc._matched_position_slot,
                    "canary_prefix": exc.matched_canary_prefix,
                    "canary_set_version_id": canaries.version_id,
                    "output_char_len": len(result.text),
                    "output_prefix_hash": _prefix_hash(result.text),
                },
            )
            raise

        # Step 6 — persist tool rows + assistant turn atomically.
        # Tool rows come BEFORE the assistant row (by insertion order and
        # by created_at because the assistant row is added last in the txn).
        # Story 10.6b's citation assembler reads these rows later.
        for tc in result.tool_calls:
            db.add(
                ChatMessage(
                    session_id=handle.db_session_id,
                    role="tool",
                    content=_serialize_tool_call(tc),
                    guardrail_action="none" if tc.ok else "blocked",
                    redaction_flags={
                        "filter_source": "tool_dispatcher",
                        "tool_name": tc.tool_name,
                        "error_kind": tc.error_kind,
                    },
                )
            )
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

        # tool_hop_count: a single AIMessage iteration may emit multiple
        # tool_use blocks that we dispatch in series, collapsing to one hop.
        # Approximate hop count as the number of tool-groupings; for the
        # current series-execution loop each invocation == one hop, so we
        # count unique ``elapsed_ms + tool_use_id`` groupings. Simpler proxy:
        # report tool_call_count for both, and let Story 10.9 split if needed.
        tool_call_count = len(result.tool_calls)
        tool_hop_count = tool_call_count
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
                "system_prompt_version": CHAT_SYSTEM_PROMPT_VERSION,
                "input_validator_version": INPUT_VALIDATOR_VERSION,
                "canary_set_version_id": canaries.version_id,
                "tool_manifest_version": CHAT_TOOL_MANIFEST_VERSION,
                "tool_call_count": tool_call_count,
                "tool_hop_count": tool_hop_count,
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
    # send_turn_stream — Story 10.5 AC #2
    # ------------------------------------------------------------------
    #
    # Handler invariants (AC #14):
    #   (1) streaming variant is transport-only; the six-step pipeline is
    #       identical to ``send_turn`` — Step 0 user-row persist, Step 1
    #       input validation, Step 2 canary + system-prompt load, Step 3
    #       memory-bounds / summarization, Step 4 backend.invoke_stream
    #       (final-iteration astream only), Step 5 canary scan on
    #       ACCUMULATED final text, Step 6 assistant row + last_active_at.
    #   (2) the canary scan runs on the accumulated final text, NOT
    #       per-delta — canaries may be split across token chunks and the
    #       per-delta scan would be both lossy and redundant.
    #   (3) persistence invariants match ``send_turn`` exactly — same rows
    #       end up in chat_messages whether the caller used send_turn or
    #       send_turn_stream; guardrail_action='blocked' rows still land on
    #       the refusal paths.
    #   (4) a client disconnect does NOT skip persistence — Steps 4–6 are
    #       wrapped in an outer try/finally with a _finalized gate. The four
    #       terminal branches (happy-path, canary-leak, tool-abort, guardrail-
    #       intervention) each flip _finalized=True before raising; the finally
    #       runs the late-write path (canary re-scan + assistant row + tool
    #       rows + last_active_at bump) only when _finalized is False. This
    #       handles GeneratorExit (client disconnect via agen.aclose()),
    #       asyncio.CancelledError (server shutdown), and any unanticipated
    #       exception. The finalizer is best-effort (its own try/except
    #       Exception → chat.stream.finalizer_failed log) and never masks
    #       the original exception. See Story 10.5a (TD-108 + TD-109 short-
    #       term resolution).
    #   (5) the canary scan ALSO runs from the outer finally on the
    #       GeneratorExit / ChatGuardrailInterventionError(non-empty
    #       accumulated_text) / ChatTransientError paths, emitting
    #       chat.canary.leaked ERROR with finalizer_path=True. This is the
    #       audit-layer safety net for canaries that slip past the happy-
    #       path Step 5 scan due to mid-stream short-circuits. The wire-gate
    #       (rolling-window matcher) remains TD-109 medium-term.

    async def send_turn_stream(
        self,
        db: SQLModelAsyncSession,
        handle: ChatSessionHandle,
        user_message: str,
        *,
        correlation_id: str,
        guardrail_id: str | None = None,
        guardrail_version: str | None = None,
    ) -> AsyncIterator[ChatStreamEvent]:
        """Stream-capable variant of ``send_turn``. Story 10.5 AC #2.

        Yields ``ChatStreamStarted`` first, then zero-or-more tool-hop events
        and token deltas, then a terminal ``ChatStreamCompleted``. Typed
        exceptions raise IDENTICALLY to ``send_turn``; the API layer catches
        them at the route boundary for ``CHAT_REFUSED`` translation.
        """
        history = await self._load_history(db, handle.db_session_id)

        # Step 0 — persist user row (own txn for audit-trail invariant).
        user_row = ChatMessage(
            session_id=handle.db_session_id, role="user", content=user_message
        )
        db.add(user_row)
        await db.commit()
        history.append(user_row)

        # Step 1 — input validator.
        try:
            validate_input(user_message)
        except ChatInputBlockedError as exc:
            user_row.guardrail_action = "blocked"
            user_row.redaction_flags = {
                "filter_source": "input_validator",
                "reason": exc.reason,
                "pattern_id": exc.pattern_id,
            }
            db.add(user_row)
            await db.commit()
            logger.info(
                "chat.input.blocked",
                extra={
                    "correlation_id": correlation_id,
                    "db_session_id": str(handle.db_session_id),
                    "reason": exc.reason,
                    "pattern_id": exc.pattern_id,
                    "input_char_len": len(user_message),
                    "input_prefix_hash": _prefix_hash(user_message),
                },
            )
            raise

        # Step 2 — canary + hardened system prompt.
        try:
            canaries = await get_canary_set()
        except CanaryLoadError as exc:
            logger.error(
                "chat.canary.load_failed",
                extra={
                    "correlation_id": correlation_id,
                    "db_session_id": str(handle.db_session_id),
                    "error_class": type(exc).__name__,
                    "error_message": str(exc)[:200],
                },
            )
            raise ChatConfigurationError(
                f"Chat canary load failed: {type(exc).__name__}"
            ) from exc
        rendered = render_system_prompt(canaries)

        # Step 3 — memory bounds.
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

        # Opening event — the API layer emits chat-open AFTER this first yield.
        yield ChatStreamStarted(
            correlation_id=correlation_id, session_id=handle.db_session_id
        )

        # Step 4 — backend.invoke_stream. Tool-loop hops resolve non-stream;
        # the final plain-text iteration streams token-by-token.
        context_messages = history[:-1]
        accumulated_text = ""
        completed: BackendStreamDone | None = None
        tool_results: list = []
        _finalized = False
        try:
            try:
                async for backend_event in self._backend.invoke_stream(
                    db_session_id=handle.db_session_id,
                    context_messages=context_messages,
                    user_message=user_message,
                    system_prompt=rendered.text,
                    user_id=handle.user_id,
                    db=db,
                    guardrail_id=guardrail_id,
                    guardrail_version=guardrail_version,
                ):
                    if isinstance(backend_event, BackendToolHop):
                        yield ChatToolHopStarted(
                            tool_name=backend_event.tool_name,
                            hop_index=backend_event.hop_index,
                        )
                        yield ChatToolHopCompleted(
                            tool_name=backend_event.tool_name,
                            hop_index=backend_event.hop_index,
                            ok=backend_event.ok,
                        )
                        tool_results.append(backend_event.result)
                    elif isinstance(backend_event, BackendTokenDelta):
                        accumulated_text += backend_event.text
                        yield ChatTokenDelta(text=backend_event.text)
                    elif isinstance(backend_event, BackendStreamDone):
                        completed = backend_event
            except (
                ChatToolLoopExceededError,
                ChatToolNotAllowedError,
                ChatToolAuthorizationError,
            ) as exc:
                # Persist whatever tool rows executed before the loop aborted,
                # bump last_active_at, surface the existing per-reason ERROR
                # log (mirrors send_turn's Step 4.5).
                partial_calls = getattr(exc, "tool_calls_so_far", ()) or tuple(
                    tool_results
                )
                for tc in partial_calls:
                    db.add(
                        ChatMessage(
                            session_id=handle.db_session_id,
                            role="tool",
                            content=_serialize_tool_call(tc),
                            guardrail_action="none" if tc.ok else "blocked",
                            redaction_flags={
                                "filter_source": "tool_dispatcher",
                                "tool_name": tc.tool_name,
                                "error_kind": tc.error_kind,
                            },
                        )
                    )
                await db.exec(
                    sa_update(ChatSession)
                    .where(ChatSession.id == handle.db_session_id)
                    .values(last_active_at=_now())
                )
                await db.commit()
                _finalized = True
                if isinstance(exc, ChatToolLoopExceededError):
                    logger.error(
                        "chat.tool.loop_exceeded",
                        extra={
                            "correlation_id": correlation_id,
                            "db_session_id": str(handle.db_session_id),
                            "hops": exc.hops,
                            "last_tool_name": exc.last_tool_name,
                        },
                    )
                elif isinstance(exc, ChatToolAuthorizationError):
                    logger.error(
                        "chat.turn.aborted_authorization",
                        extra={
                            "correlation_id": correlation_id,
                            "db_session_id": str(handle.db_session_id),
                            "tool_name": exc.tool_name,
                        },
                    )
                else:
                    logger.error(
                        "chat.turn.aborted_tool_not_allowed",
                        extra={
                            "correlation_id": correlation_id,
                            "db_session_id": str(handle.db_session_id),
                            "tool_name": exc.tool_name,
                        },
                    )
                raise
            except ChatGuardrailInterventionError as exc:
                # AC #3: with non-empty accumulated_text, defer persistence
                # to the finalizer (canary re-scan + assistant row); with
                # empty accumulated_text, this branch owns persistence.
                if not accumulated_text:
                    for tc in tool_results:
                        db.add(
                            ChatMessage(
                                session_id=handle.db_session_id,
                                role="tool",
                                content=_serialize_tool_call(tc),
                                guardrail_action="none" if tc.ok else "blocked",
                                redaction_flags={
                                    "filter_source": "tool_dispatcher",
                                    "tool_name": tc.tool_name,
                                    "error_kind": tc.error_kind,
                                },
                            )
                        )
                    await db.exec(
                        sa_update(ChatSession)
                        .where(ChatSession.id == handle.db_session_id)
                        .values(last_active_at=_now())
                    )
                    await db.commit()
                    _finalized = True
                # Re-raise with correlation_id stamped (frozen-exception-safe:
                # the attribute is a plain instance attribute on Exception).
                exc.correlation_id = correlation_id
                logger.info(
                    "chat.stream.guardrail_intervened",
                    extra={
                        "correlation_id": correlation_id,
                        "db_session_id": str(handle.db_session_id),
                        "intervention_kind": exc.intervention_kind,
                    },
                )
                raise

            # Step 5 — canary scan on accumulated final text (NOT per-delta).
            try:
                scan_for_canaries(accumulated_text, canaries)
            except ChatPromptLeakDetectedError as exc:
                assistant_row = ChatMessage(
                    session_id=handle.db_session_id,
                    role="assistant",
                    content=accumulated_text,
                    guardrail_action="blocked",
                    redaction_flags={
                        "filter_source": "canary_detector",
                        "canary_slot": exc._matched_position_slot,
                        "canary_prefix": exc.matched_canary_prefix,
                    },
                )
                db.add(assistant_row)
                await db.exec(
                    sa_update(ChatSession)
                    .where(ChatSession.id == handle.db_session_id)
                    .values(last_active_at=_now())
                )
                await db.commit()
                _finalized = True
                logger.error(
                    "chat.canary.leaked",
                    extra={
                        "correlation_id": correlation_id,
                        "db_session_id": str(handle.db_session_id),
                        "canary_slot": exc._matched_position_slot,
                        "canary_prefix": exc.matched_canary_prefix,
                        "canary_set_version_id": canaries.version_id,
                        "output_char_len": len(accumulated_text),
                        "output_prefix_hash": _prefix_hash(accumulated_text),
                    },
                )
                raise

            # Step 6 — persist tool rows + assistant row atomically.
            for tc in tool_results:
                db.add(
                    ChatMessage(
                        session_id=handle.db_session_id,
                        role="tool",
                        content=_serialize_tool_call(tc),
                        guardrail_action="none" if tc.ok else "blocked",
                        redaction_flags={
                            "filter_source": "tool_dispatcher",
                            "tool_name": tc.tool_name,
                            "error_kind": tc.error_kind,
                        },
                    )
                )
            assistant_row = ChatMessage(
                session_id=handle.db_session_id,
                role="assistant",
                content=accumulated_text,
            )
            db.add(assistant_row)
            await db.exec(
                sa_update(ChatSession)
                .where(ChatSession.id == handle.db_session_id)
                .values(last_active_at=_now())
            )
            await db.commit()
            _finalized = True

            tool_call_count = len(tool_results)
            input_tokens = completed.input_tokens if completed else 0
            output_tokens = completed.output_tokens if completed else 0
            token_source = completed.token_source if completed else "model"
            logger.info(
                "chat.turn.completed",
                extra={
                    "correlation_id": correlation_id,
                    "db_session_id": str(handle.db_session_id),
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "session_turn_count": count_turns(history),
                    "summarization_applied": summarization_applied,
                    "token_source": token_source,
                    "system_prompt_version": CHAT_SYSTEM_PROMPT_VERSION,
                    "input_validator_version": INPUT_VALIDATOR_VERSION,
                    "canary_set_version_id": canaries.version_id,
                    "tool_manifest_version": CHAT_TOOL_MANIFEST_VERSION,
                    "tool_call_count": tool_call_count,
                    "tool_hop_count": tool_call_count,
                    "streaming": True,
                },
            )
            yield ChatStreamCompleted(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                session_turn_count=count_turns(history),
                summarization_applied=summarization_applied,
                token_source=token_source,
                tool_call_count=tool_call_count,
            )
        finally:
            # Late-write finalizer — best-effort; must not mask the original
            # cause (so we catch Exception, NOT BaseException — GeneratorExit
            # / CancelledError / KeyboardInterrupt / SystemExit propagate).
            if not _finalized:
                try:
                    canary_leak_exc: ChatPromptLeakDetectedError | None = None
                    if accumulated_text:
                        try:
                            scan_for_canaries(accumulated_text, canaries)
                        except ChatPromptLeakDetectedError as exc_canary:
                            canary_leak_exc = exc_canary

                    # F.3 first, then F.1/F.2 — tool rows precede assistant row
                    # to match happy-path ordering (Step 6 persists tools then
                    # assistant), preserving AC #14 invariant 3.
                    for tc in tool_results:
                        db.add(
                            ChatMessage(
                                session_id=handle.db_session_id,
                                role="tool",
                                content=_serialize_tool_call(tc),
                                guardrail_action="none" if tc.ok else "blocked",
                                redaction_flags={
                                    "filter_source": "tool_dispatcher",
                                    "tool_name": tc.tool_name,
                                    "error_kind": tc.error_kind,
                                },
                            )
                        )

                    if canary_leak_exc is not None:
                        db.add(
                            ChatMessage(
                                session_id=handle.db_session_id,
                                role="assistant",
                                content=accumulated_text,
                                guardrail_action="blocked",
                                redaction_flags={
                                    "filter_source": "canary_detector",
                                    "canary_slot": canary_leak_exc._matched_position_slot,
                                    "canary_prefix": canary_leak_exc.matched_canary_prefix,
                                },
                            )
                        )
                    elif accumulated_text:
                        db.add(
                            ChatMessage(
                                session_id=handle.db_session_id,
                                role="assistant",
                                content=accumulated_text,
                            )
                        )

                    await db.exec(
                        sa_update(ChatSession)
                        .where(ChatSession.id == handle.db_session_id)
                        .values(last_active_at=_now())
                    )
                    await db.commit()

                    if canary_leak_exc is not None:
                        logger.error(
                            "chat.canary.leaked",
                            extra={
                                "correlation_id": correlation_id,
                                "db_session_id": str(handle.db_session_id),
                                "canary_slot": canary_leak_exc._matched_position_slot,
                                "canary_prefix": canary_leak_exc.matched_canary_prefix,
                                "canary_set_version_id": canaries.version_id,
                                "output_char_len": len(accumulated_text),
                                "output_prefix_hash": _prefix_hash(accumulated_text),
                                "finalizer_path": True,
                            },
                        )
                    _finalized = True
                except Exception as exc_finalizer:  # noqa: BLE001
                    logger.error(
                        "chat.stream.finalizer_failed",
                        extra={
                            "correlation_id": correlation_id,
                            "db_session_id": str(handle.db_session_id),
                            "error_class": type(exc_finalizer).__name__,
                            "error_message": str(exc_finalizer)[:200],
                            "accumulated_char_len": len(accumulated_text),
                            "tool_results_count": len(tool_results),
                        },
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
