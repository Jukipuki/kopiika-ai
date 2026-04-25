"""Tests for Story 2.4: Generic CSV Parser.

Covers: GenericParser (recognizable format, unrecognizable format,
flexible date formats, flexible amount parsing),
parser service integration for unknown formats.
"""

import uuid
from datetime import datetime
from pathlib import Path

import pytest
from sqlmodel import select

from app.agents.ingestion.parsers.generic import GenericParser
from app.models.transaction import Transaction
from app.services.format_detector import FormatDetectionResult
from app.services.parser_service import (
    UnsupportedFormatError,
    parse_and_store_transactions,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"


# ==================== 5.7: GenericParser — Recognizable Format ====================


class TestGenericParserRecognizable:
    """Test GenericParser with CSV that has recognizable date/amount/description columns."""

    def test_recognizable_columns_found_and_parsed(self):
        content = (FIXTURES_DIR / "generic_recognizable.csv").read_bytes()
        parser = GenericParser()
        result = parser.parse(content, encoding="utf-8", delimiter=",")

        assert result.parsed_count == 4
        assert result.flagged_count == 0
        assert result.total_rows == 4

    def test_descriptions_parsed(self):
        content = (FIXTURES_DIR / "generic_recognizable.csv").read_bytes()
        parser = GenericParser()
        result = parser.parse(content, encoding="utf-8", delimiter=",")

        descriptions = [txn.description for txn in result.transactions]
        assert "Grocery Store" in descriptions
        assert "Salary Payment" in descriptions

    def test_mcc_and_balance_are_none(self):
        content = (FIXTURES_DIR / "generic_recognizable.csv").read_bytes()
        parser = GenericParser()
        result = parser.parse(content, encoding="utf-8", delimiter=",")

        for txn in result.transactions:
            assert txn.mcc is None
            assert txn.balance is None

    def test_default_currency_is_uah(self):
        content = (FIXTURES_DIR / "generic_recognizable.csv").read_bytes()
        parser = GenericParser()
        result = parser.parse(content, encoding="utf-8", delimiter=",")

        for txn in result.transactions:
            assert txn.currency_code == 980


# ==================== 5.8: GenericParser — Unrecognizable Format ====================


class TestGenericParserUnrecognizable:
    """Test GenericParser with completely unrecognizable CSV."""

    def test_unrecognizable_returns_empty_with_flagged_row(self):
        content = (FIXTURES_DIR / "generic_unrecognizable.csv").read_bytes()
        parser = GenericParser()
        result = parser.parse(content, encoding="utf-8", delimiter=",")

        assert result.parsed_count == 0
        assert result.flagged_count == 1
        assert result.total_rows == 0

        assert len(result.flagged_rows) == 1
        assert "not yet supported" in result.flagged_rows[0].reason

    def test_empty_csv_returns_empty_parse_result(self):
        parser = GenericParser()
        result = parser.parse(b"", encoding="utf-8", delimiter=",")

        assert result.parsed_count == 0
        assert result.flagged_count == 0


# ==================== 5.9: GenericParser — Flexible Date Formats ====================


class TestGenericParserDateFormats:
    """Test GenericParser handles multiple date formats."""

    def test_flexible_date_formats_all_parsed(self):
        content = (FIXTURES_DIR / "generic_recognizable.csv").read_bytes()
        parser = GenericParser()
        result = parser.parse(content, encoding="utf-8", delimiter=",")

        # Row 1: DD.MM.YYYY -> 01.01.2024
        assert result.transactions[0].date == datetime(2024, 1, 1)
        # Row 2: YYYY-MM-DD -> 2024-01-02
        assert result.transactions[1].date == datetime(2024, 1, 2)
        # Row 3: DD/MM/YYYY -> 03/01/2024
        assert result.transactions[2].date == datetime(2024, 1, 3)
        # Row 4: DD.MM.YYYY HH:MM:SS -> 04.01.2024 18:45:00
        assert result.transactions[3].date == datetime(2024, 1, 4, 18, 45, 0)

    def test_dates_are_naive_datetimes(self):
        content = (FIXTURES_DIR / "generic_recognizable.csv").read_bytes()
        parser = GenericParser()
        result = parser.parse(content, encoding="utf-8", delimiter=",")

        for txn in result.transactions:
            assert txn.date.tzinfo is None


# ==================== 5.10: GenericParser — Flexible Amount Parsing ====================


class TestGenericParserAmountParsing:
    """Test GenericParser handles comma and period decimal separators."""

    def test_period_decimal_parsed(self):
        content = (FIXTURES_DIR / "generic_recognizable.csv").read_bytes()
        parser = GenericParser()
        result = parser.parse(content, encoding="utf-8", delimiter=",")

        # Row 1: -150.50 -> -15050 kopiykas
        assert result.transactions[0].amount == -15050

    def test_comma_decimal_parsed(self):
        content = (FIXTURES_DIR / "generic_recognizable.csv").read_bytes()
        parser = GenericParser()
        result = parser.parse(content, encoding="utf-8", delimiter=",")

        # Row 2: -850,00 -> -85000 kopiykas
        assert result.transactions[1].amount == -85000

    def test_large_positive_amount(self):
        content = (FIXTURES_DIR / "generic_recognizable.csv").read_bytes()
        parser = GenericParser()
        result = parser.parse(content, encoding="utf-8", delimiter=",")

        # Row 3: 25000.00 -> 2500000 kopiykas
        assert result.transactions[2].amount == 2500000


# ==================== 5.12: Parser Service — Unknown Format with GenericParser ====================


class TestParserServiceGeneric:
    """Test parser_service uses GenericParser as fallback for unknown formats."""

    @pytest.mark.asyncio
    async def test_unknown_format_with_recognizable_columns_uses_generic(self, async_session):
        user_id = uuid.uuid4()
        upload_id = uuid.uuid4()

        from app.models.user import User
        from app.models.upload import Upload

        user = User(id=user_id, cognito_sub="test-sub-generic", email="generic@test.com")
        session = async_session
        session.add(user)
        upload = Upload(
            id=upload_id,
            user_id=user_id,
            file_name="generic.csv",
            s3_key="test/generic",
            file_size=100,
            mime_type="text/csv",
        )
        session.add(upload)
        await session.commit()

        content = (FIXTURES_DIR / "generic_recognizable.csv").read_bytes()
        format_result = FormatDetectionResult(
            bank_format="unknown",
            encoding="utf-8",
            delimiter=",",
            column_count=4,
            confidence_score=0.3,
            header_row=[],
        )

        result = await parse_and_store_transactions(
            session=session,
            user_id=user_id,
            upload_id=upload_id,
            file_bytes=content,
            format_result=format_result,
        )
        await session.commit()

        assert result.parsed_count == 4
        assert result.flagged_count == 0

        transactions = (await session.exec(select(Transaction))).all()
        assert len(transactions) == 4

    @pytest.mark.asyncio
    async def test_completely_unknown_format_raises_unsupported_error(self, async_session):
        user_id = uuid.uuid4()
        upload_id = uuid.uuid4()

        from app.models.user import User
        from app.models.upload import Upload

        user = User(id=user_id, cognito_sub="test-sub-unsupported", email="unsupported@test.com")
        session = async_session
        session.add(user)
        upload = Upload(
            id=upload_id,
            user_id=user_id,
            file_name="unknown.csv",
            s3_key="test/unknown",
            file_size=100,
            mime_type="text/csv",
        )
        session.add(upload)
        await session.commit()

        content = (FIXTURES_DIR / "generic_unrecognizable.csv").read_bytes()
        format_result = FormatDetectionResult(
            bank_format="unknown",
            encoding="utf-8",
            delimiter=",",
            column_count=3,
            confidence_score=0.1,
            header_row=[],
        )

        with pytest.raises(UnsupportedFormatError) as exc_info:
            await parse_and_store_transactions(
                session=session,
                user_id=user_id,
                upload_id=upload_id,
                file_bytes=content,
                format_result=format_result,
            )

        assert "not yet supported" in str(exc_info.value)
        assert "Monobank CSV" in str(exc_info.value)
        assert "PrivatBank CSV" in str(exc_info.value)


# ==================== Story 2.9: GenericParser — Currency Resolution ====================


class TestGenericParserCurrency:
    """Test Generic parser resolves new currencies and flags unknowns."""

    def _make_csv(self, rows: list[str]) -> bytes:
        header = "Date,Amount,Description,Currency\n"
        return (header + "\n".join(rows) + "\n").encode("utf-8")

    def test_known_currencies_resolved(self):
        content = self._make_csv([
            "01.01.2024,-10.00,Zurich Coffee,CHF",
            "02.01.2024,-1500.00,Tokyo Ramen,JPY",
            "03.01.2024,-80.00,Prague Metro,CZK",
            "04.01.2024,-50.00,Istanbul Taxi,TRY",
        ])
        parser = GenericParser()
        result = parser.parse(content, encoding="utf-8", delimiter=",")

        assert result.parsed_count == 4
        mappings = [(t.currency_code, t.currency_alpha) for t in result.transactions]
        assert mappings == [
            (756, "CHF"),
            (392, "JPY"),
            (203, "CZK"),
            (949, "TRY"),
        ]
        for txn in result.transactions:
            assert txn.currency_unknown_raw is None

    def test_unknown_currency_flagged(self, caplog):
        import logging as _logging

        content = self._make_csv([
            "01.01.2024,-10.00,Exotic Exchange,XYZ",
        ])
        parser = GenericParser()
        app_logger = _logging.getLogger("app")
        app_logger.propagate = True
        try:
            with caplog.at_level(_logging.WARNING, logger="app.agents.ingestion.parsers.generic"):
                result = parser.parse(content, encoding="utf-8", delimiter=",")
        finally:
            app_logger.propagate = False

        assert result.parsed_count == 1
        txn = result.transactions[0]
        assert txn.currency_code == 0
        assert txn.currency_alpha is None
        assert txn.currency_unknown_raw == "XYZ"
        warnings = [r for r in caplog.records if r.message == "currency_unknown"]
        assert len(warnings) == 1
        assert getattr(warnings[0], "raw_currency", None) == "XYZ"
        assert getattr(warnings[0], "parser", None) == "generic"

    def test_no_currency_column_defaults_to_uah(self):
        """CSV with no currency column — generic parser must keep defaulting to UAH (AC #5)."""
        content = (FIXTURES_DIR / "generic_recognizable.csv").read_bytes()
        parser = GenericParser()
        result = parser.parse(content, encoding="utf-8", delimiter=",")

        for txn in result.transactions:
            assert txn.currency_code == 980
            assert txn.currency_alpha is None
            assert txn.currency_unknown_raw is None


# ==================== Story 11.6: Decode fallback on misdetected encoding ====================


class TestGenericDecodeFallback:
    """AC #3: Fall back to utf-8 with errors='replace' instead of raising."""

    def test_invalid_bytes_for_encoding_fall_back_instead_of_raising(self):
        from app.agents.ingestion.parsers.generic import GenericParser

        header = b"Date,Amount,Description\n"
        bad_row = b"01.01.2026,-100.00,\xff\xfe Bad Byte\n"
        file_bytes = header + bad_row

        parser = GenericParser()
        result = parser.parse(file_bytes, encoding="utf-8", delimiter=",")
        assert result.parsed_count == 1
        assert "\ufffd" in result.transactions[0].description
