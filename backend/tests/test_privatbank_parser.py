"""Tests for Story 2.4: PrivatBank CSV Parser.

Covers: PrivatBankParser (standard format, currency handling, malformed rows,
amount conversion, date parsing, raw_data preservation),
parser service integration with PrivatBank format.
"""

import uuid
from datetime import datetime
from pathlib import Path

import pytest
import pytest_asyncio
from sqlmodel import select

from app.agents.ingestion.parsers.base import FlaggedRow, ParseResult, TransactionData
from app.agents.ingestion.parsers.privatbank import PrivatBankParser
from app.models.flagged_import_row import FlaggedImportRow
from app.models.transaction import Transaction
from app.services.format_detector import FormatDetectionResult
from app.services.parser_service import parse_and_store_transactions

FIXTURES_DIR = Path(__file__).parent / "fixtures"


# ==================== 5.1: PrivatBankParser — Standard Format ====================


class TestPrivatBankParserStandard:
    """Test PrivatBankParser with standard PrivatBank CSV format."""

    def test_standard_format_all_fields_parsed(self):
        content = (FIXTURES_DIR / "privatbank_standard.csv").read_bytes()
        parser = PrivatBankParser()
        result = parser.parse(content, encoding="utf-8", delimiter=",")

        assert result.parsed_count == 5
        assert result.flagged_count == 0
        assert result.total_rows == 5

        txn = result.transactions[0]
        assert txn.description == "Супермаркет Сільпо"
        assert txn.mcc is None  # PrivatBank has no MCC column
        assert txn.amount == -15050  # -150.50 UAH in kopiykas
        assert txn.balance is None  # PrivatBank has no balance column
        assert txn.currency_code == 980
        assert isinstance(txn.date, datetime)
        assert txn.date == datetime(2024, 1, 1, 12, 0, 0)

    def test_all_transactions_parsed_correctly(self):
        content = (FIXTURES_DIR / "privatbank_standard.csv").read_bytes()
        parser = PrivatBankParser()
        result = parser.parse(content, encoding="utf-8", delimiter=",")

        amounts = [txn.amount for txn in result.transactions]
        assert amounts == [-15050, -85000, 2500000, -32075, -50000]

        descriptions = [txn.description for txn in result.transactions]
        assert descriptions == [
            "Супермаркет Сільпо",
            "АЗС WOG",
            "Зарплата",
            "Аптека Подорожник",
            "Переказ на картку",
        ]


# ==================== 5.2: PrivatBankParser — Currency Handling ====================


class TestPrivatBankParserCurrency:
    """Test PrivatBankParser currency mapping."""

    def test_uah_maps_to_980(self):
        content = (FIXTURES_DIR / "privatbank_standard.csv").read_bytes()
        parser = PrivatBankParser()
        result = parser.parse(content, encoding="utf-8", delimiter=",")

        for txn in result.transactions:
            assert txn.currency_code == 980

    def test_usd_maps_to_840(self):
        content = (FIXTURES_DIR / "privatbank_malformed.csv").read_bytes()
        parser = PrivatBankParser()
        result = parser.parse(content, encoding="utf-8", delimiter=",")

        # Last valid row has USD currency
        usd_txn = [t for t in result.transactions if t.currency_code == 840]
        assert len(usd_txn) == 1
        assert usd_txn[0].description == "Переказ"


# ==================== 5.3: PrivatBankParser — Malformed Rows ====================


class TestPrivatBankParserMalformed:
    """Test PrivatBankParser handles malformed rows gracefully."""

    def test_malformed_rows_flagged_valid_rows_parsed(self):
        content = (FIXTURES_DIR / "privatbank_malformed.csv").read_bytes()
        parser = PrivatBankParser()
        result = parser.parse(content, encoding="utf-8", delimiter=",")

        # 5 data rows: row 2 valid, row 3 bad date, row 4 bad amount, row 5 valid, row 6 valid (USD)
        assert result.parsed_count == 3
        assert result.flagged_count == 2
        assert result.total_rows == 5

    def test_flagged_rows_contain_reasons(self):
        content = (FIXTURES_DIR / "privatbank_malformed.csv").read_bytes()
        parser = PrivatBankParser()
        result = parser.parse(content, encoding="utf-8", delimiter=",")

        assert len(result.flagged_rows) == 2
        # Bad date row
        assert result.flagged_rows[0].row_number == 3
        assert isinstance(result.flagged_rows[0].raw_data, dict)
        # Bad amount row
        assert result.flagged_rows[1].row_number == 4


# ==================== 5.4: PrivatBankParser — Amount Conversion ====================


class TestPrivatBankParserAmountConversion:
    """Test PrivatBankParser amount conversion to kopiykas."""

    def test_negative_amount_with_period_decimal(self):
        content = (FIXTURES_DIR / "privatbank_standard.csv").read_bytes()
        parser = PrivatBankParser()
        result = parser.parse(content, encoding="utf-8", delimiter=",")

        assert result.transactions[0].amount == -15050  # -150.50 -> -15050

    def test_large_positive_amount(self):
        content = (FIXTURES_DIR / "privatbank_standard.csv").read_bytes()
        parser = PrivatBankParser()
        result = parser.parse(content, encoding="utf-8", delimiter=",")

        assert result.transactions[2].amount == 2500000  # 25000.00 -> 2500000

    def test_comma_decimal_separator(self):
        """Test amount conversion handles comma decimal separator."""
        from app.agents.ingestion.parsers.privatbank import _parse_amount_kopiykas

        assert _parse_amount_kopiykas("1000,50") == 100050
        assert _parse_amount_kopiykas("-150,50") == -15050


# ==================== 5.5: PrivatBankParser — Date Parsing ====================


class TestPrivatBankParserDateParsing:
    """Test PrivatBankParser date parsing."""

    def test_date_parsed_correctly(self):
        content = (FIXTURES_DIR / "privatbank_standard.csv").read_bytes()
        parser = PrivatBankParser()
        result = parser.parse(content, encoding="utf-8", delimiter=",")

        assert result.transactions[0].date == datetime(2024, 1, 1, 12, 0, 0)
        assert result.transactions[1].date == datetime(2024, 1, 2, 14, 30, 0)
        assert result.transactions[2].date == datetime(2024, 1, 3, 9, 15, 0)

    def test_dates_are_naive_datetimes(self):
        content = (FIXTURES_DIR / "privatbank_standard.csv").read_bytes()
        parser = PrivatBankParser()
        result = parser.parse(content, encoding="utf-8", delimiter=",")

        for txn in result.transactions:
            assert txn.date.tzinfo is None


# ==================== 5.6: PrivatBankParser — Raw Data Preservation ====================


class TestPrivatBankParserRawData:
    """Test PrivatBankParser preserves raw row data."""

    def test_raw_data_contains_original_columns(self):
        content = (FIXTURES_DIR / "privatbank_standard.csv").read_bytes()
        parser = PrivatBankParser()
        result = parser.parse(content, encoding="utf-8", delimiter=",")

        raw = result.transactions[0].raw_data
        assert isinstance(raw, dict)
        assert "Дата операції" in raw
        assert "Опис операції" in raw
        assert "Категорія" in raw
        assert "Сума" in raw
        assert "Валюта" in raw
        assert raw["Категорія"] == "Продукти"


# ==================== 5.11: Parser Service — PrivatBank Integration ====================


class TestParserServicePrivatBank:
    """Test parser_service selects PrivatBankParser and persists to DB."""

    @pytest.mark.asyncio
    async def test_privatbank_format_selects_privatbank_parser(self, async_session):
        user_id = uuid.uuid4()
        upload_id = uuid.uuid4()

        from app.models.user import User
        from app.models.upload import Upload

        user = User(id=user_id, cognito_sub="test-sub-privat", email="privat@test.com")
        session = async_session
        session.add(user)
        upload = Upload(
            id=upload_id,
            user_id=user_id,
            file_name="privatbank.csv",
            s3_key="test/privatbank",
            file_size=100,
            mime_type="text/csv",
        )
        session.add(upload)
        await session.commit()

        content = (FIXTURES_DIR / "privatbank_standard.csv").read_bytes()
        format_result = FormatDetectionResult(
            bank_format="privatbank",
            encoding="utf-8",
            delimiter=",",
            column_count=5,
            confidence_score=0.9,
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

        assert result.parsed_count == 5
        assert result.flagged_count == 0

        # Verify transactions in DB
        transactions = (await session.exec(select(Transaction))).all()
        assert len(transactions) == 5

        txn = transactions[0]
        assert txn.user_id == user_id
        assert txn.upload_id == upload_id
        assert txn.mcc is None
        assert txn.balance is None
        assert txn.currency_code == 980


# ==================== Story 2.9: PrivatBankParser — Currency Resolution ====================


class TestPrivatBankParserCurrencyExtended:
    """Test PrivatBank parser resolves new currencies and flags unknowns."""

    def _make_csv(self, rows: list[str]) -> bytes:
        header = "Дата операції,Опис операції,Категорія,Сума,Валюта\n"
        return (header + "\n".join(rows) + "\n").encode("utf-8")

    def test_known_currencies_resolved(self):
        content = self._make_csv([
            "01.01.2024 12:00:00,Zurich Coffee,Food,-10.00,CHF",
            "02.01.2024 12:00:00,Tokyo Ramen,Food,-1500.00,JPY",
            "03.01.2024 12:00:00,Prague Metro,Transport,-80.00,CZK",
            "04.01.2024 12:00:00,Istanbul Taxi,Transport,-50.00,TRY",
        ])
        parser = PrivatBankParser()
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
            "01.01.2024 12:00:00,Exotic Exchange,Other,-10.00,XYZ",
        ])
        parser = PrivatBankParser()
        app_logger = _logging.getLogger("app")
        app_logger.propagate = True
        try:
            with caplog.at_level(_logging.WARNING, logger="app.agents.ingestion.parsers.privatbank"):
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
        assert getattr(warnings[0], "parser", None) == "privatbank"

    def test_uah_remains_unflagged_regression(self):
        """Existing UAH rows must parse unchanged — regression safety net (AC #5)."""
        content = (FIXTURES_DIR / "privatbank_standard.csv").read_bytes()
        parser = PrivatBankParser()
        result = parser.parse(content, encoding="utf-8", delimiter=",")

        for txn in result.transactions:
            assert txn.currency_code == 980
            assert txn.currency_alpha == "UAH"
            assert txn.currency_unknown_raw is None
