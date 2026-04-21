"""Unit tests for the Story 11.4 description pre-pass (cash-action override)."""

from app.agents.categorization.pre_pass import classify_pre_pass


def _txn(description: str, *, id: str = "x", amount: int = -100000, mcc: int | None = None) -> dict:
    return {"id": id, "description": description, "amount": amount, "mcc": mcc}


def test_cash_withdrawal_en_matches():
    result = classify_pre_pass(_txn("Cash withdrawal Близенько", mcc=5499))
    assert result is not None
    assert result["category"] == "atm_cash"
    assert result["transaction_kind"] == "spending"
    assert result["confidence_score"] == 0.95


def test_cash_withdrawal_ua_matches():
    result = classify_pre_pass(_txn("Видача готівки Близенько", mcc=5499))
    assert result is not None
    assert result["category"] == "atm_cash"
    assert result["transaction_kind"] == "spending"


def test_otrymannya_gotivky_matches():
    result = classify_pre_pass(_txn("Отримання готівки в АТБ", mcc=5411))
    assert result is not None
    assert result["category"] == "atm_cash"


def test_non_cash_action_description_does_not_match():
    assert classify_pre_pass(_txn("Сільпо", mcc=5411)) is None


def test_cash_action_with_food_mcc_still_overrides():
    """Confirms the MCC pass bypass: MCC 5411 would normally route to groceries."""
    result = classify_pre_pass(_txn("Cash withdrawal Novus", mcc=5411))
    assert result is not None
    assert result["category"] == "atm_cash"


def test_pre_pass_output_shape():
    result = classify_pre_pass(_txn("Cash withdrawal X", id="abc-1"))
    assert result == {
        "transaction_id": "abc-1",
        "category": "atm_cash",
        "confidence_score": 0.95,
        "transaction_kind": "spending",
        "flagged": False,
        "uncategorized_reason": None,
    }


def test_case_insensitive_match():
    assert classify_pre_pass(_txn("CASH WITHDRAWAL ATB")) is not None


def test_empty_description_returns_none():
    assert classify_pre_pass(_txn("")) is None
    assert classify_pre_pass({"id": "x", "description": None, "amount": -1, "mcc": None}) is None


def test_cash_substring_without_withdrawal_does_not_match():
    """`cash` or `готівка` alone must not match (false-positive guard)."""
    assert classify_pre_pass(_txn("Готівка Маркет")) is None
    assert classify_pre_pass(_txn("Cashback reward")) is None


def test_pre_pass_confidence_is_above_default_threshold():
    """Lock the invariant that pre-pass confidence is high enough that the
    downstream flagging threshold would never flip a pre-pass result to
    `uncategorized` if it were ever routed through that loop. Guards against
    a future bump to CATEGORIZATION_CONFIDENCE_THRESHOLD silently making
    pre-pass results low-confidence on paper while node.py skips the check.
    """
    from app.core.config import settings

    result = classify_pre_pass(_txn("Cash withdrawal X"))
    assert result is not None
    assert result["confidence_score"] >= settings.CATEGORIZATION_CONFIDENCE_THRESHOLD
    assert result["flagged"] is False


def test_categorization_node_bypasses_mcc_pass_for_cash_action():
    """AC #10 integration check: `Cash withdrawal <merchant>` + MCC 5411 must
    land as `atm_cash` via pre-pass, NOT `groceries` via the MCC pass. This
    exercises the full pipeline ordering (pre-pass BEFORE MCC), not just the
    pre-pass helper in isolation — guards against a future refactor that
    accidentally moves the pre-pass after the MCC loop.
    """
    from app.agents.categorization.node import categorization_node

    state = {
        "job_id": "pre-pass-bypass-test",
        "user_id": "u",
        "upload_id": "up",
        "transactions": [
            {"id": "t1", "description": "Cash withdrawal Novus", "amount": -500000, "mcc": 5411, "date": "2025-01-01"},
            {"id": "t2", "description": "Сільпо", "amount": -20000, "mcc": 5411, "date": "2025-01-01"},
        ],
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
        "detected_subscriptions": [],
        "triage_category_severity_map": {},
    }
    result = categorization_node(state)
    by_id = {r["transaction_id"]: r for r in result["categorized_transactions"]}
    assert by_id["t1"]["category"] == "atm_cash", (
        "Cash-withdrawal narration must override MCC 5411 via pre-pass, not fall through to groceries."
    )
    assert by_id["t1"]["transaction_kind"] == "spending"
    assert by_id["t2"]["category"] == "groceries", (
        "Non-cash-action row must still reach the MCC pass and map to groceries."
    )
    assert result["total_tokens_used"] == 0, (
        "Neither row should reach the LLM pass (pre-pass handles t1; MCC handles t2)."
    )
