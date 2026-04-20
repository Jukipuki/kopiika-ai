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
from app.services.currency import (
    DEFAULT_CURRENCY_CODE,
    UNKNOWN_CURRENCY_CODE,
    resolve_currency,
)

logger = logging.getLogger(__name__)

# Flexible header mappings to support both legacy and modern Monobank formats.
# The `amount` column stays pinned to the card-currency column (UAH): Transaction.amount
# must be comparable across rows for downstream aggregations. Foreign currency rows
# carry the operation currency in the `currency` column; amount remains in UAH.
HEADER_MAPPINGS: dict[str, list[str]] = {
    "date": ["Дата і час операції", "Дата i час операції", "Date and time"],
    "description": ["Опис операції", "Деталі операції", "Description"],
    "mcc": ["MCC"],
    "amount": ["Сума в валюті картки (UAH)", "Card currency amount, (UAH)"],
    "balance": ["Залишок на рахунку (UAH)", "Залишок після операції", "Balance"],
    "currency": ["Валюта", "Currency"],
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
        try:
            text = file_bytes.decode(encoding)
        except (UnicodeDecodeError, LookupError):
            logger.warning(
                "parser.decode_fallback",
                extra={"encoding": encoding, "parser": "monobank"},
            )
            text = file_bytes.decode("utf-8", errors="replace")
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
        currency_idx = _resolve_column_index(header, "currency")

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

                currency_code = DEFAULT_CURRENCY_CODE
                currency_alpha: str | None = None
                currency_unknown_raw: str | None = None
                if currency_idx is not None and currency_idx < len(row):
                    raw_currency = row[currency_idx].strip()
                    if raw_currency:
                        info = resolve_currency(raw_currency)
                        if info is not None:
                            currency_code = info.numeric_code
                            currency_alpha = info.alpha_code
                        else:
                            currency_code = UNKNOWN_CURRENCY_CODE
                            currency_unknown_raw = raw_currency.upper()
                            logger.warning(
                                "currency_unknown",
                                extra={"raw_currency": currency_unknown_raw, "parser": "monobank"},
                            )

                transactions.append(TransactionData(
                    date=date,
                    description=description,
                    mcc=mcc,
                    amount=amount,
                    balance=balance,
                    currency_code=currency_code,
                    raw_data=raw_data,
                    currency_alpha=currency_alpha,
                    currency_unknown_raw=currency_unknown_raw,
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
