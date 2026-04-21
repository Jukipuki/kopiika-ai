"""Unit tests for the Story 11.3 enriched categorization prompt + matrix validation.

Covers the new prompt fields (signed amount, MCC, direction), the two-axis
instruction block, and the `_parse_llm_response` kind×category matrix check.
"""

import json

from app.agents.categorization.node import _build_prompt, _parse_llm_response


def _txn(
    *,
    id: str = "txn-1",
    description: str = "Test",
    amount: int = -10000,
    mcc: int | None = None,
) -> dict:
    return {"id": id, "description": description, "amount": amount, "mcc": mcc, "date": "2025-01-01"}


# ---------------------------------------------------------------------------
# _build_prompt content checks (AC #1, #2)
# ---------------------------------------------------------------------------

def test_prompt_includes_signed_amount_negative():
    prompt = _build_prompt([_txn(amount=-150000)])
    assert "-1500.00 UAH" in prompt


def test_prompt_includes_signed_amount_positive():
    prompt = _build_prompt([_txn(amount=150000)])
    assert "+1500.00 UAH" in prompt


def test_prompt_includes_mcc_when_present():
    prompt = _build_prompt([_txn(mcc=5411)])
    assert "MCC: 5411" in prompt


def test_prompt_includes_null_mcc():
    prompt = _build_prompt([_txn(mcc=None)])
    assert "MCC: null" in prompt


def test_prompt_includes_direction_debit():
    prompt = _build_prompt([_txn(amount=-5000)])
    assert "debit" in prompt
    # And not 'credit' for a single negative transaction line
    lines = [line for line in prompt.splitlines() if line.startswith("1.")]
    assert any("debit" in line for line in lines)


def test_prompt_includes_direction_credit():
    prompt = _build_prompt([_txn(amount=5000)])
    lines = [line for line in prompt.splitlines() if line.startswith("1.")]
    assert any("credit" in line for line in lines)


def test_prompt_includes_transaction_kind_in_return_format():
    prompt = _build_prompt([_txn()])
    assert "transaction_kind" in prompt


def test_prompt_includes_two_axis_rules():
    prompt = _build_prompt([_txn()])
    assert "transfers_p2p is ALWAYS kind=spending" in prompt
    assert "charity is ALWAYS kind=spending" in prompt
    assert "savings category requires kind=savings" in prompt
    assert "transfers category requires kind=transfer" in prompt


def test_prompt_includes_few_shot_examples():
    prompt = _build_prompt([_txn()])
    assert "Few-shot examples" in prompt
    # At least a couple of the canonical IDs should appear
    assert "ex-01" in prompt
    assert "ex-07" in prompt


def test_prompt_signature_returns_str():
    result = _build_prompt([_txn()])
    assert isinstance(result, str)


# ---------------------------------------------------------------------------
# Story 11.3a disambiguation rules (AC #1, #2, #9)
# ---------------------------------------------------------------------------

def test_prompt_includes_charity_jar_rule():
    """Rule 1 (Monobank banka jar tops ups are never savings) must appear verbatim."""
    prompt = _build_prompt([_txn()])
    assert "Поповнення «" in prompt
    assert "NEVER savings" in prompt
    assert "Поповнення депозиту" in prompt  # savings-reserved marker in the rule text


def test_prompt_includes_cash_action_rule():
    """Rule 2 (cash-action narration overrides merchant MCC) must appear verbatim."""
    prompt = _build_prompt([_txn()])
    assert "Cash withdrawal" in prompt
    assert "Видача готівки" in prompt
    assert "atm_cash" in prompt


def test_prompt_includes_fop_merchant_rule():
    """Rule 3 (ФОП/FOP with merchant MCC is a merchant, not P2P) must appear verbatim."""
    prompt = _build_prompt([_txn()])
    assert "ФОП" in prompt
    assert "LIQPAY*FOP" in prompt
    assert "transfers_p2p only when" in prompt


def test_prompt_includes_self_transfer_rule():
    """Story 11.4 AC #4: Rule 4 (self-transfer vs P2P) must appear in prompt."""
    prompt = _build_prompt([_txn()])
    assert "Переказ між власними рахунками" in prompt
    assert "Self-transfer" in prompt or "self-transfer" in prompt.lower()
    # The absence-of-personal-name signal must be spelled out.
    assert "personal full name" in prompt


def test_prompt_includes_card_color_few_shot():
    """Story 11.4 AC #5: card-color self-transfer example must be present."""
    prompt = _build_prompt([_txn()])
    assert "З Білої картки" in prompt
    assert "Конвертація UAH" in prompt or "Конвертація валют" in prompt
    assert "Переказ на картку" in prompt


def test_prompt_includes_new_few_shot_examples():
    """Three few-shot examples per new rule must appear (AC #2)."""
    prompt = _build_prompt([_txn()])
    # Rule 1 few-shots
    assert "На детектор FPV" in prompt
    assert "На Авто!" in prompt
    # Rule 2 few-shots
    assert "Cash withdrawal Близенько" in prompt
    assert "Видача готівки Близенько" in prompt
    # Rule 3 few-shots
    assert "FOP Ruban Olha Heorhii" in prompt
    assert "LIQPAY*FOP Lutsenko Ev" in prompt


# ---------------------------------------------------------------------------
# _parse_llm_response matrix validation (AC #3)
# ---------------------------------------------------------------------------

def test_parse_llm_response_kind_category_mismatch_overrides():
    """savings+income is a matrix violation → category=uncategorized, confidence=0.0."""
    txn = _txn(id="x", amount=-500)
    content = json.dumps([
        {"id": "x", "category": "savings", "transaction_kind": "income", "confidence": 0.9}
    ])
    parsed = _parse_llm_response(content, [txn])
    assert len(parsed) == 1
    entry = parsed[0]
    assert entry["category"] == "uncategorized"
    assert entry["confidence_score"] == 0.0
    # kind falls back to sign-based (negative amount → spending)
    assert entry["transaction_kind"] == "spending"


def test_parse_llm_response_valid_pair_passes_through():
    txn = _txn(id="x", amount=-500)
    content = json.dumps([
        {"id": "x", "category": "groceries", "transaction_kind": "spending", "confidence": 0.85}
    ])
    parsed = _parse_llm_response(content, [txn])
    assert len(parsed) == 1
    entry = parsed[0]
    assert entry["category"] == "groceries"
    assert entry["transaction_kind"] == "spending"
    assert entry["confidence_score"] == 0.85


def test_parse_llm_response_savings_requires_savings_kind():
    """category=savings with kind=spending violates matrix (savings→only savings kind)."""
    txn = _txn(id="x", amount=-500)
    content = json.dumps([
        {"id": "x", "category": "savings", "transaction_kind": "spending", "confidence": 0.8}
    ])
    parsed = _parse_llm_response(content, [txn])
    assert parsed[0]["category"] == "uncategorized"
    assert parsed[0]["confidence_score"] == 0.0


def test_parse_llm_response_transfers_p2p_with_spending_valid():
    """transfers_p2p+spending is allowed (P2P reduces net worth)."""
    txn = _txn(id="x", amount=-1500)
    content = json.dumps([
        {"id": "x", "category": "transfers_p2p", "transaction_kind": "spending", "confidence": 0.91}
    ])
    parsed = _parse_llm_response(content, [txn])
    assert parsed[0]["category"] == "transfers_p2p"
    assert parsed[0]["transaction_kind"] == "spending"
    assert parsed[0]["confidence_score"] == 0.91


def test_parse_llm_response_charity_with_spending_valid():
    txn = _txn(id="x", amount=-500)
    content = json.dumps([
        {"id": "x", "category": "charity", "transaction_kind": "spending", "confidence": 0.89}
    ])
    parsed = _parse_llm_response(content, [txn])
    assert parsed[0]["category"] == "charity"
    assert parsed[0]["transaction_kind"] == "spending"


def test_parse_llm_response_income_only_allows_other_or_uncategorized():
    """category=groceries with kind=income is invalid → uncategorized."""
    txn = _txn(id="x", amount=5000)
    content = json.dumps([
        {"id": "x", "category": "groceries", "transaction_kind": "income", "confidence": 0.9}
    ])
    parsed = _parse_llm_response(content, [txn])
    assert parsed[0]["category"] == "uncategorized"
    # positive amount → kind_by_sign = income
    assert parsed[0]["transaction_kind"] == "income"


def test_parse_llm_response_salary_as_income_other_valid():
    txn = _txn(id="x", amount=4500000)
    content = json.dumps([
        {"id": "x", "category": "other", "transaction_kind": "income", "confidence": 0.95}
    ])
    parsed = _parse_llm_response(content, [txn])
    assert parsed[0]["category"] == "other"
    assert parsed[0]["transaction_kind"] == "income"
    assert parsed[0]["confidence_score"] == 0.95


# ---------------------------------------------------------------------------
# H1 regression: LLM-emitted `uncategorized` must not land with high confidence
# ---------------------------------------------------------------------------

def test_prompt_does_not_offer_uncategorized_to_llm():
    """`uncategorized` is a pipeline sentinel, not part of the LLM's vocabulary."""
    prompt = _build_prompt([_txn()])
    # The enumerated category list in the prompt must not include `uncategorized`.
    # (The token may legitimately appear elsewhere — e.g., future docs — but not
    # in the comma-separated enum line.)
    enum_line = next(
        line for line in prompt.splitlines() if "groceries" in line and "restaurants" in line
    )
    assert "uncategorized" not in enum_line


def test_parse_llm_response_uncategorized_emission_is_zeroed():
    """If the model ignores the prompt and emits `uncategorized`, confidence→0 so flagging fires."""
    txn = _txn(id="x", amount=-500)
    content = json.dumps([
        {"id": "x", "category": "uncategorized", "transaction_kind": "spending", "confidence": 0.95}
    ])
    parsed = _parse_llm_response(content, [txn])
    assert parsed[0]["category"] == "uncategorized"
    assert parsed[0]["confidence_score"] == 0.0


# ---------------------------------------------------------------------------
# H2 regression: MCC pass must not hard-kind inflows as spending
# ---------------------------------------------------------------------------

def test_mcc_pass_positive_amount_defers_to_llm():
    """MCC-mapped inflow (e.g., refund at a grocery store) must not emit groceries+spending."""
    from unittest.mock import MagicMock, patch

    from app.agents.categorization.node import categorization_node

    # amount=+5000 kopiykas at MCC 5411 (groceries) — a refund.
    # MCC→groceries + kind_by_sign(income) is matrix-invalid → defer to LLM.
    refund_txn = {"id": "r1", "description": "Refund", "amount": 5000, "mcc": 5411, "date": "2025-01-01"}
    state = {
        "job_id": "j", "user_id": "u", "upload_id": "up",
        "transactions": [refund_txn], "categorized_transactions": [],
        "errors": [], "step": "categorization", "total_tokens_used": 0,
        "locale": "uk", "insight_cards": [], "literacy_level": "beginner",
        "completed_nodes": [], "failed_node": None, "pattern_findings": [],
        "detected_subscriptions": [], "triage_category_severity_map": {},
    }

    llm_payload = [{"id": "r1", "category": "other", "transaction_kind": "income", "confidence": 0.9}]
    mock_response = MagicMock()
    mock_response.content = json.dumps(llm_payload)
    mock_response.usage_metadata = {"total_tokens": 10}
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = mock_response
    mock_llm.model = "test-model"

    with patch("app.agents.categorization.node.get_llm_client", return_value=mock_llm):
        result = categorization_node(state)

    entry = result["categorized_transactions"][0]
    assert entry["category"] == "other"
    assert entry["transaction_kind"] == "income"
    # Crucially, the LLM was consulted (not short-circuited to groceries/spending by MCC pass).
    mock_llm.invoke.assert_called_once()


def test_mcc_pass_negative_amount_emits_spending():
    """Negative amount + MCC-mapped category → kind=spending via kind_by_sign (matrix-valid)."""
    from unittest.mock import MagicMock, patch

    from app.agents.categorization.node import categorization_node

    spend_txn = {"id": "s1", "description": "ATB", "amount": -34250, "mcc": 5411, "date": "2025-01-01"}
    state = {
        "job_id": "j", "user_id": "u", "upload_id": "up",
        "transactions": [spend_txn], "categorized_transactions": [],
        "errors": [], "step": "categorization", "total_tokens_used": 0,
        "locale": "uk", "insight_cards": [], "literacy_level": "beginner",
        "completed_nodes": [], "failed_node": None, "pattern_findings": [],
        "detected_subscriptions": [], "triage_category_severity_map": {},
    }

    mock_llm = MagicMock()
    with patch("app.agents.categorization.node.get_llm_client", return_value=mock_llm):
        result = categorization_node(state)

    entry = result["categorized_transactions"][0]
    assert entry["category"] == "groceries"
    assert entry["transaction_kind"] == "spending"
    # LLM must NOT have been called — MCC pass handled it.
    mock_llm.invoke.assert_not_called()
