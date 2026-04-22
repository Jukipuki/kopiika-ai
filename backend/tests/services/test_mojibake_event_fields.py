"""Story 11.9 AC #4, #12: parser.mojibake_detected event naming + fields."""
from __future__ import annotations

import logging
import uuid
from datetime import datetime
from unittest.mock import patch

import pytest

from app.agents.ingestion.parsers.base import ParseResult, TransactionData
from app.services.format_detector import FormatDetectionResult
from app.services.parser_service import _parse_and_build_records


@pytest.fixture(autouse=True)
def _enable_app_logger_propagation():
    app_logger = logging.getLogger("app")
    prev = app_logger.propagate
    app_logger.propagate = True
    try:
        yield
    finally:
        app_logger.propagate = prev


def _format_result() -> FormatDetectionResult:
    return FormatDetectionResult(
        bank_format="monobank",
        encoding="cp1251",
        delimiter=";",
        column_count=5,
        confidence_score=1.0,
        header_row=[],
        amount_sign_convention="negative_is_outflow",
    )


def _txn(description: str, idx: int) -> TransactionData:
    return TransactionData(
        date=datetime(2026, 2, idx + 1),
        description=description,
        mcc=5812,
        amount=-100 * (idx + 1),
        balance=None,
        currency_code=980,
        raw_data={},
    )


def test_mojibake_event_renamed_and_extended(caplog):
    rows = [_txn(f"CLEAN-TXN{i}", i) for i in range(7)]
    rows.append(_txn("�" * 5 + "XYZAB", 7))
    parse_result = ParseResult(
        transactions=rows, flagged_rows=[], total_rows=8, parsed_count=8, flagged_count=0,
    )
    user_id = uuid.uuid4()
    upload_id = uuid.uuid4()

    caplog.set_level(logging.WARNING, logger="app.services.parser_service")
    with patch(
        "app.agents.ingestion.parsers.monobank.MonobankParser.parse",
        return_value=parse_result,
    ):
        _parse_and_build_records(
            user_id, upload_id, b"ignored", _format_result(), session=None
        )

    # Old name must not be used anywhere.
    assert not any(r.getMessage() == "encoding.mojibake_detected" for r in caplog.records)

    events = [r for r in caplog.records if r.getMessage() == "parser.mojibake_detected"]
    assert len(events) == 1
    rec = events[0]
    assert getattr(rec, "user_id") == str(user_id)
    assert getattr(rec, "upload_id") == str(upload_id)
    assert getattr(rec, "encoding") == "cp1251"
    assert getattr(rec, "replacement_char_rate") > 0.05
    assert getattr(rec, "transaction_count") == 8
