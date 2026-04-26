"""Story 10.5 AC #11 — ChatStreamEvent dataclass shapes."""

from __future__ import annotations

import json
import uuid

import pytest

from datetime import date

from app.agents.chat.citations import (
    CategoryCitation,
    ProfileFieldCitation,
    RagDocCitation,
    TransactionCitation,
)
from app.agents.chat.stream_events import (
    ChatCitationsAttached,
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


def test_citations_attached_round_trip_each_kind():
    citations = (
        TransactionCitation(
            id=uuid.uuid4(),
            booked_at=date(2026, 3, 14),
            description="Coffee",
            amount_kopiykas=-100,
            currency="UAH",
            category_code="groceries",
            label="Coffee · 2026-03-14",
        ),
        CategoryCitation(code="groceries", label="Groceries"),
        ProfileFieldCitation(
            field="monthly_expenses_kopiykas",
            value=4_530_000,
            currency="UAH",
            as_of=date(2026, 4, 1),
            label="Monthly expenses (Apr 2026)",
        ),
        RagDocCitation(
            source_id="en/x",
            title="en/x",
            snippet="a",
            similarity=0.5,
            label="en/x",
        ),
    )
    event = ChatCitationsAttached(citations=citations)
    d = event_to_json_dict(event)
    assert d["kind"] == "citations_attached"
    assert len(d["citations"]) == 4
    json.dumps(d)  # serializable without an encoder hook (uuids/dates → str)


def test_unknown_event_raises():
    class Other:
        pass

    with pytest.raises(TypeError):
        event_to_json_dict(Other())  # type: ignore[arg-type]
