"""Unit tests for parse_validator service (Story 11.5)."""
from datetime import date, datetime

import pytest

from app.agents.ingestion.parsers.base import TransactionData
from app.services.parse_validator import validate_parsed_rows


def _txn(
    *,
    date_value: datetime | date = datetime(2026, 1, 15),
    description: str = "COFFEE",
    mcc: int | None = 5812,
    amount: int = -10000,
    raw: dict | None = None,
) -> TransactionData:
    return TransactionData(
        date=date_value,
        description=description,
        mcc=mcc,
        amount=amount,
        balance=None,
        currency_code=980,
        raw_data=raw if raw is not None else {"seed": description},
    )


class TestPerRowRules:
    def test_accepts_valid_row(self):
        result = validate_parsed_rows([_txn()], today=date(2026, 4, 20))
        assert len(result.accepted) == 1
        assert result.rejected_rows == []
        assert result.warnings == []
        assert result.wholesale_rejected is False

    def test_rejects_date_too_old(self):
        # > 5 years before today
        old = _txn(date_value=datetime(2020, 1, 1))
        result = validate_parsed_rows([old], today=date(2026, 4, 20))
        assert len(result.accepted) == 0
        assert len(result.rejected_rows) == 1
        assert result.rejected_rows[0].reason == "date_out_of_range"
        assert result.rejected_rows[0].row_number == 1

    def test_rejects_date_in_future(self):
        # > today + 1 day
        future = _txn(date_value=datetime(2027, 1, 1))
        result = validate_parsed_rows([future], today=date(2026, 4, 20))
        assert len(result.rejected_rows) == 1
        assert result.rejected_rows[0].reason == "date_out_of_range"

    def test_accepts_date_within_bounds(self):
        # Exactly the earliest and the latest boundary
        earliest = _txn(date_value=datetime(2021, 4, 20))  # today - 5y
        latest = _txn(date_value=datetime(2026, 4, 21))    # today + 1 day
        result = validate_parsed_rows([earliest, latest], today=date(2026, 4, 20))
        assert len(result.accepted) == 2
        assert result.rejected_rows == []

    def test_rejects_zero_amount(self):
        zero = _txn(amount=0)
        result = validate_parsed_rows([zero], today=date(2026, 4, 20))
        assert len(result.rejected_rows) == 1
        assert result.rejected_rows[0].reason == "zero_or_null_amount"

    def test_rejects_no_description_and_no_mcc(self):
        row = _txn(description="", mcc=None)
        result = validate_parsed_rows([row], today=date(2026, 4, 20))
        assert len(result.rejected_rows) == 1
        assert result.rejected_rows[0].reason == "no_identifying_info"

    def test_rejects_whitespace_only_description_without_mcc(self):
        row = _txn(description="   ", mcc=None)
        result = validate_parsed_rows([row], today=date(2026, 4, 20))
        assert len(result.rejected_rows) == 1
        assert result.rejected_rows[0].reason == "no_identifying_info"

    def test_accepts_row_with_only_mcc(self):
        row = _txn(description="", mcc=5812)
        result = validate_parsed_rows([row], today=date(2026, 4, 20))
        assert len(result.accepted) == 1

    def test_accepts_row_with_only_description(self):
        row = _txn(description="UNKNOWN MERCHANT", mcc=None)
        result = validate_parsed_rows([row], today=date(2026, 4, 20))
        assert len(result.accepted) == 1


class TestSignConvention:
    def test_warns_on_negative_under_positive_is_income(self):
        row = _txn(amount=-1000)
        result = validate_parsed_rows(
            [row], amount_sign_convention="positive_is_income", today=date(2026, 4, 20)
        )
        assert len(result.accepted) == 1
        assert len(result.warnings) == 1
        assert result.warnings[0].reason == "sign_convention_mismatch"

    def test_warns_on_positive_under_negative_is_outflow(self):
        row = _txn(amount=1000)
        result = validate_parsed_rows(
            [row], amount_sign_convention="negative_is_outflow", today=date(2026, 4, 20)
        )
        assert len(result.accepted) == 1
        assert len(result.warnings) == 1
        assert result.warnings[0].reason == "sign_convention_mismatch"

    def test_no_warning_when_convention_is_none(self):
        row = _txn(amount=1000)
        result = validate_parsed_rows(
            [row], amount_sign_convention=None, today=date(2026, 4, 20)
        )
        assert len(result.warnings) == 0


class TestWholesaleRejection:
    def test_rejects_wholesale_when_duplicate_rate_exceeds_threshold(self):
        # 6 of 20 rows (30%) share the same (description, amount, date)
        rows = [
            _txn(description="DUP", amount=-100, date_value=datetime(2026, 1, 1))
            for _ in range(6)
        ] + [
            _txn(description=f"U{i}", amount=-200 - i, date_value=datetime(2026, 1, 2))
            for i in range(14)
        ]
        result = validate_parsed_rows(rows, today=date(2026, 4, 20))
        assert result.wholesale_rejected is True
        assert result.wholesale_rejection_reason == "suspicious_duplicate_rate"
        assert result.accepted == []
        assert result.rejected_rows == []

    def test_does_not_reject_wholesale_below_threshold(self):
        # 4 of 20 = 20%, NOT > 20%
        rows = [
            _txn(description="DUP", amount=-100, date_value=datetime(2026, 1, 1))
            for _ in range(4)
        ] + [
            _txn(description=f"U{i}", amount=-200 - i, date_value=datetime(2026, 1, 2))
            for i in range(16)
        ]
        result = validate_parsed_rows(rows, today=date(2026, 4, 20))
        assert result.wholesale_rejected is False
        assert len(result.accepted) == 20

    def test_empty_rows_do_not_trigger_wholesale(self):
        result = validate_parsed_rows([], today=date(2026, 4, 20))
        assert result.wholesale_rejected is False
        assert result.accepted == []


class TestDateBoundary:
    def test_leap_day_today_does_not_crash(self):
        # Feb 29 on a leap year — today.year - 5 is not leap. Must not raise.
        leap_today = date(2024, 2, 29)
        row = _txn(date_value=datetime(2023, 6, 1))
        result = validate_parsed_rows([row], today=leap_today)
        assert len(result.accepted) == 1


class TestRowNumbering:
    def test_rejected_row_numbers_are_one_based(self):
        rows = [
            _txn(description="A", amount=-1000),
            _txn(description="B", amount=0),  # rejected
            _txn(description="C", amount=-2000),
            _txn(description="", mcc=None, amount=-3000),  # rejected
        ]
        result = validate_parsed_rows(rows, today=date(2026, 4, 20))
        nums = sorted(r.row_number for r in result.rejected_rows)
        assert nums == [2, 4]
