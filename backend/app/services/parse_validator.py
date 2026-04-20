"""Post-parse validation layer for ingested statement rows.

Applies semantic validity checks to rows already produced by a parser and
classifies each row as accepted, rejected, or warned. Also detects the
wholesale-duplicate pattern that indicates a corrupt export.
"""
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, timedelta

from app.agents.ingestion.parsers.base import FlaggedRow, TransactionData

_DUPLICATE_RATE_THRESHOLD = 0.20
_DATE_LOOKBACK_YEARS = 5


@dataclass
class ValidationResult:
    accepted: list[TransactionData] = field(default_factory=list)
    rejected_rows: list[FlaggedRow] = field(default_factory=list)
    warnings: list[FlaggedRow] = field(default_factory=list)
    wholesale_rejected: bool = False
    wholesale_rejection_reason: str | None = None


def _row_date(txn: TransactionData) -> date:
    return txn.date.date() if hasattr(txn.date, "date") else txn.date


def validate_parsed_rows(
    rows: list[TransactionData],
    amount_sign_convention: str | None = None,
    today: date | None = None,
) -> ValidationResult:
    """Validate a parser's output row-by-row.

    Per-row rules reject rows with unusable data (`date_out_of_range`,
    `zero_or_null_amount`, `no_identifying_info`). Sign-convention
    mismatches are persisted as warnings, not rejections. A > 20%
    duplicate rate triggers wholesale rejection of the entire output —
    a heuristic for corrupt exports.
    """
    today = today or date.today()
    try:
        earliest = today.replace(year=today.year - _DATE_LOOKBACK_YEARS)
    except ValueError:
        # Feb 29 in a leap year: year - N is not leap — fall back to Feb 28.
        earliest = today.replace(year=today.year - _DATE_LOOKBACK_YEARS, day=28)
    latest = today + timedelta(days=1)

    if rows:
        key_counts = Counter(
            (r.description, r.amount, _row_date(r))
            for r in rows
        )
        most_common_count = key_counts.most_common(1)[0][1]
        # Guard: a single row (count=1) trivially hits 100% but is not a "duplicate".
        # Require at least 2 identical rows before considering the corpus suspicious.
        if most_common_count > 1 and most_common_count / len(rows) > _DUPLICATE_RATE_THRESHOLD:
            return ValidationResult(
                wholesale_rejected=True,
                wholesale_rejection_reason="suspicious_duplicate_rate",
            )

    result = ValidationResult()
    for idx, txn in enumerate(rows):
        row_num = idx + 1

        txn_date = _row_date(txn)
        if not (earliest <= txn_date <= latest):
            result.rejected_rows.append(
                FlaggedRow(row_number=row_num, raw_data=txn.raw_data, reason="date_out_of_range")
            )
            continue

        if txn.amount == 0:
            result.rejected_rows.append(
                FlaggedRow(row_number=row_num, raw_data=txn.raw_data, reason="zero_or_null_amount")
            )
            continue

        has_description = bool(txn.description and txn.description.strip())
        has_identifier = txn.mcc is not None
        if not has_description and not has_identifier:
            result.rejected_rows.append(
                FlaggedRow(row_number=row_num, raw_data=txn.raw_data, reason="no_identifying_info")
            )
            continue

        if amount_sign_convention == "positive_is_income" and txn.amount < 0:
            result.warnings.append(
                FlaggedRow(row_number=row_num, raw_data=txn.raw_data, reason="sign_convention_mismatch")
            )
        elif amount_sign_convention == "negative_is_outflow" and txn.amount > 0:
            # Positive amount under negative_is_outflow convention may be legitimate income;
            # the rule is a soft cross-check — flag but do not reject.
            result.warnings.append(
                FlaggedRow(row_number=row_num, raw_data=txn.raw_data, reason="sign_convention_mismatch")
            )

        result.accepted.append(txn)

    return result
