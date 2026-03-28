"""Tests for Story 2.3: Monobank CSV Parser.

Covers: Transaction model, FlaggedImportRow model, MonobankParser
(legacy/modern/embedded newlines/malformed/edge cases),
amount conversion, date parsing, parser service, parser selection.
"""

import uuid
from datetime import datetime
from pathlib import Path

import pytest
import pytest_asyncio
from sqlmodel import select

from app.agents.ingestion.parsers.base import FlaggedRow, ParseResult, TransactionData
from app.agents.ingestion.parsers.monobank import MonobankParser
from app.models.flagged_import_row import FlaggedImportRow
from app.models.transaction import Transaction
from app.services.format_detector import FormatDetectionResult
from app.services.parser_service import (
    UnsupportedFormatError,
    parse_and_store_transactions,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"


# ==================== 5.5: MonobankParser — Legacy Format ====================


class TestMonobankParserLegacy:
    """Test MonobankParser with legacy format (Windows-1251, semicolons, 5 columns)."""

    def test_legacy_format_all_fields_parsed(self):
        content = (FIXTURES_DIR / "monobank_legacy.csv").read_bytes()
        parser = MonobankParser()
        result = parser.parse(content, encoding="windows-1251", delimiter=";")

        assert result.parsed_count == 5
        assert result.flagged_count == 0
        assert result.total_rows == 5

        txn = result.transactions[0]
        assert txn.description == "Супермаркет АТБ"
        assert txn.mcc == 5411
        assert txn.amount == -15050  # -150.50 UAH in kopiykas
        assert txn.balance == 1000000  # 10000.00 UAH in kopiykas
        assert txn.currency_code == 980
        assert isinstance(txn.date, datetime)
        assert txn.date == datetime(2024, 1, 1, 12, 0, 0)

    def test_legacy_format_empty_mcc_is_none(self):
        content = (FIXTURES_DIR / "monobank_legacy.csv").read_bytes()
        parser = MonobankParser()
        result = parser.parse(content, encoding="windows-1251", delimiter=";")

        # Third row is "Зарплата" with empty MCC
        salary_txn = result.transactions[2]
        assert salary_txn.mcc is None
        assert salary_txn.amount == 500000  # 5000.00 UAH

    def test_legacy_format_raw_data_preserved(self):
        content = (FIXTURES_DIR / "monobank_legacy.csv").read_bytes()
        parser = MonobankParser()
        result = parser.parse(content, encoding="windows-1251", delimiter=";")

        txn = result.transactions[0]
        assert isinstance(txn.raw_data, dict)
        assert len(txn.raw_data) > 0


# ==================== 5.6: MonobankParser — Modern Format ====================


class TestMonobankParserModern:
    """Test MonobankParser with modern format (UTF-8, commas, 10 columns)."""

    def test_modern_format_all_columns_mapped(self):
        content = (FIXTURES_DIR / "monobank_modern_multi.csv").read_bytes()
        parser = MonobankParser()
        result = parser.parse(content, encoding="utf-8", delimiter=",")

        assert result.parsed_count == 11
        assert result.flagged_count == 0

    def test_modern_format_encoding_handled(self):
        content = (FIXTURES_DIR / "monobank_modern_multi.csv").read_bytes()
        parser = MonobankParser()
        result = parser.parse(content, encoding="utf-8", delimiter=",")

        # Verify Ukrainian text is correctly decoded
        txn = result.transactions[0]
        assert "Супермаркет" in txn.description

    def test_modern_format_mcc_parsed(self):
        content = (FIXTURES_DIR / "monobank_modern_multi.csv").read_bytes()
        parser = MonobankParser()
        result = parser.parse(content, encoding="utf-8", delimiter=",")

        assert result.transactions[0].mcc == 5411
        # Row with MCC=0 (повернення коштів)
        assert result.transactions[10].mcc == 0

    def test_modern_format_empty_mcc_is_none(self):
        content = (FIXTURES_DIR / "monobank_modern_multi.csv").read_bytes()
        parser = MonobankParser()
        result = parser.parse(content, encoding="utf-8", delimiter=",")

        # "Зарплата" row has empty MCC
        salary_txn = result.transactions[2]
        assert salary_txn.mcc is None

    def test_modern_format_balance_column_mapped(self):
        content = (FIXTURES_DIR / "monobank_modern_multi.csv").read_bytes()
        parser = MonobankParser()
        result = parser.parse(content, encoding="utf-8", delimiter=",")

        # "Залишок після операції" should map to balance
        txn = result.transactions[0]
        assert txn.balance == 1000000  # 10000.00


# ==================== 5.7: MonobankParser — Embedded Newlines ====================


class TestMonobankParserEmbeddedNewlines:
    """Test MonobankParser correctly handles embedded newlines in quoted fields."""

    def test_embedded_newlines_rows_correctly_split(self):
        content = (FIXTURES_DIR / "monobank_embedded_newlines.csv").read_bytes()
        parser = MonobankParser()
        result = parser.parse(content, encoding="utf-8", delimiter=",")

        assert result.parsed_count == 3
        assert result.flagged_count == 0

    def test_embedded_newlines_description_preserved(self):
        content = (FIXTURES_DIR / "monobank_embedded_newlines.csv").read_bytes()
        parser = MonobankParser()
        result = parser.parse(content, encoding="utf-8", delimiter=",")

        # First row has multi-line description
        txn = result.transactions[0]
        assert "Супермаркет АТБ" in txn.description
        assert "Хрещатик" in txn.description

    def test_embedded_newlines_amounts_correct(self):
        content = (FIXTURES_DIR / "monobank_embedded_newlines.csv").read_bytes()
        parser = MonobankParser()
        result = parser.parse(content, encoding="utf-8", delimiter=",")

        assert result.transactions[0].amount == -15050
        assert result.transactions[1].amount == -7525
        assert result.transactions[2].amount == 500000


# ==================== 5.8: MonobankParser — Malformed Rows ====================


class TestMonobankParserMalformed:
    """Test MonobankParser handles malformed rows gracefully."""

    def test_malformed_valid_rows_parsed(self):
        content = (FIXTURES_DIR / "monobank_malformed_rows.csv").read_bytes()
        parser = MonobankParser()
        result = parser.parse(content, encoding="utf-8", delimiter=",")

        # Rows 1 and 4 are valid, rows 2, 3, 5 are malformed
        assert result.parsed_count == 2

    def test_malformed_invalid_rows_flagged(self):
        content = (FIXTURES_DIR / "monobank_malformed_rows.csv").read_bytes()
        parser = MonobankParser()
        result = parser.parse(content, encoding="utf-8", delimiter=",")

        assert result.flagged_count >= 2  # At least invalid-date and not-a-number rows

    def test_malformed_flagged_rows_have_reasons(self):
        content = (FIXTURES_DIR / "monobank_malformed_rows.csv").read_bytes()
        parser = MonobankParser()
        result = parser.parse(content, encoding="utf-8", delimiter=",")

        for flagged in result.flagged_rows:
            assert isinstance(flagged, FlaggedRow)
            assert flagged.reason != ""
            assert flagged.row_number > 0

    def test_malformed_parse_result_reflects_partial_success(self):
        content = (FIXTURES_DIR / "monobank_malformed_rows.csv").read_bytes()
        parser = MonobankParser()
        result = parser.parse(content, encoding="utf-8", delimiter=",")

        assert result.total_rows == result.parsed_count + result.flagged_count
        assert result.parsed_count > 0
        assert result.flagged_count > 0


# ==================== 5.9: MonobankParser — Amount Conversion ====================


class TestMonobankAmountConversion:
    """Test amount conversion from decimal string to integer kopiykas."""

    def test_negative_amount(self):
        """'-150.50' → -15050"""
        content = (FIXTURES_DIR / "monobank_modern_multi.csv").read_bytes()
        parser = MonobankParser()
        result = parser.parse(content, encoding="utf-8", delimiter=",")

        assert result.transactions[0].amount == -15050

    def test_positive_amount(self):
        """'5000.00' → 500000"""
        content = (FIXTURES_DIR / "monobank_modern_multi.csv").read_bytes()
        parser = MonobankParser()
        result = parser.parse(content, encoding="utf-8", delimiter=",")

        assert result.transactions[2].amount == 500000

    def test_small_amount(self):
        """Test precision for small amounts — verify Decimal is used, not float."""
        from app.agents.ingestion.parsers.monobank import _parse_amount_kopiykas

        assert _parse_amount_kopiykas("0.01") == 1
        assert _parse_amount_kopiykas("-0.01") == -1
        assert _parse_amount_kopiykas("1000.00") == 100000

    def test_amount_precision_no_float_errors(self):
        """Ensure Decimal-based conversion avoids float precision issues."""
        from app.agents.ingestion.parsers.monobank import _parse_amount_kopiykas

        # float(0.1 + 0.2) != 0.3, but Decimal handles this correctly
        assert _parse_amount_kopiykas("0.10") == 10
        assert _parse_amount_kopiykas("99.99") == 9999


# ==================== 5.10: MonobankParser — Date Parsing ====================


class TestMonobankDateParsing:
    """Test date parsing from DD.MM.YYYY HH:MM:SS format."""

    def test_date_parsed_correctly(self):
        """'01.01.2024 12:00:00' → datetime(2024, 1, 1, 12, 0, 0)"""
        content = (FIXTURES_DIR / "monobank_modern_multi.csv").read_bytes()
        parser = MonobankParser()
        result = parser.parse(content, encoding="utf-8", delimiter=",")

        txn = result.transactions[0]
        assert txn.date == datetime(2024, 1, 1, 12, 0, 0)

    def test_date_is_naive(self):
        """Dates must be naive (no timezone) for SQLite compatibility."""
        content = (FIXTURES_DIR / "monobank_modern_multi.csv").read_bytes()
        parser = MonobankParser()
        result = parser.parse(content, encoding="utf-8", delimiter=",")

        for txn in result.transactions:
            assert txn.date.tzinfo is None

    def test_various_dates_parsed(self):
        from app.agents.ingestion.parsers.monobank import _parse_date

        assert _parse_date("01.01.2024 12:00:00") == datetime(2024, 1, 1, 12, 0, 0)
        assert _parse_date("31.12.2023 23:59:59") == datetime(2023, 12, 31, 23, 59, 59)
        assert _parse_date("15.06.2024 00:00:00") == datetime(2024, 6, 15, 0, 0, 0)


# ==================== 5.11: Parser Service — Parse and Store ====================


class TestParserServiceParseAndStore:
    """Test parse_and_store_transactions persists transactions to DB."""

    @pytest.mark.asyncio
    async def test_transactions_persisted_to_db(self, async_session):
        user_id = uuid.uuid4()
        upload_id = uuid.uuid4()

        # Create prerequisite user and upload records
        from app.models.user import User
        from app.models.upload import Upload

        user = User(id=user_id, cognito_sub="test-sub-parser", email="parser@test.com")
        session = async_session
        session.add(user)
        upload = Upload(
            id=upload_id,
            user_id=user_id,
            file_name="test.csv",
            s3_key="test/key",
            file_size=100,
            mime_type="text/csv",
        )
        session.add(upload)
        await session.commit()

        content = (FIXTURES_DIR / "monobank_modern_multi.csv").read_bytes()
        format_result = FormatDetectionResult(
            bank_format="monobank",
            encoding="utf-8",
            delimiter=",",
            column_count=10,
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

        assert result.parsed_count == 11
        assert result.flagged_count == 0

        # Verify transactions in DB
        transactions = (await session.exec(select(Transaction))).all()
        assert len(transactions) == 11

        # Verify transaction fields
        txn = transactions[0]
        assert txn.user_id == user_id
        assert txn.upload_id == upload_id

    @pytest.mark.asyncio
    async def test_flagged_rows_stored_in_separate_table(self, async_session):
        user_id = uuid.uuid4()
        upload_id = uuid.uuid4()

        from app.models.user import User
        from app.models.upload import Upload

        user = User(id=user_id, cognito_sub="test-sub-flagged", email="flagged@test.com")
        session = async_session
        session.add(user)
        upload = Upload(
            id=upload_id,
            user_id=user_id,
            file_name="malformed.csv",
            s3_key="test/malformed",
            file_size=100,
            mime_type="text/csv",
        )
        session.add(upload)
        await session.commit()

        content = (FIXTURES_DIR / "monobank_malformed_rows.csv").read_bytes()
        format_result = FormatDetectionResult(
            bank_format="monobank",
            encoding="utf-8",
            delimiter=",",
            column_count=10,
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

        assert result.flagged_count > 0

        # Flagged rows stored in flagged_import_rows table, NOT transactions
        flagged = (
            await session.exec(select(FlaggedImportRow).where(FlaggedImportRow.upload_id == upload_id))
        ).all()
        assert len(flagged) == result.flagged_count
        for row in flagged:
            assert row.reason is not None
            assert row.row_number > 0

        # Transactions table contains ONLY valid parsed rows
        transactions = (
            await session.exec(select(Transaction).where(Transaction.upload_id == upload_id))
        ).all()
        assert len(transactions) == result.parsed_count

    @pytest.mark.asyncio
    async def test_service_does_not_commit(self, async_session):
        """Verify caller controls transaction boundary — service only adds to session."""
        user_id = uuid.uuid4()
        upload_id = uuid.uuid4()

        from app.models.user import User
        from app.models.upload import Upload

        user = User(id=user_id, cognito_sub="test-sub-nocommit", email="nocommit@test.com")
        session = async_session
        session.add(user)
        upload = Upload(
            id=upload_id,
            user_id=user_id,
            file_name="test.csv",
            s3_key="test/nocommit",
            file_size=100,
            mime_type="text/csv",
        )
        session.add(upload)
        await session.commit()

        content = (FIXTURES_DIR / "monobank_modern_multi.csv").read_bytes()
        format_result = FormatDetectionResult(
            bank_format="monobank",
            encoding="utf-8",
            delimiter=",",
            column_count=10,
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

        # Rollback instead of committing — nothing should be persisted
        await session.rollback()

        transactions = (await session.exec(select(Transaction))).all()
        assert len(transactions) == 0


# ==================== 5.12: Parser Service — Partial Results ====================


class TestParserServicePartialResults:
    """Test that partial results are persisted when some rows fail."""

    @pytest.mark.asyncio
    async def test_partial_results_persisted(self, async_session):
        user_id = uuid.uuid4()
        upload_id = uuid.uuid4()

        from app.models.user import User
        from app.models.upload import Upload

        user = User(id=user_id, cognito_sub="test-sub-partial", email="partial@test.com")
        session = async_session
        session.add(user)
        upload = Upload(
            id=upload_id,
            user_id=user_id,
            file_name="malformed.csv",
            s3_key="test/partial",
            file_size=100,
            mime_type="text/csv",
        )
        session.add(upload)
        await session.commit()

        content = (FIXTURES_DIR / "monobank_malformed_rows.csv").read_bytes()
        format_result = FormatDetectionResult(
            bank_format="monobank",
            encoding="utf-8",
            delimiter=",",
            column_count=10,
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

        # Both valid transactions and flagged rows should be persisted
        assert result.parsed_count > 0
        assert result.flagged_count > 0
        assert result.persisted_count == result.parsed_count + result.flagged_count

        # Valid transactions in transactions table
        all_txns = (await session.exec(
            select(Transaction).where(Transaction.upload_id == upload_id)
        )).all()
        assert len(all_txns) == result.parsed_count

        # Flagged rows in flagged_import_rows table
        all_flagged = (await session.exec(
            select(FlaggedImportRow).where(FlaggedImportRow.upload_id == upload_id)
        )).all()
        assert len(all_flagged) == result.flagged_count


# ==================== 5.13: Transaction Model — Migration ====================


class TestTransactionModel:
    """Test Transaction model and Alembic migration."""

    def test_migration_file_exists(self):
        migration_dir = Path(__file__).parent.parent / "alembic" / "versions"
        migration_files = list(migration_dir.glob("*create_transactions_table*"))
        assert len(migration_files) == 1

    def test_migration_has_correct_columns(self):
        migration_dir = Path(__file__).parent.parent / "alembic" / "versions"
        migration_file = list(migration_dir.glob("*create_transactions_table*"))[0]
        content = migration_file.read_text()

        expected_columns = [
            "id", "user_id", "upload_id", "date", "description",
            "mcc", "amount", "balance", "currency_code", "raw_data",
            "created_at",
        ]
        for col in expected_columns:
            assert f"'{col}'" in content, f"Column {col} not found in migration"

    def test_migration_has_indexes(self):
        migration_dir = Path(__file__).parent.parent / "alembic" / "versions"
        migration_file = list(migration_dir.glob("*create_transactions_table*"))[0]
        content = migration_file.read_text()

        assert "idx_transactions_user_id" in content
        assert "idx_transactions_upload_id" in content
        assert "idx_transactions_date" in content

    def test_migration_has_foreign_keys(self):
        migration_dir = Path(__file__).parent.parent / "alembic" / "versions"
        migration_file = list(migration_dir.glob("*create_transactions_table*"))[0]
        content = migration_file.read_text()

        assert "users.id" in content
        assert "uploads.id" in content

    def test_migration_has_flagged_import_rows_table(self):
        migration_dir = Path(__file__).parent.parent / "alembic" / "versions"
        migration_file = list(migration_dir.glob("*create_transactions_table*"))[0]
        content = migration_file.read_text()

        assert "flagged_import_rows" in content
        assert "row_number" in content
        assert "reason" in content

    @pytest.mark.asyncio
    async def test_transaction_crud(self, async_session):
        """Test that Transaction records can be created and queried."""
        user_id = uuid.uuid4()
        upload_id = uuid.uuid4()

        from app.models.user import User
        from app.models.upload import Upload

        user = User(id=user_id, cognito_sub="test-sub-crud", email="crud@test.com")
        session = async_session
        session.add(user)
        upload = Upload(
            id=upload_id,
            user_id=user_id,
            file_name="test.csv",
            s3_key="test/crud",
            file_size=100,
            mime_type="text/csv",
        )
        session.add(upload)
        await session.commit()

        txn = Transaction(
            user_id=user_id,
            upload_id=upload_id,
            date=datetime(2024, 1, 1, 12, 0, 0),
            description="Test transaction",
            mcc=5411,
            amount=-15050,
            balance=1000000,
            currency_code=980,
            raw_data={"test": "data"},
        )
        session.add(txn)
        await session.commit()

        result = (await session.exec(select(Transaction))).all()
        assert len(result) == 1
        assert result[0].amount == -15050
        assert result[0].description == "Test transaction"
        assert result[0].raw_data == {"test": "data"}


# ==================== 5.14: Parser Selection ====================


class TestParserSelection:
    """Test that correct parser is selected based on bank_format."""

    def test_monobank_format_selects_monobank_parser(self):
        from app.services.parser_service import _PARSERS

        assert "monobank" in _PARSERS
        assert _PARSERS["monobank"] is MonobankParser

    @pytest.mark.asyncio
    async def test_unknown_format_raises_error(self, async_session):
        format_result = FormatDetectionResult(
            bank_format="unknown",
            encoding="utf-8",
            delimiter=",",
            column_count=3,
            confidence_score=0.1,
            header_row=[],
        )

        with pytest.raises(UnsupportedFormatError):
            await parse_and_store_transactions(
                session=async_session,
                user_id=uuid.uuid4(),
                upload_id=uuid.uuid4(),
                file_bytes=b"a,b,c\n1,2,3",
                format_result=format_result,
            )

    @pytest.mark.asyncio
    async def test_privatbank_format_selects_parser(self, async_session):
        """PrivatBank parser is now implemented — should not raise UnsupportedFormatError."""
        from app.agents.ingestion.parsers.privatbank import PrivatBankParser
        from app.services.parser_service import _PARSERS

        assert "privatbank" in _PARSERS
        assert _PARSERS["privatbank"] is PrivatBankParser

        # Verify the parser actually works through instantiation
        parser = PrivatBankParser()
        result = parser.parse(
            b"\xef\xbb\xbf\xd0\x94\xd0\xb0\xd1\x82\xd0\xb0 \xd0\xbe\xd0\xbf\xd0\xb5\xd1\x80\xd0\xb0\xd1\x86\xd1\x96\xd1\x97",  # BOM + "Дата операції" header only
            encoding="utf-8",
            delimiter=",",
        )
        assert result.parsed_count == 0


# ==================== Edge Cases (M3) ====================


class TestMonobankParserEdgeCases:
    """Test parser edge cases: BOM, empty file, header-only file."""

    def test_utf8_bom_handled(self):
        """UTF-8 BOM should be stripped — header matching must still work."""
        content = (FIXTURES_DIR / "monobank_modern_multi.csv").read_bytes()
        bom_content = b"\xef\xbb\xbf" + content
        parser = MonobankParser()
        result = parser.parse(bom_content, encoding="utf-8", delimiter=",")

        assert result.parsed_count == 11
        assert result.flagged_count == 0

    def test_empty_file(self):
        """0 bytes should return empty ParseResult, not crash."""
        parser = MonobankParser()
        result = parser.parse(b"", encoding="utf-8", delimiter=",")

        assert result.parsed_count == 0
        assert result.flagged_count == 0
        assert result.total_rows == 0

    def test_header_only_file(self):
        """CSV with header but no data rows should return 0 transactions."""
        header = '"Дата i час операції","Деталі операції",MCC,"Сума в валюті картки (UAH)","Сума в валюті операції",Валюта,Курс,"Сума комісій (UAH)","Сума кешбеку (UAH)","Залишок після операції"\n'
        parser = MonobankParser()
        result = parser.parse(header.encode("utf-8"), encoding="utf-8", delimiter=",")

        assert result.parsed_count == 0
        assert result.flagged_count == 0
        assert result.total_rows == 0
