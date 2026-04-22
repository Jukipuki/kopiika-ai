"""Tests for Story 11.2: transaction_kind field + expanded MCC taxonomy."""

import json
import uuid
from unittest.mock import MagicMock, patch

import pytest

from app.agents.categorization.mcc_mapping import (
    KIND_CATEGORY_RULES,
    MCC_TO_CATEGORY,
    VALID_CATEGORIES,
    VALID_KINDS,
    get_mcc_category,
    kind_by_sign,
    validate_kind_category,
)
from app.agents.categorization.node import categorization_node


def _make_transaction(mcc=None, description="Test", amount=-10000) -> dict:
    return {
        "id": str(uuid.uuid4()),
        "mcc": mcc,
        "description": description,
        "amount": amount,
        "date": "2026-04-20",
    }


def _make_state(**overrides):
    base = {
        "job_id": str(uuid.uuid4()),
        "user_id": str(uuid.uuid4()),
        "upload_id": str(uuid.uuid4()),
        "transactions": [],
        "categorized_transactions": [],
        "errors": [],
        "step": "categorization",
        "total_tokens_used": 0,
        "locale": "uk",
        "insight_cards": [],
        "literacy_level": "beginner",
        "completed_nodes": [],
        "failed_node": None,
        "pattern_findings": [],
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# MCC pass: emits transaction_kind='spending' with confidence 0.95
# ---------------------------------------------------------------------------

def test_mcc_pass_emits_transaction_kind_spending():
    txn = _make_transaction(mcc=5411, description="СІЛЬПО")
    state = _make_state(transactions=[txn])

    with patch("app.agents.categorization.node.get_llm_client") as mock_get_llm:
        result = categorization_node(state)

    mock_get_llm.assert_not_called()
    entry = result["categorized_transactions"][0]
    assert entry["category"] == "groceries"
    assert entry["transaction_kind"] == "spending"
    assert entry["confidence_score"] == 0.95


# ---------------------------------------------------------------------------
# MCC table changes (AC #2, #4)
# ---------------------------------------------------------------------------

def test_mcc_4829_routes_to_llm_pass():
    """MCC 4829 (Wire Transfer / Money Order) is intentionally unmapped."""
    assert 4829 not in MCC_TO_CATEGORY
    assert get_mcc_category(4829) is None


def test_mcc_8398_maps_to_charity():
    assert get_mcc_category(8398) == "charity"


def test_mcc_4215_maps_to_shopping():
    assert get_mcc_category(4215) == "shopping"


# ---------------------------------------------------------------------------
# Story 11.3a: new MCC entries + intentional omissions (AC #3, #4)
# ---------------------------------------------------------------------------

def test_mcc_5200_maps_to_shopping():
    """Home Supply Warehouse Stores — catches FOP-on-5200 merchants."""
    assert get_mcc_category(5200) == "shopping"


def test_mcc_8021_maps_to_healthcare():
    """Dentists and Orthodontists — catches FOP-on-8021 merchants."""
    assert get_mcc_category(8021) == "healthcare"


def test_mcc_6010_maps_to_atm_cash():
    """Manual Cash Disbursement — functionally same as ATM (6011)."""
    assert get_mcc_category(6010) == "atm_cash"


def test_mcc_4816_intentionally_unmapped():
    """Computer Network Services — description-authoritative, routed to LLM pass."""
    assert 4816 not in MCC_TO_CATEGORY
    assert get_mcc_category(4816) is None


def test_mcc_6012_intentionally_unmapped():
    """Financial Institutions - Merchandise — fintech catchall, routed to LLM pass."""
    assert 6012 not in MCC_TO_CATEGORY
    assert get_mcc_category(6012) is None


def test_valid_categories_includes_new_buckets():
    """Story 11.1 added these — sanity-check they survived 11.2."""
    for cat in ("savings", "transfers_p2p", "charity"):
        assert cat in VALID_CATEGORIES


# ---------------------------------------------------------------------------
# kind/category compatibility matrix
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    ("kind", "category"),
    [
        ("spending", "groceries"),
        ("spending", "restaurants"),
        ("spending", "charity"),
        ("spending", "transfers_p2p"),
        ("income", "other"),
        ("income", "uncategorized"),
        ("savings", "savings"),
        ("transfer", "transfers"),
    ],
)
def test_validate_kind_category_valid_pairs(kind, category):
    assert validate_kind_category(kind, category) is True


@pytest.mark.parametrize(
    ("kind", "category"),
    [
        ("spending", "savings"),       # spending excludes savings
        ("income", "groceries"),       # income only allows other/uncategorized
        ("income", "restaurants"),
        ("savings", "groceries"),      # savings only allows savings
        ("transfer", "groceries"),     # transfer only allows transfers
        ("transfer", "transfers_p2p"),
        ("bogus", "groceries"),        # unknown kind
    ],
)
def test_validate_kind_category_invalid_pairs(kind, category):
    assert validate_kind_category(kind, category) is False


def test_kind_category_rules_cover_all_valid_kinds():
    assert set(KIND_CATEGORY_RULES.keys()) == set(VALID_KINDS)


# ---------------------------------------------------------------------------
# kind_by_sign helper
# ---------------------------------------------------------------------------

def test_kind_by_sign_negative_is_spending():
    assert kind_by_sign(-100) == "spending"


def test_kind_by_sign_positive_is_income():
    assert kind_by_sign(50000) == "income"


def test_kind_by_sign_zero_is_spending():
    """Zero-amount edge case: default to spending (defensive — shouldn't happen in practice)."""
    assert kind_by_sign(0) == "spending"


# ---------------------------------------------------------------------------
# LLM pass picks up sign-based default until Story 11.3 enriches the prompt
# ---------------------------------------------------------------------------

def test_llm_pass_falls_back_to_kind_by_sign_when_llm_omits_kind():
    """LLM response lacks transaction_kind → sign-based default applied."""
    spend_txn = _make_transaction(mcc=None, description="Mystery shop", amount=-5000)
    income_txn = _make_transaction(mcc=None, description="Salary", amount=200000)
    state = _make_state(transactions=[spend_txn, income_txn])

    llm_payload = [
        {"id": spend_txn["id"], "category": "shopping", "confidence": 0.9},
        {"id": income_txn["id"], "category": "other", "confidence": 0.9},
    ]
    mock_response = MagicMock()
    mock_response.content = json.dumps(llm_payload)
    mock_response.usage_metadata = {"total_tokens": 50}

    mock_llm = MagicMock()
    mock_llm.invoke.return_value = mock_response
    mock_llm.model = "claude-haiku-4-5-20251001"

    with patch("app.agents.categorization.node.get_llm_client", return_value=mock_llm):
        result = categorization_node(state)

    by_id = {c["transaction_id"]: c for c in result["categorized_transactions"]}
    assert by_id[spend_txn["id"]]["transaction_kind"] == "spending"
    assert by_id[income_txn["id"]]["transaction_kind"] == "income"


def test_fallback_pair_is_always_valid():
    """The persistence fallback is (uncategorized, kind_by_sign(amount)) — must always pass the matrix."""
    for amount in (-100, 0, 1, 99999):
        kind = kind_by_sign(amount)
        assert validate_kind_category(kind, "uncategorized") is True, (
            f"Fallback pair ({kind}, uncategorized) must be valid for amount={amount}"
        )


def test_llm_parse_failure_emits_kind_by_sign():
    """Parse failure path also stamps transaction_kind via sign."""
    txn = _make_transaction(mcc=None, description="Garbled", amount=-2500)
    state = _make_state(transactions=[txn])

    mock_response = MagicMock()
    mock_response.content = "not valid json {"
    mock_response.usage_metadata = {"total_tokens": 5}

    mock_llm = MagicMock()
    mock_llm.invoke.return_value = mock_response
    mock_llm.model = "claude-haiku-4-5-20251001"

    with patch("app.agents.categorization.node.get_llm_client", return_value=mock_llm):
        result = categorization_node(state)

    entry = result["categorized_transactions"][0]
    assert entry["uncategorized_reason"] == "parse_failure"
    assert entry["transaction_kind"] == "spending"
