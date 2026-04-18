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
        "literacy_level": "beginner",
        "completed_nodes": [],
        "failed_node": None,
        "pattern_findings": [],
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
# Prompt tests — literacy level (Story 3.8)
# ---------------------------------------------------------------------------

def test_get_prompt_en_beginner():
    prompt = get_prompt("en", "beginner")
    assert "financial education assistant" in prompt
    assert "Explain concepts simply" in prompt


def test_get_prompt_en_intermediate():
    prompt = get_prompt("en", "intermediate")
    assert "financial education assistant" in prompt
    assert "optimization strategies" in prompt
    assert "50/30/20" in prompt


def test_get_prompt_uk_beginner():
    prompt = get_prompt("uk", "beginner")
    assert "фінансовий освітній асистент" in prompt
    assert "Пояснюй поняття просто" in prompt


def test_get_prompt_uk_intermediate():
    prompt = get_prompt("uk", "intermediate")
    assert "фінансовий освітній асистент" in prompt
    assert "стратегіях оптимізації" in prompt
    assert "50/30/20" in prompt


def test_get_prompt_all_four_combinations_return_different_prompts():
    """All four locale+literacy combinations return distinct prompts."""
    prompts = {
        get_prompt("en", "beginner"),
        get_prompt("en", "intermediate"),
        get_prompt("uk", "beginner"),
        get_prompt("uk", "intermediate"),
    }
    assert len(prompts) == 4


def test_get_prompt_defaults_to_beginner():
    """Without literacy_level argument, defaults to beginner."""
    assert get_prompt("en") == get_prompt("en", "beginner")
    assert get_prompt("uk") == get_prompt("uk", "beginner")


# ---------------------------------------------------------------------------
# Prompt tests — key_metric constraint (Story 3.9)
# ---------------------------------------------------------------------------

def test_key_metric_constraint_english_contains_new_wording():
    """Both English prompts contain the updated 60-char constraint text."""
    for literacy in ("beginner", "intermediate"):
        prompt = get_prompt("en", literacy)
        assert "Max 60 chars" in prompt, (
            f"English {literacy} prompt missing 60-char key_metric constraint"
        )
        assert "Do NOT combine multiple numeric figures" in prompt, (
            f"English {literacy} prompt missing 'Do NOT combine' rule"
        )


def test_key_metric_constraint_ukrainian_contains_new_wording():
    """Both Ukrainian prompts contain the updated 60-char constraint text."""
    for literacy in ("beginner", "intermediate"):
        prompt = get_prompt("uk", literacy)
        assert "60 символів" in prompt, (
            f"Ukrainian {literacy} prompt missing 60-символів key_metric constraint"
        )
        assert "НЕ поєднуй" in prompt, (
            f"Ukrainian {literacy} prompt missing 'НЕ поєднуй' rule"
        )


def test_key_metric_old_constraint_not_present_in_any_prompt():
    """Regression guard: the old 30-char constraint must not appear in EN or UK prompts."""
    all_prompts = [
        get_prompt("en", "beginner"),
        get_prompt("en", "intermediate"),
        get_prompt("uk", "beginner"),
        get_prompt("uk", "intermediate"),
    ]
    for prompt in all_prompts:
        assert "max 30" not in prompt.lower(), (
            "Old English 30-char key_metric constraint still present — update prompts.py"
        )
        assert "макс 30" not in prompt.lower(), (
            "Old Ukrainian 30-char key_metric constraint still present — update prompts.py"
        )


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
# Education node — literacy level handling (Story 3.8)
# ---------------------------------------------------------------------------

def test_education_node_reads_literacy_level_from_state():
    """Education node reads literacy_level from state and passes it to get_prompt."""
    mock_response = MagicMock()
    mock_response.content = json.dumps(MOCK_INSIGHT_CARDS)

    state = _make_state(
        transactions=_make_transactions(),
        categorized_transactions=_make_categorized_transactions(),
        locale="en",
        literacy_level="intermediate",
    )

    with (
        patch("app.agents.education.node.retrieve_relevant_docs", return_value=MOCK_RAG_DOCS),
        patch("app.agents.education.node.get_llm_client") as mock_llm_fn,
        patch("app.agents.education.node.get_prompt") as mock_get_prompt,
    ):
        mock_get_prompt.return_value = "mock prompt {user_context} {rag_context}"
        mock_llm_fn.return_value.invoke.return_value = mock_response
        education_node(state)

    mock_get_prompt.assert_called_once_with("en", "intermediate")


def test_education_node_defaults_literacy_level_to_beginner():
    """Education node defaults literacy_level to 'beginner' when not in state."""
    mock_response = MagicMock()
    mock_response.content = json.dumps(MOCK_INSIGHT_CARDS)

    # Create state without literacy_level key to test fallback default
    state = _make_state(
        transactions=_make_transactions(),
        categorized_transactions=_make_categorized_transactions(),
        locale="uk",
    )
    del state["literacy_level"]

    with (
        patch("app.agents.education.node.retrieve_relevant_docs", return_value=MOCK_RAG_DOCS),
        patch("app.agents.education.node.get_llm_client") as mock_llm_fn,
        patch("app.agents.education.node.get_prompt") as mock_get_prompt,
    ):
        mock_get_prompt.return_value = "mock prompt {user_context} {rag_context}"
        mock_llm_fn.return_value.invoke.return_value = mock_response
        education_node(state)

    mock_get_prompt.assert_called_once_with("uk", "beginner")


def test_education_node_applies_triage_severity_override(monkeypatch):
    """Story 8.3: LLM-assigned severity is overridden by triage_category_severity_map
    for cards whose category matches the map; non-matching cards keep LLM severity."""
    mock_response = MagicMock()
    mock_response.content = json.dumps([
        # Category in map → overridden to 'critical'
        {"headline": "Food", "key_metric": "₴6,800", "why_it_matters": "x",
         "deep_dive": "y", "severity": "info", "category": "groceries"},
        # Category NOT in map → keeps LLM-assigned 'warning'
        {"headline": "Restaurants", "key_metric": "₴1,200", "why_it_matters": "x",
         "deep_dive": "y", "severity": "warning", "category": "restaurants"},
    ])

    state = _make_state(
        transactions=_make_transactions(),
        categorized_transactions=_make_categorized_transactions(),
        locale="uk",
    )
    state["triage_category_severity_map"] = {"groceries": "critical"}

    with (
        patch("app.agents.education.node.retrieve_relevant_docs", return_value=MOCK_RAG_DOCS),
        patch("app.agents.education.node.get_llm_client") as mock_llm_fn,
    ):
        mock_llm_fn.return_value.invoke.return_value = mock_response
        result = education_node(state)

    by_category = {c["category"]: c for c in result["insight_cards"]}
    assert by_category["groceries"]["severity"] == "critical"  # overridden by triage map
    assert by_category["restaurants"]["severity"] == "warning"  # LLM value preserved


def test_education_node_empty_triage_map_preserves_llm_severity():
    """When triage_category_severity_map is empty (triage failed or didn't run),
    LLM-assigned severities flow through unchanged."""
    mock_response = MagicMock()
    mock_response.content = json.dumps(MOCK_INSIGHT_CARDS)

    state = _make_state(
        transactions=_make_transactions(),
        categorized_transactions=_make_categorized_transactions(),
        locale="uk",
    )
    state["triage_category_severity_map"] = {}

    with (
        patch("app.agents.education.node.retrieve_relevant_docs", return_value=MOCK_RAG_DOCS),
        patch("app.agents.education.node.get_llm_client") as mock_llm_fn,
    ):
        mock_llm_fn.return_value.invoke.return_value = mock_response
        result = education_node(state)

    # Mock cards supply "medium" and "low" — assert they survive the override branch.
    severities = {c["severity"] for c in result["insight_cards"]}
    assert severities == {"medium", "low"}


def test_education_node_intermediate_prompt_end_to_end():
    """Education node uses intermediate prompt text when literacy_level is 'intermediate' (no mock on get_prompt)."""
    mock_response = MagicMock()
    mock_response.content = json.dumps(MOCK_INSIGHT_CARDS)

    state = _make_state(
        transactions=_make_transactions(),
        categorized_transactions=_make_categorized_transactions(),
        locale="en",
        literacy_level="intermediate",
    )

    with (
        patch("app.agents.education.node.retrieve_relevant_docs", return_value=MOCK_RAG_DOCS),
        patch("app.agents.education.node.get_llm_client") as mock_llm_fn,
    ):
        mock_llm_fn.return_value.invoke.return_value = mock_response
        result = education_node(state)

        # Verify the intermediate prompt was actually sent to the LLM
        actual_prompt = mock_llm_fn.return_value.invoke.call_args[0][0]
        assert "optimization strategies" in actual_prompt
        assert "50/30/20" in actual_prompt

    assert len(result["insight_cards"]) == 2


def test_education_node_logs_long_key_metrics_for_tuning():
    """Story 3.9: cards whose key_metric exceeds 30 chars are logged for prompt-tuning review."""
    long_metric = "₴87,582.04 (25.9% of total) vs. ₴213,238.50 finance allocation"  # 62 chars
    short_metric = "₴1,200/month"  # 12 chars
    cards_with_mixed_lengths = [
        {**MOCK_INSIGHT_CARDS[0], "key_metric": long_metric},
        {**MOCK_INSIGHT_CARDS[1], "key_metric": short_metric},
    ]
    mock_response = MagicMock()
    mock_response.content = json.dumps(cards_with_mixed_lengths)

    state = _make_state(
        transactions=_make_transactions(),
        categorized_transactions=_make_categorized_transactions(),
        locale="en",
    )

    with (
        patch("app.agents.education.node.retrieve_relevant_docs", return_value=MOCK_RAG_DOCS),
        patch("app.agents.education.node.get_llm_client") as mock_llm_fn,
        patch("app.agents.education.node.logger") as mock_logger,
    ):
        mock_llm_fn.return_value.invoke.return_value = mock_response
        education_node(state)

    info_calls = mock_logger.info.call_args_list
    long_metric_logs = [c for c in info_calls if c.args and c.args[0] == "key_metric_length_over_30"]
    assert len(long_metric_logs) == 1, (
        f"Expected exactly one key_metric_length_over_30 log (for the 62-char metric); got {len(long_metric_logs)}"
    )
    logged_extra = long_metric_logs[0].kwargs["extra"]
    assert logged_extra["length"] == len(long_metric)
    assert logged_extra["value"].startswith("₴87,582.04")


def test_education_node_logs_literacy_level():
    """Education node logs literacy_level in structured output."""
    mock_response = MagicMock()
    mock_response.content = json.dumps(MOCK_INSIGHT_CARDS)

    state = _make_state(
        transactions=_make_transactions(),
        categorized_transactions=_make_categorized_transactions(),
        locale="en",
        literacy_level="intermediate",
    )

    with (
        patch("app.agents.education.node.retrieve_relevant_docs", return_value=MOCK_RAG_DOCS),
        patch("app.agents.education.node.get_llm_client") as mock_llm_fn,
        patch("app.agents.education.node.logger") as mock_logger,
    ):
        mock_llm_fn.return_value.invoke.return_value = mock_response
        education_node(state)

    # Verify logger.info was called with literacy_level in the format string
    info_calls = mock_logger.info.call_args_list
    assert any("literacy_level" in str(c) and "intermediate" in str(c) for c in info_calls)


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
