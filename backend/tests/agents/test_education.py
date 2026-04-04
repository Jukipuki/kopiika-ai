"""Tests for Education Agent (Story 3.3)."""

import json
import uuid
from unittest.mock import MagicMock, patch

import pytest

from app.agents.education.node import (
    _build_spending_summary,
    _parse_insight_cards,
    education_node,
)
from app.agents.education.prompts import get_prompt
from app.agents.state import FinancialPipelineState

# Stable UUIDs so transactions and categorized_transactions can be joined by id
_TXN_IDS = [str(uuid.uuid4()) for _ in range(5)]


def _make_state(**overrides) -> FinancialPipelineState:
    """Return a minimal pipeline state for tests."""
    base: FinancialPipelineState = {
        "job_id": str(uuid.uuid4()),
        "user_id": str(uuid.uuid4()),
        "upload_id": str(uuid.uuid4()),
        "transactions": [],
        "categorized_transactions": [],
        "errors": [],
        "step": "education",
        "total_tokens_used": 0,
        "locale": "uk",
        "insight_cards": [],
    }
    base.update(overrides)
    return base


def _make_transactions() -> list[dict]:
    """Raw transactions with amounts (matches real pipeline shape)."""
    return [
        {"id": _TXN_IDS[0], "mcc": "5411", "description": "ATB Market", "amount": -450000, "date": "2026-03-15"},
        {"id": _TXN_IDS[1], "mcc": "5411", "description": "Silpo", "amount": -230000, "date": "2026-03-16"},
        {"id": _TXN_IDS[2], "mcc": "5812", "description": "Puzata Hata", "amount": -120000, "date": "2026-03-17"},
        {"id": _TXN_IDS[3], "mcc": "4111", "description": "Bolt ride", "amount": -80000, "date": "2026-03-18"},
        {"id": _TXN_IDS[4], "mcc": "7832", "description": "Multiplex Cinema", "amount": -50000, "date": "2026-03-19"},
    ]


def _make_categorized_transactions() -> list[dict]:
    """Categorized transactions WITHOUT amounts (matches real categorization node output)."""
    return [
        {"transaction_id": _TXN_IDS[0], "category": "groceries", "confidence_score": 1.0, "flagged": False},
        {"transaction_id": _TXN_IDS[1], "category": "groceries", "confidence_score": 1.0, "flagged": False},
        {"transaction_id": _TXN_IDS[2], "category": "restaurants", "confidence_score": 0.9, "flagged": False},
        {"transaction_id": _TXN_IDS[3], "category": "transport", "confidence_score": 1.0, "flagged": False},
        {"transaction_id": _TXN_IDS[4], "category": "entertainment", "confidence_score": 0.85, "flagged": False},
    ]


MOCK_INSIGHT_CARDS = [
    {
        "headline": "High grocery spending",
        "key_metric": "₴6,800 on groceries",
        "why_it_matters": "Groceries are your largest expense category.",
        "deep_dive": "Consider meal planning to reduce food waste and costs.",
        "severity": "medium",
        "category": "groceries",
    },
    {
        "headline": "Dining out adds up",
        "key_metric": "₴1,200 on restaurants",
        "why_it_matters": "Restaurant spending is about 15% of your food budget.",
        "deep_dive": "Cooking at home can save significantly over time.",
        "severity": "low",
        "category": "restaurants",
    },
]

MOCK_RAG_DOCS = [
    {"doc_id": "uk/budgeting-basics", "language": "uk", "chunk_type": "overview", "content": "Бюджет — це план...", "similarity": 0.92},
    {"doc_id": "uk/spending-categories", "language": "uk", "chunk_type": "key_concepts", "content": "Категорії витрат...", "similarity": 0.88},
]


# ---------------------------------------------------------------------------
# Prompt tests
# ---------------------------------------------------------------------------

def test_get_prompt_english():
    prompt = get_prompt("en")
    assert "financial education assistant" in prompt
    assert "{user_context}" in prompt
    assert "{rag_context}" in prompt


def test_get_prompt_ukrainian():
    prompt = get_prompt("uk")
    assert "фінансовий освітній асистент" in prompt
    assert "{user_context}" in prompt
    assert "{rag_context}" in prompt


def test_get_prompt_defaults_to_ukrainian():
    prompt = get_prompt("fr")
    assert "фінансовий освітній асистент" in prompt


# ---------------------------------------------------------------------------
# Spending summary tests
# ---------------------------------------------------------------------------

def test_build_spending_summary():
    txns = _make_transactions()
    cats = _make_categorized_transactions()
    summary = _build_spending_summary(txns, cats)
    assert "groceries" in summary
    assert "restaurants" in summary
    assert "Total spending" in summary
    # Verify amounts are non-zero (C1 regression guard)
    assert "₴0.00" not in summary.split("\n")[0]


def test_build_spending_summary_empty():
    summary = _build_spending_summary([], [])
    assert "Total spending: ₴0.00" in summary


# ---------------------------------------------------------------------------
# Parse insight cards tests
# ---------------------------------------------------------------------------

def test_parse_insight_cards_valid_json():
    content = json.dumps(MOCK_INSIGHT_CARDS)
    cards = _parse_insight_cards(content)
    assert len(cards) == 2
    assert cards[0]["headline"] == "High grocery spending"
    assert cards[1]["category"] == "restaurants"


def test_parse_insight_cards_with_markdown_fences():
    content = f"```json\n{json.dumps(MOCK_INSIGHT_CARDS)}\n```"
    cards = _parse_insight_cards(content)
    assert len(cards) == 2


def test_parse_insight_cards_invalid_json():
    with pytest.raises(Exception):
        _parse_insight_cards("not json at all")


def test_parse_insight_cards_not_array():
    with pytest.raises(ValueError, match="not a JSON array"):
        _parse_insight_cards('{"headline": "test"}')


# ---------------------------------------------------------------------------
# Education node — happy path
# ---------------------------------------------------------------------------

def test_education_node_happy_path():
    """Education node generates insight cards with mocked retriever + LLM."""
    mock_response = MagicMock()
    mock_response.content = json.dumps(MOCK_INSIGHT_CARDS)

    state = _make_state(
        transactions=_make_transactions(),
        categorized_transactions=_make_categorized_transactions(),
        locale="uk",
    )

    with (
        patch("app.agents.education.node.retrieve_relevant_docs", return_value=MOCK_RAG_DOCS),
        patch("app.agents.education.node.get_llm_client") as mock_llm_fn,
    ):
        mock_llm_fn.return_value.invoke.return_value = mock_response
        result = education_node(state)

    assert len(result["insight_cards"]) == 2
    assert result["insight_cards"][0]["headline"] == "High grocery spending"
    assert result["step"] == "education"


def test_education_node_english_locale():
    """Education node uses English prompt when locale is 'en'."""
    mock_response = MagicMock()
    mock_response.content = json.dumps(MOCK_INSIGHT_CARDS)

    state = _make_state(
        transactions=_make_transactions(),
        categorized_transactions=_make_categorized_transactions(),
        locale="en",
    )

    with (
        patch("app.agents.education.node.retrieve_relevant_docs", return_value=MOCK_RAG_DOCS),
        patch("app.agents.education.node.get_llm_client") as mock_llm_fn,
    ):
        mock_llm_fn.return_value.invoke.return_value = mock_response
        result = education_node(state)

    assert len(result["insight_cards"]) == 2


# ---------------------------------------------------------------------------
# Education node — graceful degradation (AC #5)
# ---------------------------------------------------------------------------

def test_education_node_graceful_degradation_retriever_failure():
    """When retriever fails, education node returns empty insight_cards."""
    state = _make_state(
        transactions=_make_transactions(),
        categorized_transactions=_make_categorized_transactions(),
    )

    with patch("app.agents.education.node.retrieve_relevant_docs", side_effect=Exception("DB down")):
        result = education_node(state)

    assert result["insight_cards"] == []
    assert result["step"] == "education"


def test_education_node_graceful_degradation_llm_failure():
    """When both LLMs fail, education node returns empty insight_cards."""
    state = _make_state(
        transactions=_make_transactions(),
        categorized_transactions=_make_categorized_transactions(),
    )

    with (
        patch("app.agents.education.node.retrieve_relevant_docs", return_value=MOCK_RAG_DOCS),
        patch("app.agents.education.node.get_llm_client", side_effect=Exception("LLM down")),
        patch("app.agents.education.node.get_fallback_llm_client", side_effect=Exception("Fallback down")),
    ):
        result = education_node(state)

    assert result["insight_cards"] == []
    assert result["step"] == "education"


def test_education_node_graceful_degradation_parse_failure():
    """When LLM returns unparseable content, returns empty insight_cards."""
    mock_response = MagicMock()
    mock_response.content = "This is not JSON"

    state = _make_state(
        transactions=_make_transactions(),
        categorized_transactions=_make_categorized_transactions(),
    )

    with (
        patch("app.agents.education.node.retrieve_relevant_docs", return_value=MOCK_RAG_DOCS),
        patch("app.agents.education.node.get_llm_client") as mock_llm_fn,
    ):
        mock_llm_fn.return_value.invoke.return_value = mock_response
        result = education_node(state)

    assert result["insight_cards"] == []
    assert result["step"] == "education"


def test_education_node_no_categorized_transactions():
    """With no categorized transactions, education node skips and returns empty."""
    state = _make_state(categorized_transactions=[])
    result = education_node(state)
    assert result["insight_cards"] == []
    assert result["step"] == "education"


# ---------------------------------------------------------------------------
# Education node — fallback LLM
# ---------------------------------------------------------------------------

def test_education_node_primary_fails_uses_fallback():
    """When primary LLM fails, fallback LLM is used."""
    mock_response = MagicMock()
    mock_response.content = json.dumps(MOCK_INSIGHT_CARDS)

    state = _make_state(
        transactions=_make_transactions(),
        categorized_transactions=_make_categorized_transactions(),
    )

    with (
        patch("app.agents.education.node.retrieve_relevant_docs", return_value=MOCK_RAG_DOCS),
        patch("app.agents.education.node.get_llm_client") as mock_primary,
        patch("app.agents.education.node.get_fallback_llm_client") as mock_fallback,
    ):
        mock_primary.return_value.invoke.side_effect = Exception("Primary down")
        mock_fallback.return_value.invoke.return_value = mock_response
        result = education_node(state)

    assert len(result["insight_cards"]) == 2
