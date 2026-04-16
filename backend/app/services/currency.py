"""Central CURRENCY_MAP — single source of truth for ISO 4217 currency codes
supported by the ingestion parsers and transaction API.

Allowed imports from:
  - app.agents.ingestion.parsers.* (pure-data module, no ORM/I/O)
  - app.api.v1.transactions
  - app.services.*
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class CurrencyInfo:
    numeric_code: int   # ISO 4217 numeric (e.g., 980)
    alpha_code: str     # ISO 4217 alpha-3 (e.g., "UAH")
    symbol: str         # Display symbol (e.g., "₴", "CHF" for currencies without a unique glyph)


CURRENCY_MAP: dict[str, CurrencyInfo] = {
    "UAH": CurrencyInfo(980, "UAH", "₴"),
    "USD": CurrencyInfo(840, "USD", "$"),
    "EUR": CurrencyInfo(978, "EUR", "€"),
    "GBP": CurrencyInfo(826, "GBP", "£"),
    "PLN": CurrencyInfo(985, "PLN", "zł"),
    "CHF": CurrencyInfo(756, "CHF", "CHF"),  # No widely-recognized glyph; use ISO code
    "JPY": CurrencyInfo(392, "JPY", "¥"),
    "CZK": CurrencyInfo(203, "CZK", "Kč"),
    "TRY": CurrencyInfo(949, "TRY", "₺"),
}

# UAH numeric — used only by parsers with NO currency column (legacy Monobank 5-col format).
DEFAULT_CURRENCY_CODE: int = 980

# Sentinel for unrecognized alpha codes. 0 is not a valid ISO 4217 numeric (codes are 100–999)
# so it cannot collide with any legitimate currency.
UNKNOWN_CURRENCY_CODE: int = 0

# Numeric → alpha lookup used by the transaction API serializer.
_NUMERIC_TO_ALPHA: dict[int, str] = {info.numeric_code: info.alpha_code for info in CURRENCY_MAP.values()}


def resolve_currency(raw: str | None) -> CurrencyInfo | None:
    """Return CurrencyInfo for a recognized alpha code (case-insensitive, whitespace-trimmed); None otherwise."""
    if raw is None:
        return None
    return CURRENCY_MAP.get(raw.strip().upper())


def alpha_for_numeric(numeric: int) -> str | None:
    """Return ISO 4217 alpha-3 for a recognized numeric code; None otherwise."""
    return _NUMERIC_TO_ALPHA.get(numeric)


def extract_raw_currency(raw_data: dict | None) -> str | None:
    """Best-effort recovery of the raw alpha currency string from a parsed CSV row.

    Looks for common currency-column names. Returns trimmed/uppercased value or None.
    """
    if not raw_data:
        return None
    for key in ("Валюта", "Currency"):
        value = raw_data.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip().upper()
    return None
