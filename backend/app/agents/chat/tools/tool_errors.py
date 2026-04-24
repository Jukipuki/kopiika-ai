"""Typed exceptions raised at the chat tool-loop boundary.

Story 10.4c. Soft-vs-hard split:
- Soft (returned to the model as a ``ToolResult`` for self-correction):
  schema errors, execution errors, unknown tools emitted by the model.
  These do NOT raise — the dispatcher builds an ``ok=False`` result and
  returns it so the next loop iteration lets the model recover.
- Hard (bubble up to the handler; turn is aborted):
  ``ChatToolAuthorizationError`` (cross-user read attempt — fail closed),
  ``ChatToolLoopExceededError`` (too many hops — probably adversarial).

The ``not_allowed`` exception has dual use: the dispatcher catches it
internally and converts to a soft ToolResult; the loop guard raises it
outward as a hard failure if the model keeps calling unknown tools past
the hop cap. The same class reads naturally in both places.
"""

from __future__ import annotations


class ChatToolError(Exception):
    """Base class — callers should catch the concrete subclass.

    ``tool_calls_so_far`` carries any ``ToolResult`` objects the backend had
    already collected when the error fired, so the handler can persist them
    as ``role='tool'`` rows for forensic value (Story 10.4c AC #9).
    Populated by the backend before re-raising; ``()`` if never set.
    """

    tool_calls_so_far: tuple = ()


class ChatToolNotAllowedError(ChatToolError):
    """The model asked for a tool that is not in the allowlist."""

    def __init__(self, *, tool_name: str) -> None:
        super().__init__(f"Tool not allowed: {tool_name!r}")
        self.tool_name = tool_name


class ChatToolSchemaError(ChatToolError):
    """The model's tool input failed pydantic validation."""

    def __init__(self, *, tool_name: str, detail: str) -> None:
        super().__init__(f"Tool schema error for {tool_name!r}: {detail}")
        self.tool_name = tool_name
        self.detail = detail


class ChatToolExecutionError(ChatToolError):
    """A handler raised an unexpected error during execution."""

    def __init__(self, *, tool_name: str) -> None:
        super().__init__(f"Tool execution error for {tool_name!r}")
        self.tool_name = tool_name


class ChatToolAuthorizationError(ChatToolError):
    """A handler detected a cross-user access attempt.

    Fail-closed: this bubbles upward out of the dispatcher without being
    converted to a ToolResult. A misrouted cross-user read is never
    returned to the model, even as an error envelope.
    """

    def __init__(self, *, tool_name: str) -> None:
        super().__init__(f"Tool authorization failed for {tool_name!r}")
        self.tool_name = tool_name


class ChatToolLoopExceededError(ChatToolError):
    """The tool-use loop exceeded ``MAX_TOOL_HOPS``.

    Likely a stuck loop or adversarial driving; the handler aborts the
    turn and the SSE translator (Story 10.5) surfaces the user-facing
    ``CHAT_REFUSED.reason="tool_blocked"`` envelope.
    """

    def __init__(self, *, hops: int, last_tool_name: str | None = None) -> None:
        super().__init__(f"Tool loop exceeded after {hops} hops")
        self.hops = hops
        self.last_tool_name = last_tool_name


__all__ = [
    "ChatToolAuthorizationError",
    "ChatToolError",
    "ChatToolExecutionError",
    "ChatToolLoopExceededError",
    "ChatToolNotAllowedError",
    "ChatToolSchemaError",
]
