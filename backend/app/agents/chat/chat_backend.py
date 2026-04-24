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
import uuid
from dataclasses import dataclass, field
from typing import Any

from app.core.config import settings

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

    async def terminate_remote_session(self, agentcore_session_id: str) -> None:
        return None


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
