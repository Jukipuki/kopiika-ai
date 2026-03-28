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
    currency_code: int
    raw_data: dict


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
