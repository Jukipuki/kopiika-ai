"""Description-based pre-pass for the categorization pipeline (Story 11.4).

Runs BEFORE the MCC pass. When a pre-pass rule matches, the MCC pass and LLM
pass are both skipped — the pre-pass result is authoritative.

Rule inventory is deliberately narrow (one rule). Any future pre-pass rule must
be justified by a demonstrated failure cluster that prompt/MCC approaches cannot
handle; see Story 11.4 Dev Notes for the rationale.
"""

import re

_CASH_ACTION_RE = re.compile(
    r"\b(cash\s+withdrawal|видача\s+готівки|отримання\s+готівки)\b",
    re.IGNORECASE,
)


def classify_pre_pass(txn: dict) -> dict | None:
    """Return a categorized result dict if a pre-pass rule matches, else None.

    Rule A (cash-action narration): description names a cash-withdrawal action
    → atm_cash regardless of MCC. Cashback-at-till commonly arrives with
    food/retail MCCs (5499, 5411); the narrative overrides.
    """
    description = (txn.get("description") or "").strip()
    if _CASH_ACTION_RE.search(description):
        return {
            "transaction_id": txn["id"],
            "category": "atm_cash",
            "confidence_score": 0.95,
            "transaction_kind": "spending",
            "flagged": False,
            "uncategorized_reason": None,
        }
    return None
