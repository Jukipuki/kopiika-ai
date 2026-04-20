"""Integration tests for parser_service + validation layer (Story 11.5).

Exercises `_parse_and_build_records()` end-to-end by stubbing a parser's
`ParseResult` with rows that trip each validation rule.
"""
import uuid
from datetime import datetime
from unittest.mock import patch

import pytest

from app.agents.ingestion.parsers.base import FlaggedRow, ParseResult, TransactionData
from app.services.format_detector import FormatDetectionResult
from app.services.parser_service import (
    WholesaleRejectionError,
    _parse_and_build_records,
)


def _format_result(bank: str = "monobank") -> FormatDetectionResult:
    return FormatDetectionResult(
        bank_format=bank,
        encoding="utf-8",
        delimiter=";",
        column_count=5,
        confidence_score=1.0,
        header_row=[],
        amount_sign_convention="negative_is_outflow" if bank != "unknown" else None,
    )


def _txn(
    *,
    date: datetime = datetime(2026, 1, 15),
    description: str = "COFFEE",
    mcc: int | None = 5812,
    amount: int = -10000,
) -> TransactionData:
    return TransactionData(
        date=date,
        description=description,
        mcc=mcc,
        amount=amount,
        balance=None,
        currency_code=980,
        raw_data={"seed": description},
    )


def _run_with_parsed(rows, flagged_rows=None):
    parse_result = ParseResult(
        transactions=rows,
        flagged_rows=flagged_rows or [],
        total_rows=len(rows) + len(flagged_rows or []),
        parsed_count=len(rows),
        flagged_count=len(flagged_rows or []),
    )
    user_id = uuid.uuid4()
    upload_id = uuid.uuid4()
    with patch("app.agents.ingestion.parsers.monobank.MonobankParser.parse", return_value=parse_result):
        return _parse_and_build_records(user_id, upload_id, b"ignored", _format_result())


class TestParserServiceValidation:
    def test_valid_rows_pass_through(self):
        rows = [
            _txn(description=f"TXN-{i}", amount=-100 * (i + 1), date=datetime(2026, 2, i + 1))
            for i in range(5)
        ]
        txns, flagged, result = _run_with_parsed(rows)
        assert len(txns) == 5
        assert flagged == []
        assert result.validation_rejected_count == 0
        assert result.validation_warnings_count == 0
        assert result.rejected_rows == []

    def test_date_out_of_range_rejected(self):
        rows = [
            _txn(description="OLD", date=datetime(2015, 1, 1)),  # > 5y ago
            _txn(description="GOOD", date=datetime(2026, 1, 1)),
        ]
        txns, flagged, result = _run_with_parsed(rows)
        assert len(txns) == 1
        assert txns[0].description == "GOOD"
        assert result.validation_rejected_count == 1
        assert result.rejected_rows[0]["reason"] == "date_out_of_range"
        assert len(flagged) == 1

    def test_zero_amount_rejected(self):
        rows = [
            _txn(description="ZERO", amount=0),
            _txn(description="GOOD"),
        ]
        _, flagged, result = _run_with_parsed(rows)
        assert result.validation_rejected_count == 1
        assert result.rejected_rows[0]["reason"] == "zero_or_null_amount"
        assert flagged[0].reason == "zero_or_null_amount"

    def test_no_identifying_info_rejected(self):
        rows = [
            _txn(description="", mcc=None),
            _txn(description="GOOD"),
        ]
        _, _, result = _run_with_parsed(rows)
        assert result.validation_rejected_count == 1
        assert result.rejected_rows[0]["reason"] == "no_identifying_info"

    def test_sign_convention_warning_is_persisted_not_rejected(self):
        # negative_is_outflow convention → positive amount triggers warning only
        rows = [
            _txn(description="INFLOW", amount=500),
            _txn(description="OUTFLOW", amount=-500),
        ]
        txns, _, result = _run_with_parsed(rows)
        # Both persist — warning doesn't block persistence
        assert len(txns) == 2
        assert result.validation_rejected_count == 0
        assert result.validation_warnings_count == 1
        assert result.warnings[0]["reason"] == "sign_convention_mismatch"

    def test_wholesale_rejection_raises(self):
        # 5 of 10 (50%) identical rows trip the >20% threshold
        duplicates = [
            _txn(description="SAME", amount=-100, date=datetime(2026, 1, 1))
            for _ in range(5)
        ]
        uniques = [
            _txn(description=f"U{i}", amount=-200 - i, date=datetime(2026, 1, 2))
            for i in range(5)
        ]
        with pytest.raises(WholesaleRejectionError) as excinfo:
            _run_with_parsed(duplicates + uniques)
        assert excinfo.value.reason == "suspicious_duplicate_rate"

    def test_parser_flagged_rows_preserved_alongside_validation_rejections(self):
        rows = [_txn(description="GOOD"), _txn(amount=0, description="ZERO")]
        parser_flagged = [FlaggedRow(row_number=99, raw_data={"raw": "malformed"}, reason="malformed_row")]
        parse_result = ParseResult(
            transactions=rows,
            flagged_rows=parser_flagged,
            total_rows=3,
            parsed_count=2,
            flagged_count=1,
        )
        user_id = uuid.uuid4()
        upload_id = uuid.uuid4()
        with patch(
            "app.agents.ingestion.parsers.monobank.MonobankParser.parse",
            return_value=parse_result,
        ):
            _, flagged_records, result = _parse_and_build_records(
                user_id, upload_id, b"ignored", _format_result()
            )
        reasons = {fr.reason for fr in flagged_records}
        assert reasons == {"malformed_row", "zero_or_null_amount"}
        # flagged_count in the result reflects parser + validator rejections
        assert result.flagged_count == 2

    def test_mojibake_detected_when_descriptions_have_replacement_chars(self):
        # 8 descriptions × 10 chars (=80 chars total), 5 U+FFFD → 6.25% > 5%
        rows = [
            _txn(description=f"CLEAN-TXN{i}", amount=-100 * (i + 1), date=datetime(2026, 2, i + 1))
            for i in range(7)
        ]
        rows.append(
            _txn(
                description="\ufffd" * 5 + "XYZAB",
                amount=-999,
                date=datetime(2026, 2, 9),
            )
        )
        txns, _, result = _run_with_parsed(rows)
        assert len(txns) == 8
        assert result.mojibake_detected is True
        assert result.mojibake_replacement_rate > 0.05

    def test_mojibake_not_detected_for_clean_utf8(self):
        rows = [_txn(description=f"CLEAN-{i}", date=datetime(2026, 3, i + 1)) for i in range(3)]
        _, _, result = _run_with_parsed(rows)
        assert result.mojibake_detected is False
        assert result.mojibake_replacement_rate == 0.0

    def test_rejected_rows_payload_shape(self):
        rows = [_txn(description="", mcc=None), _txn(description="GOOD")]
        _, _, result = _run_with_parsed(rows)
        payload = result.rejected_rows[0]
        assert set(payload.keys()) == {"row_number", "reason", "raw_row"}
        assert isinstance(payload["raw_row"], dict)
