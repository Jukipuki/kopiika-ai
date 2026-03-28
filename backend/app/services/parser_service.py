import logging
import uuid
from dataclasses import dataclass

from sqlmodel import Session
from sqlmodel.ext.asyncio.session import AsyncSession as SQLModelAsyncSession

from app.agents.ingestion.parsers.base import AbstractParser, ParseResult
from app.agents.ingestion.parsers.generic import GenericParser
from app.agents.ingestion.parsers.monobank import MonobankParser
from app.agents.ingestion.parsers.privatbank import PrivatBankParser
from app.models.flagged_import_row import FlaggedImportRow
from app.models.transaction import Transaction
from app.services.format_detector import FormatDetectionResult

logger = logging.getLogger(__name__)

_PARSERS: dict[str, type[AbstractParser]] = {
    "monobank": MonobankParser,
    "privatbank": PrivatBankParser,
}


@dataclass
class ParseAndStoreResult:
    total_rows: int
    parsed_count: int
    flagged_count: int
    persisted_count: int


class UnsupportedFormatError(Exception):
    """Raised when no parser is available for the detected bank format."""


def _parse_and_build_records(
    user_id: uuid.UUID,
    upload_id: uuid.UUID,
    file_bytes: bytes,
    format_result: FormatDetectionResult,
) -> tuple[list[Transaction], list[FlaggedImportRow], ParseAndStoreResult]:
    """Parse file and build ORM objects. Shared by async and sync store functions."""
    parser_cls = _PARSERS.get(format_result.bank_format)

    if parser_cls is not None:
        parser = parser_cls()
        result = parser.parse(
            file_bytes=file_bytes,
            encoding=format_result.encoding,
            delimiter=format_result.delimiter,
        )
    else:
        generic = GenericParser()
        result = generic.parse(
            file_bytes=file_bytes,
            encoding=format_result.encoding,
            delimiter=format_result.delimiter,
        )
        if result.parsed_count == 0:
            raise UnsupportedFormatError(
                "This file format is not yet supported. "
                "Currently supported: Monobank CSV, PrivatBank CSV."
            )

    transactions = [
        Transaction(
            user_id=user_id,
            upload_id=upload_id,
            date=txn_data.date,
            description=txn_data.description,
            mcc=txn_data.mcc,
            amount=txn_data.amount,
            balance=txn_data.balance,
            currency_code=txn_data.currency_code,
            raw_data=txn_data.raw_data,
        )
        for txn_data in result.transactions
    ]

    flagged_records = [
        FlaggedImportRow(
            user_id=user_id,
            upload_id=upload_id,
            row_number=flagged.row_number,
            raw_data=flagged.raw_data if isinstance(flagged.raw_data, dict) else {"raw": flagged.raw_data},
            reason=flagged.reason,
        )
        for flagged in result.flagged_rows
    ]

    persisted_count = len(transactions) + len(flagged_records)
    store_result = ParseAndStoreResult(
        total_rows=result.total_rows,
        parsed_count=result.parsed_count,
        flagged_count=result.flagged_count,
        persisted_count=persisted_count,
    )

    return transactions, flagged_records, store_result


async def parse_and_store_transactions(
    session: SQLModelAsyncSession,
    user_id: uuid.UUID,
    upload_id: uuid.UUID,
    file_bytes: bytes,
    format_result: FormatDetectionResult,
) -> ParseAndStoreResult:
    """Select parser based on format, parse transactions, and add to session.

    NOTE: Does NOT commit the session — caller controls the transaction boundary.
    """
    transactions, flagged_records, result = _parse_and_build_records(
        user_id, upload_id, file_bytes, format_result,
    )
    session.add_all(transactions)
    session.add_all(flagged_records)

    logger.info(
        "Parse and store complete",
        extra={
            "upload_id": str(upload_id),
            "total_rows": result.total_rows,
            "parsed": result.parsed_count,
            "flagged": result.flagged_count,
            "persisted": result.persisted_count,
        },
    )

    return result


def sync_parse_and_store_transactions(
    session: Session,
    user_id: uuid.UUID,
    upload_id: uuid.UUID,
    file_bytes: bytes,
    format_result: FormatDetectionResult,
) -> ParseAndStoreResult:
    """Synchronous version for Celery worker context.

    NOTE: Does NOT commit the session — caller controls the transaction boundary.
    """
    transactions, flagged_records, result = _parse_and_build_records(
        user_id, upload_id, file_bytes, format_result,
    )
    session.add_all(transactions)
    session.add_all(flagged_records)

    logger.info(
        "Sync parse and store complete",
        extra={
            "upload_id": str(upload_id),
            "total_rows": result.total_rows,
            "parsed": result.parsed_count,
            "flagged": result.flagged_count,
            "persisted": result.persisted_count,
        },
    )

    return result
