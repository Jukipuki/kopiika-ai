"""Chat stream event types — the handler → API-layer transport contract.

Story 10.5. Producer: ``ChatSessionHandler.send_turn_stream`` (see
session_handler.py). Consumer: the FastAPI SSE generator in
``app/api/v1/chat.py``. The events are internal — the API layer translates
them into the kebab-case SSE frames documented in
``docs/chat-sse-contract.md``.

# SCOPE: six frozen dataclasses shaped by AC #3 (Stories 10.5 + 10.6b).
# Non-goals (sibling/downstream, do NOT add here):
#   - SSE wire-framing (event: / data: lines)        → api/v1/chat.py (AC #5)
#   - CHAT_REFUSED envelope translation              → api/v1/chat.py (AC #4)
#   - JSON schema versioning                          → docs/chat-sse-contract.md
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from app.agents.chat.citations import citation_to_json_dict


@dataclass(frozen=True)
class ChatStreamStarted:
    """First event on every stream. Lets the API emit ``chat-open`` before
    any user-observable streaming — confirms auth + Guardrail binding
    completed before tokens flow."""

    correlation_id: str
    session_id: uuid.UUID


@dataclass(frozen=True)
class ChatToolHopStarted:
    """Emitted once per tool invocation, before the dispatcher runs. Collapsed
    to one ``chat-thinking`` SSE frame by the API layer (AC #5)."""

    tool_name: str
    hop_index: int  # 1-based


@dataclass(frozen=True)
class ChatToolHopCompleted:
    """Emitted after a tool dispatch resolves. NOT surfaced to the client
    (AC #5) — the next ``chat-token`` or ``chat-thinking`` is the implicit
    completion signal; a separate end-of-hop frame adds UI noise."""

    tool_name: str
    hop_index: int
    ok: bool


@dataclass(frozen=True)
class ChatTokenDelta:
    """One non-empty chunk of the final assistant iteration's text stream.

    Empty-string deltas from Bedrock are filtered BEFORE yielding (AC #3) so
    the API layer's ``chat-token`` payload is always at least one char.
    """

    text: str


@dataclass(frozen=True)
class ChatCitationsAttached:
    """Emitted on the happy path AFTER the final ChatTokenDelta and BEFORE
    ChatStreamCompleted. Empty tuple = no citations on this turn (the API
    layer skips emitting a chat-citations frame in that case)."""

    citations: tuple  # tuple[Citation, ...]


@dataclass(frozen=True)
class ChatStreamCompleted:
    """Terminal event on a successful turn. Carries the same metrics the
    non-streaming ``ChatTurnResponse`` carries — the API layer maps these
    into the ``chat-complete`` frame."""

    input_tokens: int
    output_tokens: int
    session_turn_count: int
    summarization_applied: bool
    token_source: str  # "model" | "tiktoken"
    tool_call_count: int


# Inline citation markers ([^N]) → TD-122 follow-up.


ChatStreamEvent = (
    ChatStreamStarted
    | ChatToolHopStarted
    | ChatToolHopCompleted
    | ChatTokenDelta
    | ChatCitationsAttached
    | ChatStreamCompleted
)


def event_to_json_dict(event: ChatStreamEvent) -> dict:
    """Stable JSON serialization helper — used by test_stream_events.py's
    round-trip assertions and by the API layer when logging.

    Keys are snake_case at this boundary; the API layer handles any camel
    conversion when it writes to the SSE frame payload.
    """
    if isinstance(event, ChatStreamStarted):
        return {
            "kind": "started",
            "correlation_id": event.correlation_id,
            "session_id": str(event.session_id),
        }
    if isinstance(event, ChatToolHopStarted):
        return {
            "kind": "tool_hop_started",
            "tool_name": event.tool_name,
            "hop_index": event.hop_index,
        }
    if isinstance(event, ChatToolHopCompleted):
        return {
            "kind": "tool_hop_completed",
            "tool_name": event.tool_name,
            "hop_index": event.hop_index,
            "ok": event.ok,
        }
    if isinstance(event, ChatTokenDelta):
        return {"kind": "token_delta", "text": event.text}
    if isinstance(event, ChatCitationsAttached):
        return {
            "kind": "citations_attached",
            "citations": [citation_to_json_dict(c) for c in event.citations],
        }
    if isinstance(event, ChatStreamCompleted):
        return {
            "kind": "completed",
            "input_tokens": event.input_tokens,
            "output_tokens": event.output_tokens,
            "session_turn_count": event.session_turn_count,
            "summarization_applied": event.summarization_applied,
            "token_source": event.token_source,
            "tool_call_count": event.tool_call_count,
        }
    raise TypeError(f"Unknown ChatStreamEvent variant: {type(event).__name__}")


__all__ = [
    "ChatCitationsAttached",
    "ChatStreamCompleted",
    "ChatStreamEvent",
    "ChatStreamStarted",
    "ChatTokenDelta",
    "ChatToolHopCompleted",
    "ChatToolHopStarted",
    "event_to_json_dict",
]
