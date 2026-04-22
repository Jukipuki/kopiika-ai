"""Generic-schema parser that applies a mapping produced by AI schema detection.

Story 11.7 introduced AI-assisted detection; Story 11.10 promotes counterparty
signals to first-class `TransactionData` fields (TD-049 resolution). Given a
`mapping: dict` (from `resolve_bank_format`), parse a CSV file deterministically
into the shared `ParseResult` shape, populating `counterparty_name` /
`counterparty_tax_id` / `counterparty_account` directly on the DTO when the
mapping exposes them.
"""
from __future__ import annotations

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

_COUNTERPARTY_MAPPING_KEYS: tuple[tuple[str, str], ...] = (
    ("counterparty_name_column", "counterparty_name"),
    ("counterparty_tax_id_column", "counterparty_tax_id"),
    ("counterparty_account_column", "counterparty_account"),
)
_FIRST_CLASS_COUNTERPARTY_FIELDS = {
    "counterparty_name",
    "counterparty_tax_id",
    "counterparty_account",
}


def _col_index(header: list[str], name: str | None) -> int | None:
    if not name:
        return None
    try:
        return header.index(name)
    except ValueError:
        return None


def _safe_cell(row: list[str], idx: int | None) -> str | None:
    if idx is None or idx >= len(row):
        return None
    value = row[idx]
    return value if value is not None else None


def _parse_amount_kopiykas(value: str) -> int:
    normalized = value.strip().replace("\u00a0", "").replace(" ", "").replace(",", ".")
    return int(round(Decimal(normalized) * 100))


def _parse_mcc(value: str | None) -> int | None:
    if not value:
        return None
    stripped = value.strip()
    if not stripped:
        return None
    try:
        return int(stripped)
    except ValueError:
        return None


class AIDetectedParser(AbstractParser):
    """Applies a detected mapping to parse a CSV statement.

    The mapping is produced by `app.services.schema_detection.resolve_bank_format`
    and contains the canonical column-mapping keys from tech spec §2.4. The
    delimiter is NOT taken from the mapping — the LLM never sees raw file bytes
    (the prompt shows cells already parsed and re-joined with " | "), so its
    delimiter guess is unreliable. The caller-supplied delimiter from the
    format detector is the authoritative source.
    """

    def __init__(self, mapping: dict):
        self._mapping = mapping

    def parse(self, file_bytes: bytes, encoding: str, delimiter: str) -> ParseResult:
        mapping = self._mapping

        try:
            text = file_bytes.decode(encoding)
        except (UnicodeDecodeError, LookupError):
            logger.warning(
                "parser.decode_fallback",
                extra={"encoding": encoding, "parser": "ai_detected"},
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

        date_idx = _col_index(header, mapping.get("date_column"))
        amount_idx = _col_index(header, mapping.get("amount_column"))
        desc_idx = _col_index(header, mapping.get("description_column"))
        currency_idx = _col_index(header, mapping.get("currency_column"))
        mcc_idx = _col_index(header, mapping.get("mcc_column"))
        balance_idx = _col_index(header, mapping.get("balance_column"))
        sign_convention = mapping.get("amount_sign_convention")
        date_format = mapping.get("date_format") or "%Y-%m-%d"

        # Counterparty lookups — may all be None; that's fine.
        counterparty_idxs: list[tuple[str, int]] = []
        for mapping_key, field_name in _COUNTERPARTY_MAPPING_KEYS:
            idx = _col_index(header, mapping.get(mapping_key))
            if idx is not None:
                counterparty_idxs.append((field_name, idx))

        if date_idx is None or amount_idx is None:
            return ParseResult(
                flagged_rows=[
                    FlaggedRow(
                        row_number=0,
                        raw_data=",".join(header),
                        reason="ai_detected: date/amount columns missing from mapping",
                    )
                ],
                total_rows=0,
                flagged_count=1,
            )

        transactions: list[TransactionData] = []
        flagged_rows: list[FlaggedRow] = []
        row_number = 1  # header was row 1

        for row in reader:
            row_number += 1
            if not row or all(cell.strip() == "" for cell in row):
                continue

            try:
                raw_data: dict = dict(zip(header, row))
                raw_date = row[date_idx]
                date = datetime.strptime(raw_date.strip(), date_format)

                raw_amount = row[amount_idx]
                amount = _parse_amount_kopiykas(raw_amount)
                # sign_convention is consumed by parse_validator (soft warning
                # on opposite-polarity rows); the parser itself does not flip
                # signs — both `positive_is_income` and `negative_is_outflow`
                # describe signed amounts that already match Kopiika's
                # canonical convention. See TD-051 for unsigned/split-column
                # formats that would require real transformation here.
                _ = sign_convention

                description = (
                    row[desc_idx].strip()
                    if desc_idx is not None and desc_idx < len(row)
                    else ""
                )
                mcc = _parse_mcc(_safe_cell(row, mcc_idx))
                balance_cell = _safe_cell(row, balance_idx)
                balance = (
                    _parse_amount_kopiykas(balance_cell)
                    if balance_cell and balance_cell.strip()
                    else None
                )

                currency_code = DEFAULT_CURRENCY_CODE
                currency_alpha: str | None = None
                currency_unknown_raw: str | None = None
                raw_currency = _safe_cell(row, currency_idx)
                if raw_currency and raw_currency.strip():
                    info = resolve_currency(raw_currency.strip())
                    if info is not None:
                        currency_code = info.numeric_code
                        currency_alpha = info.alpha_code
                    else:
                        currency_code = UNKNOWN_CURRENCY_CODE
                        currency_unknown_raw = raw_currency.strip().upper()
                        logger.warning(
                            "currency_unknown",
                            extra={
                                "raw_currency": currency_unknown_raw,
                                "parser": "ai_detected",
                            },
                        )

                counterparty_values: dict[str, str | None] = {
                    "counterparty_name": None,
                    "counterparty_tax_id": None,
                    "counterparty_account": None,
                }
                for field_name, idx in counterparty_idxs:
                    value = _safe_cell(row, idx)
                    if value is not None and value.strip():
                        counterparty_values[field_name] = value.strip()

                transactions.append(
                    TransactionData(
                        date=date,
                        description=description,
                        mcc=mcc,
                        amount=amount,
                        balance=balance,
                        currency_code=currency_code,
                        raw_data=raw_data,
                        currency_alpha=currency_alpha,
                        currency_unknown_raw=currency_unknown_raw,
                        counterparty_name=counterparty_values["counterparty_name"],
                        counterparty_tax_id=counterparty_values["counterparty_tax_id"],
                        counterparty_account=counterparty_values["counterparty_account"],
                    )
                )
            except (IndexError, ValueError, InvalidOperation) as exc:
                flagged_rows.append(
                    FlaggedRow(
                        row_number=row_number,
                        raw_data=dict(zip(header, row)) if row else ",".join(row),
                        reason=str(exc),
                    )
                )

        total_rows = len(transactions) + len(flagged_rows)
        return ParseResult(
            transactions=transactions,
            flagged_rows=flagged_rows,
            total_rows=total_rows,
            parsed_count=len(transactions),
            flagged_count=len(flagged_rows),
        )
