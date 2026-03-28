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

# PrivatBank CSV columns (all 5 required by format_detector)
COLUMN_DATE = "Дата операції"
COLUMN_DESCRIPTION = "Опис операції"
COLUMN_CATEGORY = "Категорія"
COLUMN_AMOUNT = "Сума"
COLUMN_CURRENCY = "Валюта"

EXPECTED_COLUMNS = [COLUMN_DATE, COLUMN_DESCRIPTION, COLUMN_CATEGORY, COLUMN_AMOUNT, COLUMN_CURRENCY]

# ISO 4217 numeric currency codes
CURRENCY_MAP: dict[str, int] = {
    "UAH": 980,
    "USD": 840,
    "EUR": 978,
    "GBP": 826,
    "PLN": 985,
}

DEFAULT_CURRENCY_CODE = 980  # UAH


def _resolve_column_index(header: list[str], column_name: str) -> int | None:
    """Find the column index by exact header name."""
    for i, col in enumerate(header):
        if col.strip() == column_name:
            return i
    return None


def _parse_date(value: str) -> datetime:
    """Parse PrivatBank date format DD.MM.YYYY HH:MM:SS to naive datetime."""
    return datetime.strptime(value.strip(), "%d.%m.%Y %H:%M:%S")


def _parse_amount_kopiykas(value: str) -> int:
    """Convert decimal amount string to integer kopiykas using Decimal for precision.

    Handles both period (.) and comma (,) decimal separators.
    """
    normalized = value.strip().replace(",", ".")
    return int(round(Decimal(normalized) * 100))


def _resolve_currency_code(value: str) -> int:
    """Map currency string to ISO 4217 numeric code."""
    stripped = value.strip().upper()
    code = CURRENCY_MAP.get(stripped)
    if code is None:
        logger.warning("Unknown currency '%s', defaulting to UAH (980)", stripped)
        return DEFAULT_CURRENCY_CODE
    return code


class PrivatBankParser(AbstractParser):
    def parse(self, file_bytes: bytes, encoding: str, delimiter: str) -> ParseResult:
        """Parse PrivatBank CSV file bytes into structured transaction data."""
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
        date_idx = _resolve_column_index(header, COLUMN_DATE)
        desc_idx = _resolve_column_index(header, COLUMN_DESCRIPTION)
        cat_idx = _resolve_column_index(header, COLUMN_CATEGORY)
        amount_idx = _resolve_column_index(header, COLUMN_AMOUNT)
        currency_idx = _resolve_column_index(header, COLUMN_CURRENCY)

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
        row_number = 1  # header is row 1

        for row in reader:
            row_number += 1

            # Skip empty rows
            if not row or all(cell.strip() == "" for cell in row):
                continue

            try:
                raw_data = dict(zip(header, row))
                date = _parse_date(row[date_idx])
                description = row[desc_idx].strip() if desc_idx is not None and desc_idx < len(row) else ""
                amount = _parse_amount_kopiykas(row[amount_idx])

                # Resolve currency code from currency column
                currency_code = DEFAULT_CURRENCY_CODE
                if currency_idx is not None and currency_idx < len(row):
                    currency_code = _resolve_currency_code(row[currency_idx])

                transactions.append(TransactionData(
                    date=date,
                    description=description,
                    mcc=None,  # PrivatBank CSV has no MCC column
                    amount=amount,
                    balance=None,  # PrivatBank CSV has no balance column
                    currency_code=currency_code,
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
