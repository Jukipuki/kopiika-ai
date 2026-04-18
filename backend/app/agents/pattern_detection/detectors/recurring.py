"""Recurring subscription detector for Story 8.2.

Pure Python — no LLM. Given a list of transactions, identify merchants that
are charged on a regular monthly or annual cadence with consistent amounts,
and emit one subscription dict per detected recurring charge.

All amounts are integer kopiykas; negative amounts are debits (spending).
Income (positive amounts) is excluded.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from datetime import date

_MONTHLY_GAP_MIN_DAYS = 25
_MONTHLY_GAP_MAX_DAYS = 35
_ANNUAL_GAP_MIN_DAYS = 358
_ANNUAL_GAP_MAX_DAYS = 372
_AMOUNT_TOLERANCE = 0.05
_MONTHLY_INACTIVITY_DAYS = 35
_ANNUAL_INACTIVITY_DAYS = 375

_TRAILING_DIGITS_RE = re.compile(r"\s+\d+$")
_LEADING_PREFIXES = ("оплата", "переказ", "transfer", "commission", "комісія")


def _normalize_merchant(description: str | None) -> str:
    """Normalize a merchant description into a bucket key.

    Lowercase, strip whitespace, strip trailing standalone digits, and strip
    known leading noise prefixes. Keeps it simple — no fuzzy matching.
    """
    if not description:
        return ""
    text = description.strip().lower()
    # Strip leading prefixes iteratively. Requires a non-alphanumeric boundary
    # after the prefix so "transferwise" is NOT stripped to "wise".
    changed = True
    while changed:
        changed = False
        for prefix in _LEADING_PREFIXES:
            if not text.startswith(prefix):
                continue
            boundary_idx = len(prefix)
            if boundary_idx < len(text) and text[boundary_idx].isalnum():
                continue
            text = text[boundary_idx:].lstrip(" :-_")
            changed = True
    text = _TRAILING_DIGITS_RE.sub("", text)
    return text.strip()


def _display_name(raws: list[str]) -> str:
    """Pick a human-friendly display name from the raw descriptions in a group.

    Preserves original casing from the source bank statement rather than the
    lowercase bucket key — users expect to see "Netflix UA", not "netflix ua".
    Uses the most frequent raw form; ties break on first occurrence.
    """
    cleaned = [_TRAILING_DIGITS_RE.sub("", r.strip()) for r in raws if r]
    if not cleaned:
        return ""
    counts = Counter(cleaned)
    top_count = max(counts.values())
    for value in cleaned:
        if counts[value] == top_count:
            return value
    return cleaned[0]


def _parse_date(value) -> date | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _classify_gap(gap_days: int) -> str | None:
    if _MONTHLY_GAP_MIN_DAYS <= gap_days <= _MONTHLY_GAP_MAX_DAYS:
        return "monthly"
    if _ANNUAL_GAP_MIN_DAYS <= gap_days <= _ANNUAL_GAP_MAX_DAYS:
        return "annual"
    return None


def _classify_cadence(gaps: list[int]) -> str | None:
    """Classify a merchant's cadence from its inter-transaction gaps.

    Rules:
      * Every gap must fall into the same bucket (monthly or annual). A single
        off-bucket gap disqualifies the merchant.
      * At least one gap must qualify (i.e. ≥ 1 transaction pair at cadence).
      * For merchants with 3+ transactions (≥ 2 gaps), the two-consecutive
        guard is naturally enforced because all gaps must agree.

    Returns 'monthly', 'annual', or None.
    """
    if not gaps:
        return None
    buckets = [_classify_gap(g) for g in gaps]
    distinct = {b for b in buckets if b is not None}
    if len(distinct) != 1:
        return None
    if any(b is None for b in buckets):
        return None
    return distinct.pop()


def _is_amount_consistent(amounts: list[int]) -> bool:
    mean = sum(amounts) / len(amounts)
    if mean == 0:
        return False
    for amt in amounts:
        if abs(amt - mean) / mean > _AMOUNT_TOLERANCE:
            return False
    return True


def _inactivity_for_monthly(today: date, last_charge: date) -> tuple[bool, int | None]:
    delta_days = (today - last_charge).days
    if delta_days <= _MONTHLY_INACTIVITY_DAYS:
        return True, None
    # Count billing cycles elapsed (e.g. 40 days past last charge = 1 missed).
    return False, max(1, delta_days // 30)


def _inactivity_for_annual(today: date, last_charge: date) -> tuple[bool, int | None]:
    delta_days = (today - last_charge).days
    if delta_days <= _ANNUAL_INACTIVITY_DAYS:
        return True, None
    return False, max(1, delta_days // 365)


def detect_subscriptions(
    transactions: list[dict],
    today: date | None = None,
) -> list[dict]:
    """Detect recurring monthly/annual subscriptions from transaction history.

    Parameters
    ----------
    transactions:
        Raw transaction dicts (id/date/description/mcc/amount). Only spending
        transactions (amount < 0) are considered.
    today:
        Reference date for inactivity checks. Defaults to ``date.today()``.
        Injectable for deterministic testing.
    """
    reference_date = today if today is not None else date.today()

    # Group spending transactions by normalized merchant key. Keep the raw
    # description alongside so the output can surface the original casing
    # instead of the lowercased bucket key.
    by_merchant: dict[str, list[tuple[date, int, str]]] = defaultdict(list)
    for txn in transactions:
        amount = txn.get("amount", 0)
        if amount >= 0:
            continue
        parsed = _parse_date(txn.get("date"))
        if parsed is None:
            continue
        raw_description = txn.get("description") or ""
        key = _normalize_merchant(raw_description)
        if not key:
            continue
        by_merchant[key].append((parsed, abs(amount), raw_description))

    results: list[dict] = []
    for merchant_key, entries in by_merchant.items():
        if len(entries) < 2:
            continue
        entries.sort(key=lambda pair: pair[0])
        dates_sorted = [d for d, _, _ in entries]
        amounts_sorted = [a for _, a, _ in entries]
        raw_descriptions = [r for _, _, r in entries]
        gaps = [
            (dates_sorted[i] - dates_sorted[i - 1]).days
            for i in range(1, len(dates_sorted))
        ]

        cadence = _classify_cadence(gaps)
        if cadence is None:
            continue
        if not _is_amount_consistent(amounts_sorted):
            continue

        mean_amount = sum(amounts_sorted) // len(amounts_sorted)
        last_charge_date = dates_sorted[-1]
        if cadence == "monthly":
            is_active, months_inactive = _inactivity_for_monthly(
                reference_date, last_charge_date
            )
            estimated_monthly_cost = mean_amount
        else:
            is_active, months_inactive = _inactivity_for_annual(
                reference_date, last_charge_date
            )
            estimated_monthly_cost = mean_amount // 12

        display = _display_name(raw_descriptions) or merchant_key
        results.append({
            "merchant_name": display,
            "estimated_monthly_cost_kopiykas": estimated_monthly_cost,
            "billing_frequency": cadence,
            "last_charge_date": last_charge_date.isoformat(),
            "is_active": is_active,
            "months_with_no_activity": months_inactive,
        })

    results.sort(key=lambda r: r["merchant_name"].lower())
    return results
