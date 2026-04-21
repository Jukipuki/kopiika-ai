from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class TransactionData:
    date: datetime
    description: str
    mcc: int | None
    amount: int  # kopiykas
    balance: int | None  # kopiykas
    currency_code: int  # ISO 4217 numeric; UNKNOWN_CURRENCY_CODE (0) when unrecognized
    raw_data: dict
    # Parser → parser_service handoff only (not persisted):
    # - currency_alpha: set to the ISO alpha-3 when the source row's currency was recognized.
    # - currency_unknown_raw: set to the raw trimmed/uppercased string when it was NOT recognized.
    # Mutually exclusive. Both None for rows without a currency column (legacy Monobank).
    currency_alpha: str | None = None
    currency_unknown_raw: str | None = None
    # Story 11.10: counterparty signals from PE-statement-style parsers. Card
    # parsers leave these as None; downstream consumers (categorization node,
    # user-IBAN registry) treat None as "no signal, fall back to description".
    counterparty_name: str | None = None
    counterparty_tax_id: str | None = None
    counterparty_account: str | None = None


@dataclass
class FlaggedRow:
    row_number: int
    raw_data: dict | str
    reason: str


@dataclass
class ParseResult:
    transactions: list[TransactionData] = field(default_factory=list)
    flagged_rows: list[FlaggedRow] = field(default_factory=list)
    total_rows: int = 0
    parsed_count: int = 0
    flagged_count: int = 0


class AbstractParser(ABC):
    @abstractmethod
    def parse(self, file_bytes: bytes, encoding: str, delimiter: str) -> ParseResult:
        """Parse file bytes into structured transaction data."""
