"""Chat-backend abstraction — Phase A direct-Bedrock + Phase B AgentCore seam.

Story 10.4a (ADR-0004). The handler in ``session_handler.py`` speaks only to
the ``ChatBackend`` interface; the concrete implementation is chosen by
``settings.CHAT_RUNTIME`` at ``get_chat_session_handler()`` time. Phase A
ships ``DirectBedrockBackend``; Phase B (story ``10.4a-runtime``) adds
``AgentCoreBackend`` alongside without touching the handler.

Story 10.4c adds the tool-use loop inside ``DirectBedrockBackend.invoke``:
- Allowlist enforced at the dispatcher (see ``app.agents.chat.tools``).
- Series execution (not ``asyncio.gather``) preserves DB-transaction safety
  against a single ``AsyncSession`` shared across tool calls.
- ``MAX_TOOL_HOPS`` is the loop bound — a cap breach is an operator-grade
  "probably adversarial" signal, not a retry candidate.
- Schema errors are SOFT (re-entered into the model via a ``ToolMessage`` so
  the model can correct itself); authorization errors are HARD (bubble up to
  the handler, turn is aborted, Story 10.5 translates to ``CHAT_REFUSED``).

Exception translation lives here so the handler's try/except blocks stay
backend-agnostic. Both backends raise the same exception types for the same
categories of failure.
"""

from __future__ import annotations

import abc
import json
import logging
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

from app.core.config import settings

logger = logging.getLogger(__name__)

MAX_TOOL_HOPS: int = 5
"""Hard cap on tool-use iterations per turn.

Rationale: a well-formed single-turn chat resolves in <= 2 tool hops (one
data tool + possibly one RAG tool). 5 leaves headroom for a model that
self-corrects after a schema error. Beyond 5, we are in a loop — probably
stuck or adversarially driven. Not env-overridable (operational invariant).
"""


class ChatProviderNotSupportedError(Exception):
    """Raised when chat is invoked outside a Bedrock deployment."""


class ChatConfigurationError(Exception):
    """Non-retryable — IAM or ARN wiring problem. Log, do not retry."""


class ChatTransientError(Exception):
    """Retryable — Bedrock throttle / transient service unavailable."""


class ChatSessionCreationError(Exception):
    """Raised when backend session creation fails after DB row insert."""


class ChatSessionTerminationFailed(Exception):
    """Raised when backend session termination fails."""


class ChatGuardrailInterventionError(Exception):
    """Raised by ``invoke_stream`` when Bedrock Guardrails intervened in the
    streamed response. Story 10.5 AC #7.

    ``intervention_kind`` is one of ``"content_filter" | "denied_topic" |
    "pii" | "word_filter" | "grounding"`` — derived from the final-chunk
    ``trace.guardrail`` shape the pinned langchain-aws version surfaces.
    The envelope translator in ``app/api/v1/chat.py`` maps
    ``grounding`` → ``reason=ungrounded`` and the rest →
    ``reason=guardrail_blocked``.

    ``trace_summary`` is truncated to 200 chars for logging; never surfaces
    to the user. ``correlation_id`` is stamped by the handler before re-raise.
    """

    def __init__(
        self,
        *,
        intervention_kind: str,
        trace_summary: str = "",
        correlation_id: str | None = None,
    ) -> None:
        self.intervention_kind = intervention_kind
        self.trace_summary = (trace_summary or "")[:200]
        self.correlation_id = correlation_id
        super().__init__(
            f"Bedrock Guardrail intervened (kind={intervention_kind})"
        )


@dataclass(frozen=True)
class BackendTokenDelta:
    """Backend-boundary streaming event — final-iteration token chunk.

    Story 10.5 AC #7. The handler repackages these into
    ``ChatTokenDelta`` events for the API layer. Empty-text chunks from
    the underlying stream are filtered BEFORE yielding.
    """

    text: str


@dataclass(frozen=True)
class BackendToolHop:
    """Backend-boundary streaming event — one tool hop completed.

    Emitted by ``invoke_stream`` after each non-final iteration's
    dispatcher returns. Carries enough for the handler to emit
    ``ChatToolHopStarted``/``ChatToolHopCompleted`` events and to persist
    ``role='tool'`` rows identically to the non-streaming path.
    """

    tool_name: str
    hop_index: int  # 1-based
    ok: bool
    result: Any  # ToolResult — kept loosely typed to avoid cyclic import


@dataclass(frozen=True)
class BackendStreamDone:
    """Terminal backend-boundary event on a successful stream.

    Carries the same cumulative token accounting the non-streaming
    ``ChatInvocationResult`` does — the handler uses it to stamp
    ``ChatStreamCompleted``.
    """

    input_tokens: int
    output_tokens: int
    token_source: str  # "model" | "tiktoken"
    tool_calls: tuple  # tuple[ToolResult, ...]


ChatBackendStreamEvent = BackendTokenDelta | BackendToolHop | BackendStreamDone


@dataclass(frozen=True)
class ChatInvocationResult:
    """Return payload from ``ChatBackend.invoke``.

    ``token_source`` is ``"model"`` when the Bedrock response carried usage
    metadata on every iteration; ``"tiktoken"`` if any iteration fell back
    to the local estimator (once the fallback fires for any hop, the whole
    turn is reported as tiktoken-sourced).

    ``tool_calls`` is the ordered sequence of ``ToolResult`` instances
    executed during this turn (Story 10.4c). Empty tuple when the model
    answered without tools. The handler persists these as ``role='tool'``
    rows; Story 10.6b reads them for citation assembly.
    """

    text: str
    input_tokens: int
    output_tokens: int
    token_source: str  # "model" | "tiktoken"
    tool_calls: tuple = field(default_factory=tuple)  # tuple[ToolResult, ...]


def _bedrock_only_guard() -> None:
    """Raise ``ChatProviderNotSupportedError`` unless LLM_PROVIDER=bedrock."""
    if settings.LLM_PROVIDER != "bedrock":
        if settings.CHAT_RUNTIME == "agentcore":
            detail = (
                "Phase B requires LLM_PROVIDER=bedrock and AGENTCORE_RUNTIME_ARN set."
            )
            extras = (
                f" Current provider: {settings.LLM_PROVIDER}; "
                f"runtime configured: {bool(settings.AGENTCORE_RUNTIME_ARN)}."
            )
        else:
            detail = "Chat requires LLM_PROVIDER=bedrock."
            extras = f" Current provider: {settings.LLM_PROVIDER}."
        raise ChatProviderNotSupportedError(detail + extras)


class ChatBackend(abc.ABC):
    """Backend seam between ``ChatSessionHandler`` and the model fabric."""

    @abc.abstractmethod
    async def create_remote_session(self, db_session_id: uuid.UUID) -> str: ...

    @abc.abstractmethod
    async def invoke(
        self,
        *,
        db_session_id: uuid.UUID,
        context_messages: list[Any],
        user_message: str,
        system_prompt: str,
        user_id: uuid.UUID,
        db: Any,
    ) -> ChatInvocationResult: ...

    @abc.abstractmethod
    async def terminate_remote_session(self, agentcore_session_id: str) -> None: ...

    async def invoke_stream(
        self,
        *,
        db_session_id: uuid.UUID,
        context_messages: list[Any],
        user_message: str,
        system_prompt: str,
        user_id: uuid.UUID,
        db: Any,
        guardrail_id: str | None = None,
        guardrail_version: str | None = None,
    ) -> AsyncIterator[ChatBackendStreamEvent]:
        """Streaming variant of ``invoke``. Story 10.5 AC #7.

        Default implementation raises ``NotImplementedError`` so a Phase B
        ``AgentCoreBackend`` (story 10.4a-runtime) can selectively opt in
        when its streaming contract lands. ``DirectBedrockBackend`` overrides.
        """
        raise NotImplementedError(
            f"{type(self).__name__} does not implement invoke_stream"
        )
        # Unreachable — keeps the type-checker happy with the AsyncIterator signature.
        yield  # type: ignore[unreachable]


def _lc_tools_from_manifest() -> list:
    """Build the langchain-shape tool list from the manifest.

    Uses ``StructuredTool`` with an explicit name so the model sees
    ``get_transactions`` (not ``GetTransactionsInput``). The ``func`` is
    a no-op because we handle dispatch out-of-band in the invoke loop.
    """
    from langchain_core.tools import StructuredTool

    from app.agents.chat.tools import TOOL_MANIFEST

    def _noop(**_kwargs: Any) -> str:
        # Unreachable at runtime — we dispatch manually and never let
        # langchain's own tool-execution path run.
        return ""

    return [
        StructuredTool(
            name=spec.name,
            description=spec.description,
            args_schema=spec.input_model,
            func=_noop,
        )
        for spec in TOOL_MANIFEST
    ]


def _extract_tool_uses(response: Any) -> list:
    """Return a list of (id, name, input_dict) from a langchain AIMessage-like response.

    Prefers ``response.tool_calls`` (newer langchain shape); falls back to
    scanning ``response.content`` for ``tool_use`` blocks. Returns an empty
    list when the response is plain text.
    """
    # Preferred path — langchain ``tool_calls`` attribute.
    tool_calls = getattr(response, "tool_calls", None)
    if tool_calls:
        out = []
        for tc in tool_calls:
            if isinstance(tc, dict):
                name = tc.get("name") or ""
                args = tc.get("args") or tc.get("arguments") or {}
                tid = tc.get("id") or ""
            else:
                name = getattr(tc, "name", "") or ""
                args = getattr(tc, "args", None) or getattr(tc, "arguments", None) or {}
                tid = getattr(tc, "id", "") or ""
            if name:
                out.append(_ToolUseRef(id=str(tid), name=str(name), input=dict(args)))
        if out:
            return out

    # Fallback — scan content blocks.
    content = getattr(response, "content", None)
    if isinstance(content, list):
        out = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "tool_use":
                out.append(
                    _ToolUseRef(
                        id=str(block.get("id", "")),
                        name=str(block.get("name", "")),
                        input=dict(block.get("input") or {}),
                    )
                )
        return out
    return []


@dataclass(frozen=True)
class _ToolUseRef:
    id: str
    name: str
    input: dict


def _final_text(response: Any) -> str:
    """Extract the plain-text final answer from an AIMessage-like response.

    Concatenates every ``text``-type content block, ignoring any lingering
    ``tool_use`` blocks (those only appear on non-final iterations).
    """
    content = getattr(response, "content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict):
                t = block.get("type")
                if t == "text":
                    parts.append(str(block.get("text", "")))
                # Deliberately skip tool_use blocks on the final iteration
                # — if the model emitted both text + tool_use we want the
                # text (and the tool_use would have been dispatched earlier).
            else:
                parts.append(str(block))
        return "".join(parts)
    return str(content)


class DirectBedrockBackend(ChatBackend):
    """Phase A backend — direct ``bedrock-runtime:InvokeModel`` via ``llm.py``.

    Uses the ``chat_default`` models.yaml role (Sonnet inference profile)
    for the conversational turn. Summarization (owned by the handler, not
    this class) uses ``agent_default`` (Haiku) via ``get_llm_client()``.
    """

    def __init__(self) -> None:
        _bedrock_only_guard()

    async def create_remote_session(self, db_session_id: uuid.UUID) -> str:
        return str(db_session_id)

    async def invoke(
        self,
        *,
        db_session_id: uuid.UUID,
        context_messages: list[Any],
        user_message: str,
        system_prompt: str,
        user_id: uuid.UUID,
        db: Any,
    ) -> ChatInvocationResult:
        # Tool-loop invariants (10.4c):
        #   (1) allowlist enforced at dispatcher — unknown tool names round-trip
        #       to the model as a soft ToolResult, never as a silent no-op;
        #   (2) series execution preserves DB-transaction safety against the
        #       single AsyncSession shared across handlers;
        #   (3) MAX_TOOL_HOPS is the only loop bound — cap breach raises
        #       ChatToolLoopExceededError (hard);
        #   (4) schema errors are soft (re-entered into the model);
        #       authorization errors are hard (bubble up, turn aborted).
        from botocore.exceptions import ClientError
        from langchain_core.messages import (
            AIMessage,
            HumanMessage,
            SystemMessage,
            ToolMessage,
        )

        from app.agents.chat.memory_bounds import estimate_tokens
        from app.agents.chat.tools.dispatcher import ToolInvocation, dispatch_tool
        from app.agents.chat.tools.tool_errors import ChatToolLoopExceededError
        from app.agents.llm import _get_client_for, record_failure, record_success
        from app.models.chat_message import ChatMessage

        # Hardened system prompt pinned at position [0]. History-derived
        # system rows (summaries) come AFTER as auxiliary context.
        lc_messages: list[Any] = [SystemMessage(content=system_prompt)]
        for m in context_messages:
            if m.role == "user":
                lc_messages.append(HumanMessage(content=m.content))
            elif m.role == "assistant":
                lc_messages.append(AIMessage(content=m.content))
            elif m.role == "system":
                lc_messages.append(SystemMessage(content=m.content))
            # role='tool' rows from prior turns are not replayed — the model
            # has the assistant summary of any prior tool outputs; re-feeding
            # raw tool payloads would bloat context for no win.
        lc_messages.append(HumanMessage(content=user_message))

        base_client = _get_client_for("bedrock", role="chat_default")
        try:
            bound_client = base_client.bind_tools(_lc_tools_from_manifest())
        except Exception as exc:  # noqa: BLE001
            # Fail-closed: if the pinned langchain version cannot bind the
            # manifest, the only remaining path would be "invoke the model
            # with no tool schema" — which silently reverts the defense
            # layer-4 allowlist to "model answers from priors". That's the
            # exact failure mode the allowlist exists to prevent. Raise a
            # ChatConfigurationError so the handler surfaces a hard refusal.
            import logging as _logging

            _logging.getLogger(__name__).error(
                "chat.tool.bind_failed",
                extra={
                    "db_session_id": str(db_session_id),
                    "error_class": type(exc).__name__,
                    "error_message": str(exc)[:200],
                },
            )
            raise ChatConfigurationError(
                f"Chat tool manifest bind failed: {type(exc).__name__}"
            ) from exc

        hops = 0
        cumul_input = 0
        cumul_output = 0
        token_source = "model"
        tool_calls: list = []  # list[ToolResult]
        final_text = ""
        last_tool_name: str | None = None

        while True:
            try:
                response = await bound_client.ainvoke(lc_messages)
            except ClientError as exc:
                code = exc.response.get("Error", {}).get("Code", "")
                record_failure("bedrock")
                if code == "AccessDeniedException":
                    raise ChatConfigurationError(
                        f"Bedrock AccessDenied on chat invocation (session "
                        f"{db_session_id}): {code}"
                    ) from exc
                if code in ("ThrottlingException", "ServiceUnavailableException"):
                    raise ChatTransientError(
                        f"Bedrock transient error on chat invocation "
                        f"(session {db_session_id}): {code}"
                    ) from exc
                raise
            except Exception:
                record_failure("bedrock")
                raise

            # Per-iteration token accounting. A single tiktoken fallback
            # on any hop marks the whole turn as tiktoken-sourced.
            usage = getattr(response, "usage_metadata", None) or {}
            in_tokens = usage.get("input_tokens")
            out_tokens = usage.get("output_tokens")
            if in_tokens is None or out_tokens is None:
                in_tokens = estimate_tokens(
                    [
                        ChatMessage(
                            session_id=db_session_id, role="user", content=_stringify(m)
                        )
                        for m in lc_messages
                    ]
                )
                out_tokens = estimate_tokens(
                    [
                        ChatMessage(
                            session_id=db_session_id,
                            role="assistant",
                            content=_stringify(response),
                        )
                    ]
                )
                token_source = "tiktoken"
            cumul_input += int(in_tokens)
            cumul_output += int(out_tokens)

            tool_uses = _extract_tool_uses(response)
            if not tool_uses:
                final_text = _final_text(response)
                break

            hops += 1
            last_tool_name = tool_uses[-1].name if tool_uses else last_tool_name
            if hops > MAX_TOOL_HOPS:
                err = ChatToolLoopExceededError(
                    hops=hops, last_tool_name=last_tool_name
                )
                err.tool_calls_so_far = tuple(tool_calls)
                raise err

            iter_results = []
            for tu in tool_uses:
                inv = ToolInvocation(
                    tool_name=tu.name, raw_input=tu.input, tool_use_id=tu.id
                )
                # Series execution (not gather) — a shared AsyncSession is
                # not safe for concurrent handler calls.
                try:
                    res = await dispatch_tool(
                        inv,
                        user_id=user_id,
                        db=db,
                        db_session_id=db_session_id,
                    )
                except Exception as exc:
                    # Attach partial forensic state so the handler can still
                    # persist role='tool' rows for what DID execute before
                    # the hard error.
                    if hasattr(exc, "tool_calls_so_far"):
                        exc.tool_calls_so_far = tuple(tool_calls)
                    raise
                iter_results.append(res)
                tool_calls.append(res)

            # Append the assistant AIMessage that requested the tools, then
            # one ToolMessage per result. The AIMessage carries the tool_use
            # blocks the Converse API correlates against tool_call_id.
            lc_messages.append(response)
            for r in iter_results:
                lc_messages.append(
                    ToolMessage(
                        content=json.dumps(r.payload, default=str),
                        tool_call_id=r.tool_use_id,
                    )
                )

        record_success("bedrock")
        return ChatInvocationResult(
            text=final_text,
            input_tokens=cumul_input,
            output_tokens=cumul_output,
            token_source=token_source,
            tool_calls=tuple(tool_calls),
        )

    async def invoke_stream(
        self,
        *,
        db_session_id: uuid.UUID,
        context_messages: list[Any],
        user_message: str,
        system_prompt: str,
        user_id: uuid.UUID,
        db: Any,
        guardrail_id: str | None = None,
        guardrail_version: str | None = None,
    ) -> AsyncIterator[ChatBackendStreamEvent]:
        """Streaming variant of ``invoke``. Story 10.5 AC #7.

        Invariants (parallel to ``invoke``):
          (1) Tool-loop hops 0..N-1 go through non-streaming ``ainvoke``
              (tool hops don't stream; only the final plain-text iteration
              streams) — the model's intermediate tool_use responses are
              not user-observable.
          (2) Final iteration uses ``bound_client.astream(...)`` — each
              non-empty text chunk is yielded as ``BackendTokenDelta``.
          (3) Guardrails are attached to EVERY model invocation
              (intermediate ``ainvoke`` + final ``astream``) when
              ``guardrail_id`` is set. ``None`` → no attachment; a WARN
              ``chat.stream.guardrail_detached`` fires.
          (4) ``ChatGuardrailInterventionError`` is raised AFTER the final
              stream drains when the trace metadata shows intervention.
              The handler layer decides what to persist; the backend's
              yielded deltas up to that point are valid (handler/API layer
              discards them on refusal per AC #4).
          (5) Token accounting mirrors ``invoke`` exactly — cumulative
              across hops; any tiktoken fallback on any hop marks the
              whole turn as ``tiktoken``-sourced.
        """
        from botocore.exceptions import ClientError
        from langchain_core.messages import (
            AIMessage,
            HumanMessage,
            SystemMessage,
            ToolMessage,
        )

        from app.agents.chat.memory_bounds import estimate_tokens
        from app.agents.chat.tools.dispatcher import ToolInvocation, dispatch_tool
        from app.agents.chat.tools.tool_errors import ChatToolLoopExceededError
        from app.agents.llm import _get_client_for, record_failure, record_success
        from app.models.chat_message import ChatMessage

        lc_messages: list[Any] = [SystemMessage(content=system_prompt)]
        for m in context_messages:
            if m.role == "user":
                lc_messages.append(HumanMessage(content=m.content))
            elif m.role == "assistant":
                lc_messages.append(AIMessage(content=m.content))
            elif m.role == "system":
                lc_messages.append(SystemMessage(content=m.content))
        lc_messages.append(HumanMessage(content=user_message))

        base_client = _get_client_for("bedrock", role="chat_default")
        try:
            bound_client = base_client.bind_tools(_lc_tools_from_manifest())
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "chat.tool.bind_failed",
                extra={
                    "db_session_id": str(db_session_id),
                    "error_class": type(exc).__name__,
                    "error_message": str(exc)[:200],
                },
            )
            raise ChatConfigurationError(
                f"Chat tool manifest bind failed: {type(exc).__name__}"
            ) from exc

        if guardrail_id is not None:
            # ChatBedrockConverse forwards per-call kwargs through to
            # ``_converse_params`` (langchain-aws bedrock_converse.py:1741):
            # ``guardrail_config`` → ``guardrailConfig`` is the path the
            # Bedrock Converse API sees. ``with_config({"configurable": ...})``
            # is a no-op unless ``configurable_fields`` was declared, which it
            # is not for this model — so we must ``bind`` the kwarg directly.
            bound_client = bound_client.bind(
                guardrail_config={
                    "guardrailIdentifier": guardrail_id,
                    "guardrailVersion": guardrail_version or "DRAFT",
                }
            )
        else:
            logger.warning(
                "chat.stream.guardrail_detached",
                extra={
                    "db_session_id": str(db_session_id),
                    "environment": settings.ENV,
                },
            )

        hops = 0
        cumul_input = 0
        cumul_output = 0
        token_source = "model"
        tool_calls: list = []
        last_tool_name: str | None = None

        while True:
            # Non-final iteration check — we peek once and may need to break
            # into the streaming path. The loop runs at least one ``ainvoke``
            # per hop; if that response carries tool_uses, we dispatch and
            # continue; if it's plain text, we re-issue via ``astream``.
            try:
                response = await bound_client.ainvoke(lc_messages)
            except ClientError as exc:
                code = exc.response.get("Error", {}).get("Code", "")
                record_failure("bedrock")
                if code == "AccessDeniedException":
                    raise ChatConfigurationError(
                        f"Bedrock AccessDenied on chat invocation (session "
                        f"{db_session_id}): {code}"
                    ) from exc
                if code in ("ThrottlingException", "ServiceUnavailableException"):
                    raise ChatTransientError(
                        f"Bedrock transient error on chat invocation "
                        f"(session {db_session_id}): {code}"
                    ) from exc
                raise
            except Exception:
                record_failure("bedrock")
                raise

            usage = getattr(response, "usage_metadata", None) or {}
            in_tokens = usage.get("input_tokens")
            out_tokens = usage.get("output_tokens")
            if in_tokens is None or out_tokens is None:
                in_tokens = estimate_tokens(
                    [
                        ChatMessage(
                            session_id=db_session_id,
                            role="user",
                            content=_stringify(m),
                        )
                        for m in lc_messages
                    ]
                )
                out_tokens = estimate_tokens(
                    [
                        ChatMessage(
                            session_id=db_session_id,
                            role="assistant",
                            content=_stringify(response),
                        )
                    ]
                )
                token_source = "tiktoken"
            cumul_input += int(in_tokens)
            cumul_output += int(out_tokens)

            intervention_kind = _detect_guardrail_intervention(response)
            if intervention_kind is not None:
                raise ChatGuardrailInterventionError(
                    intervention_kind=intervention_kind,
                    trace_summary=str(
                        getattr(response, "response_metadata", {})
                    )[:200],
                )

            tool_uses = _extract_tool_uses(response)
            if not tool_uses:
                # Final iteration — re-issue via astream so the client sees
                # token-by-token output. Token usage is re-counted from the
                # streaming response; replace the non-streaming estimate we
                # just added (it was a peek).
                cumul_input -= int(in_tokens)
                cumul_output -= int(out_tokens)
                stream_out = ""
                final_in_tokens: int | None = None
                final_out_tokens: int | None = None
                final_intervention: str | None = None
                try:
                    stream = bound_client.astream(lc_messages)
                except ClientError as exc:
                    code = exc.response.get("Error", {}).get("Code", "")
                    record_failure("bedrock")
                    if code in (
                        "ThrottlingException",
                        "ServiceUnavailableException",
                    ):
                        raise ChatTransientError(
                            f"Bedrock transient error on chat stream "
                            f"(session {db_session_id}): {code}"
                        ) from exc
                    raise

                async for chunk in stream:
                    chunk_text = _chunk_text(chunk)
                    if chunk_text:
                        stream_out += chunk_text
                        yield BackendTokenDelta(text=chunk_text)
                    chunk_usage = getattr(chunk, "usage_metadata", None) or {}
                    if chunk_usage.get("input_tokens") is not None:
                        final_in_tokens = int(chunk_usage["input_tokens"])
                    if chunk_usage.get("output_tokens") is not None:
                        final_out_tokens = int(chunk_usage["output_tokens"])
                    kind = _detect_guardrail_intervention(chunk)
                    if kind is not None:
                        final_intervention = kind

                if final_in_tokens is None or final_out_tokens is None:
                    final_in_tokens = estimate_tokens(
                        [
                            ChatMessage(
                                session_id=db_session_id,
                                role="user",
                                content=_stringify(m),
                            )
                            for m in lc_messages
                        ]
                    )
                    final_out_tokens = estimate_tokens(
                        [
                            ChatMessage(
                                session_id=db_session_id,
                                role="assistant",
                                content=stream_out,
                            )
                        ]
                    )
                    token_source = "tiktoken"
                cumul_input += int(final_in_tokens)
                cumul_output += int(final_out_tokens)

                if final_intervention is not None:
                    raise ChatGuardrailInterventionError(
                        intervention_kind=final_intervention,
                    )

                record_success("bedrock")
                yield BackendStreamDone(
                    input_tokens=cumul_input,
                    output_tokens=cumul_output,
                    token_source=token_source,
                    tool_calls=tuple(tool_calls),
                )
                return

            hops += 1
            last_tool_name = tool_uses[-1].name if tool_uses else last_tool_name
            if hops > MAX_TOOL_HOPS:
                err = ChatToolLoopExceededError(
                    hops=hops, last_tool_name=last_tool_name
                )
                err.tool_calls_so_far = tuple(tool_calls)
                raise err

            iter_results = []
            for tu in tool_uses:
                inv = ToolInvocation(
                    tool_name=tu.name, raw_input=tu.input, tool_use_id=tu.id
                )
                try:
                    res = await dispatch_tool(
                        inv,
                        user_id=user_id,
                        db=db,
                        db_session_id=db_session_id,
                    )
                except Exception as exc:
                    if hasattr(exc, "tool_calls_so_far"):
                        exc.tool_calls_so_far = tuple(tool_calls)
                    raise
                iter_results.append(res)
                tool_calls.append(res)
                yield BackendToolHop(
                    tool_name=res.tool_name,
                    hop_index=hops,
                    ok=res.ok,
                    result=res,
                )

            lc_messages.append(response)
            for r in iter_results:
                lc_messages.append(
                    ToolMessage(
                        content=json.dumps(r.payload, default=str),
                        tool_call_id=r.tool_use_id,
                    )
                )

    async def terminate_remote_session(self, agentcore_session_id: str) -> None:
        return None


def _chunk_text(chunk: Any) -> str:
    """Extract the plain-text segment of a streamed AIMessageChunk-like obj.

    langchain-aws ``ChatBedrockConverse.astream`` yields chunks whose
    ``content`` is a str OR a list of ``{"type": "text", "text": "..."}``
    blocks (tool_use blocks have ``type="tool_use"`` and are ignored on
    the streaming path — tool dispatch is done on the ainvoke peek iteration).
    """
    content = getattr(chunk, "content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, dict):
                if block.get("type") == "text":
                    parts.append(str(block.get("text", "")))
            else:
                parts.append(str(block))
        return "".join(parts)
    return ""


def _detect_guardrail_intervention(response: Any) -> str | None:
    """Inspect a response / chunk for Bedrock Guardrail intervention.

    Returns the intervention kind (one of ``content_filter`` | ``denied_topic``
    | ``pii`` | ``word_filter`` | ``grounding``) when Guardrails blocked /
    modified the response; ``None`` for clean responses.

    Detection strategy (layered — the exact langchain-aws shape is still in
    flux between minor versions, so we inspect multiple known locations):
      (1) ``response.response_metadata["stopReason"] == "guardrail_intervened"``
          with a trace at ``response.response_metadata["trace"]["guardrail"]``.
      (2) ``response.additional_kwargs["trace"]["guardrail"]`` — older
          langchain-aws shape.
      (3) ``response.response_metadata["amazon-bedrock-guardrailAction"] ==
          "INTERVENED"`` with category details in the same dict.

    Kind derivation inspects the guardrail trace dict:
      - ``contextualGroundingPolicy`` non-empty              → ``grounding``
      - ``topicPolicy`` with a blocked topic                → ``denied_topic``
      - ``sensitiveInformationPolicy`` with a PII match     → ``pii``
      - ``wordPolicy`` with a matched word                  → ``word_filter``
      - default (``contentPolicy`` filter hit or unknown)   → ``content_filter``
    """
    metadata = getattr(response, "response_metadata", None) or {}
    additional = getattr(response, "additional_kwargs", None) or {}

    stop_reason = metadata.get("stopReason") or metadata.get("stop_reason")
    guardrail_action = metadata.get("amazon-bedrock-guardrailAction") or metadata.get(
        "guardrailAction"
    )

    trace = (
        (metadata.get("trace") or {}).get("guardrail")
        if isinstance(metadata.get("trace"), dict)
        else None
    )
    if trace is None:
        trace = (
            (additional.get("trace") or {}).get("guardrail")
            if isinstance(additional.get("trace"), dict)
            else None
        )

    intervened = (
        stop_reason == "guardrail_intervened"
        or guardrail_action == "INTERVENED"
        or bool(trace)
    )
    if not intervened:
        return None

    if isinstance(trace, dict):
        output_assessments = trace.get("outputAssessments") or trace.get(
            "output_assessments"
        )
        input_assessment = trace.get("inputAssessment") or trace.get(
            "input_assessment"
        )
        blobs: list[dict] = []
        if isinstance(output_assessments, dict):
            for v in output_assessments.values():
                if isinstance(v, list):
                    blobs.extend(b for b in v if isinstance(b, dict))
                elif isinstance(v, dict):
                    blobs.append(v)
        if isinstance(input_assessment, dict):
            blobs.append(input_assessment)
        for blob in blobs:
            if blob.get("contextualGroundingPolicy"):
                return "grounding"
            if blob.get("topicPolicy"):
                return "denied_topic"
            if blob.get("sensitiveInformationPolicy"):
                return "pii"
            if blob.get("wordPolicy"):
                return "word_filter"
    return "content_filter"


def _stringify(obj: Any) -> str:
    """Best-effort str of a langchain message for tiktoken estimation.

    Used only on the fallback path when usage_metadata is missing; the
    estimate is intentionally approximate.
    """
    c = getattr(obj, "content", obj)
    if isinstance(c, str):
        return c
    if isinstance(c, list):
        return "".join(
            str(b.get("text", "")) if isinstance(b, dict) else str(b) for b in c
        )
    return str(c)


def build_backend() -> ChatBackend:
    """Factory — instantiates the backend selected by ``settings.CHAT_RUNTIME``."""
    if settings.CHAT_RUNTIME == "direct":
        return DirectBedrockBackend()
    if settings.CHAT_RUNTIME == "agentcore":
        raise ChatConfigurationError(
            "CHAT_RUNTIME='agentcore' requires Phase B (story 10.4a-runtime) "
            "— not yet implemented per ADR-0004."
        )
    raise ChatConfigurationError(f"Unknown CHAT_RUNTIME: {settings.CHAT_RUNTIME!r}")
