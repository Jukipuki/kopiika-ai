import csv
import io
import logging
from datetime import datetime
from decimal import Decimal, InvalidOperation

from app.agents.ingestion.parsers.base import (
    AbstractParser,
    FlaggedRow,
    ParseResult,
    TransactionData,
)

logger = logging.getLogger(__name__)

# Flexible header mappings to support both legacy and modern Monobank formats
HEADER_MAPPINGS: dict[str, list[str]] = {
    "date": ["Дата і час операції", "Дата i час операції"],
    "description": ["Опис операції", "Деталі операції"],
    "mcc": ["MCC"],
    "amount": ["Сума в валюті картки (UAH)"],
    "balance": ["Залишок на рахунку (UAH)", "Залишок після операції"],
}


def _resolve_column_index(header: list[str], field_name: str) -> int | None:
    """Find the column index for a field using flexible header matching."""
    candidates = HEADER_MAPPINGS.get(field_name, [])
    for candidate in candidates:
        for i, col in enumerate(header):
            if col.strip() == candidate:
                return i
    return None


def _parse_date(value: str) -> datetime:
    """Parse Monobank date format DD.MM.YYYY HH:MM:SS to naive datetime."""
    return datetime.strptime(value.strip(), "%d.%m.%Y %H:%M:%S")


def _parse_amount_kopiykas(value: str) -> int:
    """Convert decimal amount string to integer kopiykas using Decimal for precision."""
    return int(round(Decimal(value.strip()) * 100))


def _parse_mcc(value: str) -> int | None:
    """Parse MCC code from string, returning None if empty or invalid."""
    stripped = value.strip()
    if not stripped:
        return None
    try:
        return int(stripped)
    except ValueError:
        return None


class MonobankParser(AbstractParser):
    def parse(self, file_bytes: bytes, encoding: str, delimiter: str) -> ParseResult:
        """Parse Monobank CSV file bytes into structured transaction data."""
        text = file_bytes.decode(encoding)
        if text.startswith("\ufeff"):
            text = text[1:]
        reader = csv.reader(io.StringIO(text), delimiter=delimiter)

        try:
            header = next(reader)
        except StopIteration:
            return ParseResult()

        header = [col.strip() for col in header]

        # Resolve column indexes
        date_idx = _resolve_column_index(header, "date")
        desc_idx = _resolve_column_index(header, "description")
        mcc_idx = _resolve_column_index(header, "mcc")
        amount_idx = _resolve_column_index(header, "amount")
        balance_idx = _resolve_column_index(header, "balance")

        if date_idx is None or amount_idx is None:
            return ParseResult(
                flagged_rows=[FlaggedRow(
                    row_number=0,
                    raw_data=",".join(header),
                    reason="Required columns (date, amount) not found in header",
                )],
                total_rows=0,
                flagged_count=1,
            )

        transactions: list[TransactionData] = []
        flagged_rows: list[FlaggedRow] = []
        row_number = 1  # header is row 1, first data row will be row 2

        for row in reader:
            row_number += 1

            # Skip empty rows
            if not row or all(cell.strip() == "" for cell in row):
                continue

            try:
                raw_data = dict(zip(header, row))
                date = _parse_date(row[date_idx])
                description = row[desc_idx].strip() if desc_idx is not None and desc_idx < len(row) else ""
                mcc = _parse_mcc(row[mcc_idx]) if mcc_idx is not None and mcc_idx < len(row) else None
                amount = _parse_amount_kopiykas(row[amount_idx])
                balance = (
                    _parse_amount_kopiykas(row[balance_idx])
                    if balance_idx is not None and balance_idx < len(row) and row[balance_idx].strip()
                    else None
                )

                transactions.append(TransactionData(
                    date=date,
                    description=description,
                    mcc=mcc,
                    amount=amount,
                    balance=balance,
                    currency_code=980,
                    raw_data=raw_data,
                ))
            except (IndexError, ValueError, InvalidOperation) as exc:
                flagged_rows.append(FlaggedRow(
                    row_number=row_number,
                    raw_data=dict(zip(header, row)) if row else ",".join(row),
                    reason=str(exc),
                ))

        total_rows = len(transactions) + len(flagged_rows)
        return ParseResult(
            transactions=transactions,
            flagged_rows=flagged_rows,
            total_rows=total_rows,
            parsed_count=len(transactions),
            flagged_count=len(flagged_rows),
        )
