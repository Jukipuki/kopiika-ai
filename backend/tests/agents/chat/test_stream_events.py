"""Story 10.5 AC #11 — ChatStreamEvent dataclass shapes."""

from __future__ import annotations

import json
import uuid

import pytest

from app.agents.chat.stream_events import (
    ChatStreamCompleted,
    ChatStreamStarted,
    ChatTokenDelta,
    ChatToolHopCompleted,
    ChatToolHopStarted,
    event_to_json_dict,
)


def test_all_events_are_frozen_and_hashable():
    sid = uuid.uuid4()
    events = [
        ChatStreamStarted(correlation_id="c", session_id=sid),
        ChatToolHopStarted(tool_name="get_transactions", hop_index=1),
        ChatToolHopCompleted(tool_name="get_transactions", hop_index=1, ok=True),
        ChatTokenDelta(text="hello"),
        ChatStreamCompleted(
            input_tokens=10,
            output_tokens=5,
            session_turn_count=2,
            summarization_applied=False,
            token_source="model",
            tool_call_count=1,
        ),
    ]
    for e in events:
        hash(e)
        with pytest.raises((AttributeError, Exception)):
            e.correlation_id = "mutated"  # type: ignore[misc]


def test_event_to_json_dict_round_trip_each_variant():
    sid = uuid.uuid4()
    for e in [
        ChatStreamStarted(correlation_id="c1", session_id=sid),
        ChatToolHopStarted(tool_name="x", hop_index=2),
        ChatToolHopCompleted(tool_name="x", hop_index=2, ok=False),
        ChatTokenDelta(text="δ"),
        ChatStreamCompleted(
            input_tokens=1,
            output_tokens=2,
            session_turn_count=3,
            summarization_applied=True,
            token_source="tiktoken",
            tool_call_count=0,
        ),
    ]:
        d = event_to_json_dict(e)
        # Must JSON-serialize (api layer logs / tests depend on this).
        json.dumps(d)
        assert "kind" in d


def test_unknown_event_raises():
    class Other:
        pass

    with pytest.raises(TypeError):
        event_to_json_dict(Other())  # type: ignore[arg-type]
