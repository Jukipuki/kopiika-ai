"""Prompt-rule + deterministic-enforcement tests for Story 11.10 Rules 5-8."""
from __future__ import annotations

import json
import logging

import pytest

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
    try:
        yield h
    finally:
        logger.removeHandler(h)


from app.agents.categorization.node import (
    _RULE_5_8_BLOCK,
    _apply_counterparty_rules,
    _build_prompt,
    _parse_llm_response,
)


# ---------------------------------------------------------------------------
# Prompt builder: counterparty block appears iff a row carries signals.
# ---------------------------------------------------------------------------


def test_prompt_includes_rule_5_8_when_counterparty_present():
    txns = [
        {
            "id": "t1",
            "description": "Платіж",
            "amount": -100000,
            "mcc": None,
            "counterparty_name": "ТОВ Приклад",
            "counterparty_tax_id": "12345678",
            "counterparty_tax_id_kind": "edrpou_8",
            "counterparty_account": "UA00",
            "is_self_iban": False,
        }
    ]
    prompt = _build_prompt(txns)
    assert _RULE_5_8_BLOCK.splitlines()[0] in prompt  # "5. Self-transfer by IBAN..."
    assert "is_self_iban=False" in prompt
    assert 'tax_id="12345678"' in prompt


def test_prompt_omits_rule_5_8_for_card_only_batch():
    """Card-only regression (AC #10): prompt is bitwise-identical to pre-11.10."""
    txns_card = [
        {"id": "t1", "description": "Кава", "amount": -5000, "mcc": 5814},
        {"id": "t2", "description": "Salary", "amount": 5000000, "mcc": None},
    ]
    prompt = _build_prompt(txns_card)
    assert "counterparty" not in prompt.lower()
    assert "is_self_iban" not in prompt
    # Rule 5-8 block must NOT appear.
    assert _RULE_5_8_BLOCK.splitlines()[0] not in prompt


# ---------------------------------------------------------------------------
# Deterministic post-processing: Rule 5, 6 override LLM; 7, 8 log only.
# ---------------------------------------------------------------------------


def test_rule_5_overrides_llm_when_is_self_iban(log_capture):
    txn = {
        "id": "t1",
        "amount": -500000,
        "counterparty_account": "UA123",
        "is_self_iban": True,
        "counterparty_tax_id_kind": "unknown",
    }
    # LLM tries to call this a P2P spend; Rule 5 must override.
    llm_result = {
        "transaction_id": "t1",
        "category": "transfers_p2p",
        "transaction_kind": "spending",
        "confidence_score": 0.7,
        "flagged": False,
        "uncategorized_reason": None,
    }
    out = _apply_counterparty_rules(txn, llm_result)
    assert out["category"] == "transfers"
    assert out["transaction_kind"] == "transfer"
    assert out["confidence_score"] >= 0.98
    msgs = [r.getMessage() for r in log_capture.records]
    assert any("counterparty_rule_hit" in m for m in msgs)
    assert any("counterparty_rule_override" in m for m in msgs)


def test_rule_6_treasury_outflow(log_capture):
    txn = {
        "id": "t2",
        "amount": -100000,
        "counterparty_tax_id": "37567646",
        "counterparty_tax_id_kind": "treasury",
        "is_self_iban": False,
    }
    llm_result = {
        "transaction_id": "t2",
        "category": "other",
        "transaction_kind": "spending",
        "confidence_score": 0.6,
        "flagged": False,
        "uncategorized_reason": None,
    }
    out = _apply_counterparty_rules(txn, llm_result)
    assert out["category"] == "government"
    assert out["transaction_kind"] == "spending"


def test_rule_6_treasury_inflow_is_income():
    txn = {
        "id": "t3",
        "amount": 500000,
        "counterparty_tax_id": "37567646",
        "counterparty_tax_id_kind": "treasury",
        "is_self_iban": False,
    }
    llm_result = {
        "transaction_id": "t3",
        "category": "government",
        "transaction_kind": "spending",
        "confidence_score": 0.5,
        "flagged": False,
        "uncategorized_reason": None,
    }
    out = _apply_counterparty_rules(txn, llm_result)
    assert out["category"] == "other"
    assert out["transaction_kind"] == "income"


def test_rule_7_rnokpp_advisory_only(log_capture):
    """Rule 7 logs a rule_hit but does NOT override the LLM's answer."""
    txn = {
        "id": "t4",
        "amount": -50000,
        "counterparty_tax_id": "1234567890",
        "counterparty_tax_id_kind": "rnokpp_10",
        "is_self_iban": False,
    }
    llm_result = {
        "transaction_id": "t4",
        "category": "transfers_p2p",
        "transaction_kind": "spending",
        "confidence_score": 0.85,
        "flagged": False,
        "uncategorized_reason": None,
    }
    out = _apply_counterparty_rules(txn, llm_result)
    assert out["category"] == "transfers_p2p"  # LLM answer preserved
    assert out["transaction_kind"] == "spending"
    msgs = [r.getMessage() for r in log_capture.records]
    assert any("counterparty_rule_hit" in m for m in msgs)
    assert not any("counterparty_rule_override" in m for m in msgs)


def test_rule_8_edrpou_advisory_only(log_capture):
    txn = {
        "id": "t5",
        "amount": -200000,
        "counterparty_tax_id": "12345678",
        "counterparty_tax_id_kind": "edrpou_8",
        "is_self_iban": False,
    }
    llm_result = {
        "transaction_id": "t5",
        "category": "shopping",
        "transaction_kind": "spending",
        "confidence_score": 0.9,
        "flagged": False,
        "uncategorized_reason": None,
    }
    out = _apply_counterparty_rules(txn, llm_result)
    # Outbound EDRPOU: description authoritative, no override.
    assert out["category"] == "shopping"
    assert out["transaction_kind"] == "spending"


def test_no_counterparty_signals_leaves_result_untouched():
    txn = {"id": "t6", "amount": -5000}  # card-only row
    llm_result = {
        "transaction_id": "t6",
        "category": "restaurants",
        "transaction_kind": "spending",
        "confidence_score": 0.93,
        "flagged": False,
        "uncategorized_reason": None,
    }
    before = dict(llm_result)
    out = _apply_counterparty_rules(txn, llm_result)
    assert out == before


# ---------------------------------------------------------------------------
# Parse pipeline: end-to-end via _parse_llm_response with canned LLM output.
# ---------------------------------------------------------------------------


def test_parse_response_applies_rule_5_to_self_iban():
    txns = [
        {
            "id": "t1",
            "amount": -500000,
            "mcc": None,
            "is_self_iban": True,
            "counterparty_account": "UA123",
            "counterparty_tax_id_kind": "unknown",
        }
    ]
    canned = json.dumps(
        [{"id": "t1", "category": "transfers_p2p", "transaction_kind": "spending", "confidence": 0.7}]
    )
    parsed = _parse_llm_response(canned, txns)
    assert parsed[0]["category"] == "transfers"
    assert parsed[0]["transaction_kind"] == "transfer"
    assert parsed[0]["confidence_score"] >= 0.98
