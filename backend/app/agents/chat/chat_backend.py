"""Chat-backend abstraction — Phase A direct-Bedrock + Phase B AgentCore seam.

Story 10.4a (ADR-0004). The handler in ``session_handler.py`` speaks only to
the ``ChatBackend`` interface; the concrete implementation is chosen by
``settings.CHAT_RUNTIME`` at ``get_chat_session_handler()`` time. Phase A
ships ``DirectBedrockBackend``; Phase B (story ``10.4a-runtime``) adds
``AgentCoreBackend`` alongside without touching the handler.

Exception translation lives here so the handler's try/except blocks stay
backend-agnostic. Both backends raise the same exception types for the same
categories of failure (IAM, throttle, service unavailable, not-found-on-
terminate).
"""

from __future__ import annotations

import abc
import uuid
from dataclasses import dataclass
from typing import Any

from app.core.config import settings


class ChatProviderNotSupportedError(Exception):
    """Raised when chat is invoked outside a Bedrock deployment.

    Phase A keeps this guard (per AC #14) even though direct-Bedrock could
    technically work on any provider via llm.py — production chat is
    Bedrock-only, and this prevents accidental anthropic/openai chat from a
    misconfigured dev env.
    """


class ChatConfigurationError(Exception):
    """Non-retryable — IAM or ARN wiring problem. Log, do not retry."""


class ChatTransientError(Exception):
    """Retryable — Bedrock throttle / transient service unavailable."""


class ChatSessionCreationError(Exception):
    """Raised when backend session creation fails after DB row insert.

    The handler catches this and compensates by deleting the orphan
    ``chat_sessions`` row — no dangling DB state.
    """


class ChatSessionTerminationFailed(Exception):
    """Raised when backend session termination fails.

    The handler logs and proceeds — consent revocation must not be blocked
    by a termination error (see AC #11 fail-open semantics).
    """


@dataclass(frozen=True)
class ChatInvocationResult:
    """Return payload from ``ChatBackend.invoke``.

    ``token_source`` is ``"model"`` when the Bedrock response carried usage
    metadata, ``"tiktoken"`` when we fell back to the local estimator in
    ``memory_bounds.estimate_tokens``. Story 10.9 uses this to distinguish
    real counts from approximations in dashboards.
    """

    text: str
    input_tokens: int
    output_tokens: int
    token_source: str  # "model" | "tiktoken"


def _bedrock_only_guard() -> None:
    """Raise ``ChatProviderNotSupportedError`` unless LLM_PROVIDER=bedrock.

    Matches the error message specified by AC #14 so downstream stories and
    operators see a consistent diagnostic. In Phase A (CHAT_RUNTIME='direct')
    only LLM_PROVIDER is asserted; AGENTCORE_RUNTIME_ARN is unused and is
    required only by Phase B (CHAT_RUNTIME='agentcore', story 10.4a-runtime).
    """
    if settings.LLM_PROVIDER != "bedrock":
        if settings.CHAT_RUNTIME == "agentcore":
            detail = (
                "Phase B requires LLM_PROVIDER=bedrock and "
                "AGENTCORE_RUNTIME_ARN set."
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
    async def create_remote_session(self, db_session_id: uuid.UUID) -> str:
        """Create backend-side session state (if any); return its identifier.

        Phase A: no remote state — returns ``str(db_session_id)`` so the
        handler's ``ChatSessionHandle.agentcore_session_id`` is populated
        uniformly across phases.
        Phase B: calls ``bedrock-agentcore:CreateSession`` and returns the
        AWS-assigned session id.
        """

    @abc.abstractmethod
    async def invoke(
        self,
        *,
        db_session_id: uuid.UUID,
        context_messages: list[
            Any
        ],  # list[ChatMessage] — kept loose to avoid import cycle
        user_message: str,
    ) -> ChatInvocationResult: ...

    @abc.abstractmethod
    async def terminate_remote_session(self, agentcore_session_id: str) -> None:
        """Tear down backend-side session state.

        Phase A: no-op. Phase B: ``bedrock-agentcore:DeleteSession``,
        idempotent on 404. Raises ``ChatSessionTerminationFailed`` on other
        errors; caller decides whether to propagate.
        """


class DirectBedrockBackend(ChatBackend):
    """Phase A backend — direct ``bedrock-runtime:InvokeModel`` via ``llm.py``.

    Uses the ``chat_default`` models.yaml role (Sonnet inference profile)
    for the conversational turn. Summarization (owned by the handler, not
    this class) uses ``agent_default`` (Haiku) via ``get_llm_client()`` —
    see ``session_handler.py``.
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
    ) -> ChatInvocationResult:
        # Local imports keep the module importable on non-bedrock dev machines
        # (langchain_aws pulls boto3; boto3 credentials chain resolution does
        # not fire at import, but keeping imports lazy matches the handler
        # module's posture and avoids surprising side-effects at collection
        # time under pytest.)
        from botocore.exceptions import ClientError
        from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

        from app.agents.chat.memory_bounds import estimate_tokens
        from app.agents.llm import _get_client_for, record_failure, record_success
        from app.models.chat_message import ChatMessage

        lc_messages = []
        for m in context_messages:
            if m.role == "user":
                lc_messages.append(HumanMessage(content=m.content))
            elif m.role == "assistant":
                lc_messages.append(AIMessage(content=m.content))
            elif m.role == "system":
                lc_messages.append(SystemMessage(content=m.content))
        lc_messages.append(HumanMessage(content=user_message))

        client = _get_client_for("bedrock", role="chat_default")
        try:
            response = await client.ainvoke(lc_messages)
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
        else:
            record_success("bedrock")

        # Langchain's AIMessage.content is str for plain text, or a list of
        # content blocks for tool-use responses. Phase A has no tools (10.4c),
        # so a list here is anomalous — flatten defensively.
        if isinstance(response.content, str):
            text = response.content
        elif isinstance(response.content, list):
            text = "".join(
                part.get("text", "") if isinstance(part, dict) else str(part)
                for part in response.content
            )
        else:
            text = str(response.content)

        usage = getattr(response, "usage_metadata", None) or {}
        input_tokens = usage.get("input_tokens")
        output_tokens = usage.get("output_tokens")
        if input_tokens is None or output_tokens is None:
            # Fallback: cl100k_base estimate on the rendered context + output.
            # Direction of error is documented in memory_bounds.py.
            input_tokens = estimate_tokens(
                [
                    *context_messages,
                    ChatMessage(
                        session_id=db_session_id, role="user", content=user_message
                    ),
                ]
            )
            output_tokens = estimate_tokens(
                [ChatMessage(session_id=db_session_id, role="assistant", content=text)]
            )
            token_source = "tiktoken"
        else:
            token_source = "model"

        return ChatInvocationResult(
            text=text,
            input_tokens=int(input_tokens),
            output_tokens=int(output_tokens),
            token_source=token_source,
        )

    async def terminate_remote_session(self, agentcore_session_id: str) -> None:
        # Phase A: no remote session to terminate. Handler still calls this
        # so the code path exercises on both phases (Phase B: DeleteSession).
        return None


def build_backend() -> ChatBackend:
    """Factory — instantiates the backend selected by ``settings.CHAT_RUNTIME``.

    Phase A: always ``DirectBedrockBackend``. Phase B (10.4a-runtime) adds an
    ``"agentcore"`` branch returning ``AgentCoreBackend``. No public-API
    change at the handler level.
    """
    if settings.CHAT_RUNTIME == "direct":
        return DirectBedrockBackend()
    if settings.CHAT_RUNTIME == "agentcore":
        raise ChatConfigurationError(
            "CHAT_RUNTIME='agentcore' requires Phase B (story 10.4a-runtime) "
            "— not yet implemented per ADR-0004."
        )
    raise ChatConfigurationError(f"Unknown CHAT_RUNTIME: {settings.CHAT_RUNTIME!r}")
