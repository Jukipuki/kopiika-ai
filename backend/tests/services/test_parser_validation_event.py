"""Story 11.9 AC #3, #12: parser.validation_rejected event emission.

Asserts one structured log event per rejected row with the spec §9 field set.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime
from unittest.mock import patch

import pytest

from app.agents.ingestion.parsers.base import ParseResult, TransactionData


@pytest.fixture(autouse=True)
def _enable_app_logger_propagation():
    app_logger = logging.getLogger("app")
    prev = app_logger.propagate
    app_logger.propagate = True
    try:
        yield
    finally:
        app_logger.propagate = prev
from app.services.format_detector import FormatDetectionResult  # noqa: E402
from app.services.parser_service import _parse_and_build_records  # noqa: E402


def _format_result() -> FormatDetectionResult:
    return FormatDetectionResult(
        bank_format="monobank",
        encoding="utf-8",
        delimiter=";",
        column_count=5,
        confidence_score=1.0,
        header_row=[],
        amount_sign_convention="negative_is_outflow",
    )


def _txn(*, description: str, amount: int, date: datetime, mcc: int | None = 5812) -> TransactionData:
    return TransactionData(
        date=date,
        description=description,
        mcc=mcc,
        amount=amount,
        balance=None,
        currency_code=980,
        raw_data={"seed": description},
    )


def test_validation_rejected_event_emitted_per_row(caplog):
    # Two rows with zero amount → both should be rejected and emit events.
    rows = [
        _txn(description="BAD-1", amount=0, date=datetime(2026, 2, 1)),
        _txn(description="BAD-2", amount=0, date=datetime(2026, 2, 2)),
        _txn(description="GOOD", amount=-100, date=datetime(2026, 2, 3)),
    ]
    parse_result = ParseResult(
        transactions=rows,
        flagged_rows=[],
        total_rows=3,
        parsed_count=3,
        flagged_count=0,
    )
    user_id = uuid.uuid4()
    upload_id = uuid.uuid4()

    caplog.set_level(logging.INFO, logger="app.services.parser_service")
    with patch(
        "app.agents.ingestion.parsers.monobank.MonobankParser.parse",
        return_value=parse_result,
    ):
        _parse_and_build_records(
            user_id, upload_id, b"ignored", _format_result(), session=None
        )

    events = [r for r in caplog.records if r.getMessage() == "parser.validation_rejected"]
    assert len(events) == 2, f"expected one event per rejected row, got {len(events)}"
    for record in events:
        assert getattr(record, "user_id") == str(user_id)
        assert getattr(record, "upload_id") == str(upload_id)
        assert getattr(record, "row_number") is not None
        assert isinstance(getattr(record, "reason"), str)


def test_validation_rejected_event_carries_reason_string(caplog):
    # Date out of range → a single rejection event with reason.
    rows = [
        _txn(description="OLD", amount=-100, date=datetime(1990, 1, 1)),
    ]
    parse_result = ParseResult(
        transactions=rows,
        flagged_rows=[],
        total_rows=1,
        parsed_count=1,
        flagged_count=0,
    )
    user_id = uuid.uuid4()
    upload_id = uuid.uuid4()

    caplog.set_level(logging.INFO, logger="app.services.parser_service")
    with patch(
        "app.agents.ingestion.parsers.monobank.MonobankParser.parse",
        return_value=parse_result,
    ):
        _parse_and_build_records(
            user_id, upload_id, b"ignored", _format_result(), session=None
        )

    events = [r for r in caplog.records if r.getMessage() == "parser.validation_rejected"]
    assert len(events) == 1
    assert getattr(events[0], "reason")
