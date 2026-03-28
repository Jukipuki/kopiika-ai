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

# Heuristic keywords for column detection (Ukrainian + English)
DATE_KEYWORDS = ["дата", "date"]
AMOUNT_KEYWORDS = ["сума", "amount", "sum"]
DESCRIPTION_KEYWORDS = ["опис", "description", "призначення"]
CURRENCY_KEYWORDS = ["валюта", "currency"]

# ISO 4217 numeric currency codes
CURRENCY_MAP: dict[str, int] = {
    "UAH": 980,
    "USD": 840,
    "EUR": 978,
    "GBP": 826,
    "PLN": 985,
}

# Date formats to try in order
DATE_FORMATS = [
    "%d.%m.%Y %H:%M:%S",
    "%d.%m.%Y",
    "%Y-%m-%d",
    "%d/%m/%Y",
]

DEFAULT_CURRENCY_CODE = 980  # UAH


def _find_column_by_keywords(header: list[str], keywords: list[str]) -> int | None:
    """Find column index where header contains any of the keywords (case-insensitive)."""
    for i, col in enumerate(header):
        col_lower = col.strip().lower()
        for keyword in keywords:
            if keyword in col_lower:
                return i
    return None


def _parse_date_flexible(value: str) -> datetime:
    """Try multiple date formats and return the first successful parse."""
    stripped = value.strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(stripped, fmt)
        except ValueError:
            continue
    raise ValueError(f"Unable to parse date: {stripped}")


def _parse_amount_kopiykas(value: str) -> int:
    """Convert decimal amount string to integer kopiykas.

    Handles both period (.) and comma (,) decimal separators.
    """
    normalized = value.strip().replace(",", ".")
    return int(round(Decimal(normalized) * 100))


class GenericParser(AbstractParser):
    def parse(self, file_bytes: bytes, encoding: str, delimiter: str) -> ParseResult:
        """Attempt to parse a CSV with unrecognized format using column heuristics."""
        text = file_bytes.decode(encoding)
        if text.startswith("\ufeff"):
            text = text[1:]
        reader = csv.reader(io.StringIO(text), delimiter=delimiter)

        try:
            header = next(reader)
        except StopIteration:
            return ParseResult()

        header = [col.strip() for col in header]

        # Heuristic column detection
        date_idx = _find_column_by_keywords(header, DATE_KEYWORDS)
        amount_idx = _find_column_by_keywords(header, AMOUNT_KEYWORDS)
        desc_idx = _find_column_by_keywords(header, DESCRIPTION_KEYWORDS)
        currency_idx = _find_column_by_keywords(header, CURRENCY_KEYWORDS)

        # Minimum required: date + amount
        if date_idx is None or amount_idx is None:
            return ParseResult(
                flagged_rows=[FlaggedRow(
                    row_number=0,
                    raw_data=",".join(header),
                    reason="This file format is not yet supported. Could not detect required date and amount columns.",
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
                date = _parse_date_flexible(row[date_idx])
                amount = _parse_amount_kopiykas(row[amount_idx])
                description = row[desc_idx].strip() if desc_idx is not None and desc_idx < len(row) else ""

                currency_code = DEFAULT_CURRENCY_CODE
                if currency_idx is not None and currency_idx < len(row):
                    currency_str = row[currency_idx].strip().upper()
                    currency_code = CURRENCY_MAP.get(currency_str, DEFAULT_CURRENCY_CODE)
                    if currency_str and currency_str not in CURRENCY_MAP:
                        logger.warning("Unknown currency '%s', defaulting to UAH (980)", currency_str)

                transactions.append(TransactionData(
                    date=date,
                    description=description,
                    mcc=None,
                    amount=amount,
                    balance=None,
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
