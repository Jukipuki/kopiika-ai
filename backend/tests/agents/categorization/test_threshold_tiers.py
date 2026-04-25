"""Three-tier threshold routing tests (Story 11.8 AC #11 item 1).

Exercises the post-LLM threshold loop in ``categorization_node`` with canned
LLM results for each tier boundary. Verifies:
  - >= AUTO_APPLY (0.85): silent pass-through
  - [SOFT_FLAG, AUTO_APPLY): row preserved, soft-flag telemetry emitted,
    NOT flagged
  - < SOFT_FLAG (0.6): flagged=True, category='uncategorized',
    suggested_category/kind carried, queue telemetry emitted
  - Deterministic-rule carve-out skips gating at any confidence
  - Pre-pass / MCC-pass invariant: confidence always >= 0.95

The LLM path is bypassed via monkey-patching `_categorize_batch` so the test
is deterministic and does not hit any network.
"""
from __future__ import annotations

import logging
from unittest.mock import patch

import pytest

from app.agents.categorization import node as node_mod
from app.agents.categorization.node import categorization_node
from app.agents.categorization.pre_pass import classify_pre_pass


NODE_LOGGER = "app.agents.categorization.node"


class _Capture(logging.Handler):
    def __init__(self):
        super().__init__(level=logging.INFO)
        self.records: list[logging.LogRecord] = []

    def emit(self, record):
        self.records.append(record)


@pytest.fixture
def log_capture():
    h = _Capture()
    logger = logging.getLogger(NODE_LOGGER)
    logger.addHandler(h)
    prev = logger.level
    logger.setLevel(logging.INFO)
    try:
        yield h
    finally:
        logger.setLevel(prev)
        logger.removeHandler(h)


def _state(transactions: list[dict]) -> dict:
    return {
        "job_id": "job-1",
        "user_id": "user-1",
        "upload_id": "upload-1",
        "transactions": transactions,
        "completed_nodes": [],
    }


def _fake_batch_factory(canned: list[dict]):
    """Return a stub for _categorize_batch that yields canned results."""
    def _fake(batch, llm, log_ctx):  # noqa: ARG001
        out = []
        for txn in batch:
            match = next((c for c in canned if c["transaction_id"] == txn["id"]), None)
            assert match is not None, f"canned result missing for {txn['id']}"
            out.append(dict(match))
        return out, 0
    return _fake


def _tier_events(records, transaction_id=None):
    out = []
    for r in records:
        if r.getMessage() != "categorization.confidence_tier":
            continue
        extra = getattr(r, "tier", None)
        if extra is None:
            continue
        if transaction_id and getattr(r, "tx_id", None) != transaction_id:
            continue
        out.append(r)
    return out


def test_auto_apply_tier_passes_through_silent(log_capture):
    """confidence >= 0.85 → row unflagged, no telemetry event."""
    txn = {"id": "t-auto", "description": "COFFEE", "amount": -5000, "mcc": None}
    canned = [{
        "transaction_id": "t-auto",
        "category": "restaurants",
        "transaction_kind": "spending",
        "confidence_score": 0.92,
        "flagged": False,
        "uncategorized_reason": None,
    }]
    with patch.object(node_mod, "_categorize_batch", _fake_batch_factory(canned)):
        with patch.object(node_mod, "get_llm_client", lambda: object()):
            result = categorization_node(_state([txn]))

    row = next(r for r in result["categorized_transactions"] if r["transaction_id"] == "t-auto")
    assert row["flagged"] is False
    assert row["category"] == "restaurants"
    assert row["transaction_kind"] == "spending"
    assert "suggested_category" not in row
    assert _tier_events(log_capture.records, "t-auto") == []


def test_soft_flag_tier_preserves_category_and_emits(log_capture):
    """0.6 <= confidence < 0.85 → row preserved, soft-flag event, not flagged."""
    txn = {"id": "t-soft", "description": "STORE", "amount": -8000, "mcc": None}
    canned = [{
        "transaction_id": "t-soft",
        "category": "shopping",
        "transaction_kind": "spending",
        "confidence_score": 0.72,
        "flagged": False,
        "uncategorized_reason": None,
    }]
    with patch.object(node_mod, "_categorize_batch", _fake_batch_factory(canned)):
        with patch.object(node_mod, "get_llm_client", lambda: object()):
            result = categorization_node(_state([txn]))

    row = next(r for r in result["categorized_transactions"] if r["transaction_id"] == "t-soft")
    assert row["flagged"] is False
    assert row["category"] == "shopping"
    assert row["transaction_kind"] == "spending"
    assert row.get("uncategorized_reason") is None
    events = _tier_events(log_capture.records, "t-soft")
    assert len(events) == 1
    assert events[0].tier == "soft-flag"


def test_queue_tier_flags_and_carries_suggestion(log_capture):
    """confidence < 0.6 → flagged, uncategorized, suggestion carried, event."""
    txn = {"id": "t-queue", "description": "???", "amount": -4000, "mcc": None}
    canned = [{
        "transaction_id": "t-queue",
        "category": "shopping",
        "transaction_kind": "spending",
        "confidence_score": 0.42,
        "flagged": False,
        "uncategorized_reason": None,
    }]
    with patch.object(node_mod, "_categorize_batch", _fake_batch_factory(canned)):
        with patch.object(node_mod, "get_llm_client", lambda: object()):
            result = categorization_node(_state([txn]))

    row = next(r for r in result["categorized_transactions"] if r["transaction_id"] == "t-queue")
    assert row["flagged"] is True
    assert row["category"] == "uncategorized"
    assert row["uncategorized_reason"] == "low_confidence"
    assert row["suggested_category"] == "shopping"
    assert row["suggested_kind"] == "spending"
    assert row["confidence_score"] == pytest.approx(0.42)
    events = _tier_events(log_capture.records, "t-queue")
    assert len(events) == 1
    assert events[0].tier == "queue"


def test_deterministic_rule_skips_gating(log_capture):
    """Rows stamped deterministic_rule bypass the threshold (Story 11.10)."""
    txn = {
        "id": "t-det",
        "description": "Self transfer",
        "amount": -10000,
        "mcc": None,
    }
    canned = [{
        "transaction_id": "t-det",
        "category": "transfers",
        "transaction_kind": "transfer",
        "confidence_score": 0.30,  # Would normally queue — but deterministic_rule wins.
        "flagged": False,
        "uncategorized_reason": None,
        "deterministic_rule": "rule_5_self_iban",
    }]
    with patch.object(node_mod, "_categorize_batch", _fake_batch_factory(canned)):
        with patch.object(node_mod, "get_llm_client", lambda: object()):
            result = categorization_node(_state([txn]))

    row = next(r for r in result["categorized_transactions"] if r["transaction_id"] == "t-det")
    assert row["flagged"] is False
    assert row["category"] == "transfers"
    assert "suggested_category" not in row
    # No tier event for deterministic rows.
    assert _tier_events(log_capture.records, "t-det") == []


def test_pre_pass_invariant_confidence_at_or_above_095():
    """Pass 0 (description pre-pass) must always emit confidence >= 0.95.

    Invariant pinned by AC #3: if a pre-pass rule ever drops below 0.85 the
    Story 11.8 telemetry would flood with false soft-flag / queue events.
    """
    # Sample a cash-action pattern that pre-pass recognises.
    result = classify_pre_pass({
        "id": "t-pp",
        "description": "Cash withdrawal ATM",
        "amount": -50000,
        "mcc": None,
    })
    assert result is not None
    assert result["confidence_score"] >= 0.95


def test_mcc_pass_invariant_confidence_at_095():
    """Pass 1 (MCC pass) emits confidence == 0.95 — pinned by AC #3."""
    txn = {
        "id": "t-mcc",
        "description": "Coffee house",
        "amount": -7000,
        "mcc": 5814,  # restaurants
    }
    # Drive the node with only the MCC-pass txn so LLM path is never entered.
    result = categorization_node(_state([txn]))
    row = next(r for r in result["categorized_transactions"] if r["transaction_id"] == "t-mcc")
    assert row["confidence_score"] == pytest.approx(0.95)
    assert row["flagged"] is False
    assert row["category"] == "restaurants"
