"""Statistical pattern detectors for Story 8.1.

Pure Python — no LLM calls. Given raw transactions + categorization results,
emit finding dicts describing month-over-month trends, single-transaction
anomalies, and intra-period category distribution.

All amounts are integer kopiykas; negative amounts are debits (spending).
Income (positive amounts) is excluded from every detector.
"""

from __future__ import annotations

import math
from collections import defaultdict
from datetime import date
from typing import Iterable

_TREND_THRESHOLD_PERCENT = 10.0
_ANOMALY_STDDEV_MULT = 2.0
_ANOMALY_MIN_SAMPLE = 5


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def _period_bounds(year: int, month: int) -> tuple[date, date]:
    """Return (first_day, last_day) for the given calendar month."""
    first = date(year, month, 1)
    if month == 12:
        last = date(year, 12, 31)
    else:
        last = date.fromordinal(date(year, month + 1, 1).toordinal() - 1)
    return first, last


def _join_categorized(
    transactions: list[dict],
    categorized: list[dict],
) -> list[tuple[dict, str]]:
    """Join raw transactions with their category, filtering out uncategorized spend.

    Returns list of (transaction, category) tuples for spending transactions
    (amount < 0) whose category is known and not 'uncategorized'.
    """
    cat_by_id = {c["transaction_id"]: c.get("category", "other") for c in categorized}
    result: list[tuple[dict, str]] = []
    for txn in transactions:
        amount = txn.get("amount", 0)
        if amount >= 0:
            continue  # skip income and zero-value entries
        category = cat_by_id.get(txn.get("id"))
        if not category or category == "uncategorized":
            continue
        result.append((txn, category))
    return result


def _group_by_month_category(
    joined: Iterable[tuple[dict, str]],
) -> dict[tuple[int, int], dict[str, int]]:
    """Group spending totals by (year, month) → {category: sum_abs_kopiykas}."""
    totals: dict[tuple[int, int], dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for txn, category in joined:
        parsed = _parse_date(txn.get("date"))
        if parsed is None:
            continue
        key = (parsed.year, parsed.month)
        totals[key][category] += abs(txn["amount"])
    return totals


def detect_trends(
    transactions: list[dict],
    categorized: list[dict],
) -> list[dict]:
    """Month-over-month category spending deltas.

    Emits a finding dict per category where |change_percent| >= 10 between the
    most recent month and the preceding one. Returns [] if fewer than two
    distinct months are present.
    """
    joined = _join_categorized(transactions, categorized)
    by_month = _group_by_month_category(joined)
    if len(by_month) < 2:
        return []

    months_sorted = sorted(by_month.keys())
    baseline_key = months_sorted[-2]
    current_key = months_sorted[-1]
    baseline = by_month[baseline_key]
    current = by_month[current_key]

    baseline_start, baseline_end = _period_bounds(*baseline_key)
    current_start, current_end = _period_bounds(*current_key)

    findings: list[dict] = []
    categories = set(baseline) & set(current)
    for category in sorted(categories):
        baseline_amt = baseline[category]
        current_amt = current[category]
        if baseline_amt == 0:
            continue
        change_percent = (current_amt - baseline_amt) / baseline_amt * 100
        if abs(change_percent) < _TREND_THRESHOLD_PERCENT:
            continue
        findings.append({
            "pattern_type": "trend",
            "category": category,
            "period_start": baseline_start.isoformat(),
            "period_end": current_end.isoformat(),
            "baseline_amount_kopiykas": baseline_amt,
            "current_amount_kopiykas": current_amt,
            "change_percent": round(change_percent, 2),
            "finding_json": {
                "baseline_period": {
                    "year": baseline_key[0],
                    "month": baseline_key[1],
                    "start": baseline_start.isoformat(),
                    "end": baseline_end.isoformat(),
                },
                "current_period": {
                    "year": current_key[0],
                    "month": current_key[1],
                    "start": current_start.isoformat(),
                    "end": current_end.isoformat(),
                },
                "direction": "up" if change_percent > 0 else "down",
            },
        })
    return findings


def detect_anomalies(
    transactions: list[dict],
    categorized: list[dict],
) -> list[dict]:
    """Per-category outlier detection via mean + 2·stddev threshold.

    Requires at least 5 spending transactions in a category to compute stddev.
    Emits a finding per outlier transaction.
    """
    joined = _join_categorized(transactions, categorized)
    by_category: dict[str, list[dict]] = defaultdict(list)
    for txn, category in joined:
        by_category[category].append(txn)

    findings: list[dict] = []
    for category, txns in by_category.items():
        if len(txns) < _ANOMALY_MIN_SAMPLE:
            continue
        amounts = [abs(t["amount"]) for t in txns]
        n = len(amounts)
        mean = sum(amounts) / n
        variance = sum((a - mean) ** 2 for a in amounts) / n
        stddev = math.sqrt(variance)
        if stddev == 0:
            continue
        threshold = mean + _ANOMALY_STDDEV_MULT * stddev
        for txn in txns:
            amount = abs(txn["amount"])
            if amount <= threshold:
                continue
            txn_date = _parse_date(txn.get("date"))
            findings.append({
                "pattern_type": "anomaly",
                "category": category,
                "period_start": txn_date.isoformat() if txn_date else None,
                "period_end": txn_date.isoformat() if txn_date else None,
                "baseline_amount_kopiykas": None,
                "current_amount_kopiykas": amount,
                "change_percent": None,
                "finding_json": {
                    "transaction_id": txn.get("id"),
                    "amount_kopiykas": amount,
                    "category_mean_kopiykas": round(mean),
                    "category_stddev_kopiykas": round(stddev),
                },
            })
    return findings


def detect_distribution(
    transactions: list[dict],
    categorized: list[dict],
) -> list[dict]:
    """Share-of-total-spend per category for the current calendar month.

    The current period is inferred from the data (latest month present). Every
    category with spend in that period is emitted as a 'distribution' finding.
    """
    joined = _join_categorized(transactions, categorized)
    by_month = _group_by_month_category(joined)
    if not by_month:
        return []

    current_key = max(by_month.keys())
    current = by_month[current_key]
    total = sum(current.values())
    if total == 0:
        return []

    start_date, end_date = _period_bounds(*current_key)
    start_iso = start_date.isoformat()
    end_iso = end_date.isoformat()

    ranked = sorted(current.items(), key=lambda kv: kv[1], reverse=True)
    findings: list[dict] = []
    for rank, (category, amount) in enumerate(ranked, start=1):
        share_percent = amount / total * 100
        findings.append({
            "pattern_type": "distribution",
            "category": category,
            "period_start": start_iso,
            "period_end": end_iso,
            "baseline_amount_kopiykas": None,
            "current_amount_kopiykas": amount,
            "change_percent": None,
            "finding_json": {
                "share_percent": round(share_percent, 2),
                "total_kopiykas": total,
                "rank": rank,
            },
        })
    return findings
