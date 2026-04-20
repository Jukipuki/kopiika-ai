import csv
import io
import logging
from dataclasses import dataclass

from charset_normalizer import from_bytes

logger = logging.getLogger(__name__)

# Monobank exports vary across time — match on characteristic substrings
# that appear in headers regardless of exact wording.
# Grouped by language so each export only needs to match ONE group.
MONOBANK_FINGERPRINT_GROUPS: list[list[str]] = [
    ["MCC", "валюті картки", "кешбек"],               # Ukrainian export
    ["MCC", "card currency amount", "cashback amount"], # English export
]

# Legacy exact-match set (older Monobank exports with semicolons / Win-1251)
MONOBANK_LEGACY_COLUMNS = {
    "Дата і час операції",
    "Опис операції",
    "MCC",
    "Сума в валюті картки (UAH)",
    "Залишок на рахунку (UAH)",
}

PRIVATBANK_REQUIRED_COLUMNS = {
    "Дата операції",
    "Опис операції",
    "Категорія",
    "Сума",
    "Валюта",
}

BANK_DISPLAY_NAMES: dict[str, str] = {
    "monobank": "Monobank",
    "privatbank": "PrivatBank",
}


def get_bank_display_name(detected_format: str | None) -> str | None:
    """Return a human-readable bank name for a detected format identifier.

    Returns None for unknown / missing formats so the frontend can fall back
    to its localized "Bank statement detected" copy.
    """
    if not detected_format:
        return None
    return BANK_DISPLAY_NAMES.get(detected_format)


_SIGN_CONVENTIONS: dict[str, str] = {
    "monobank": "negative_is_outflow",
    "privatbank": "negative_is_outflow",
}


def get_sign_convention(detected_format: str | None) -> str | None:
    """Return the amount sign convention for a detected format, or None if unknown."""
    if not detected_format:
        return None
    return _SIGN_CONVENTIONS.get(detected_format)


@dataclass
class FormatDetectionResult:
    bank_format: str  # "monobank" | "privatbank" | "unknown"
    encoding: str  # "windows-1251" | "utf-8" | etc.
    delimiter: str  # ";" | "," | "\t"
    column_count: int
    confidence_score: float  # 0.0 - 1.0
    header_row: list[str]
    # Known-bank sign semantic; None for unknown formats (validator skips Rule 4 then).
    amount_sign_convention: str | None = None


_MOJIBAKE_THRESHOLD = 0.05


def detect_mojibake(descriptions: list[str]) -> tuple[bool, float]:
    """Detect mojibake (encoding corruption) by counting U+FFFD replacement chars.

    Returns (is_mojibake, replacement_char_rate). Threshold: rate > 5% flags mojibake.
    """
    if not descriptions:
        return False, 0.0
    total_chars = sum(len(d) for d in descriptions)
    if total_chars == 0:
        return False, 0.0
    replacement_count = sum(d.count("\ufffd") for d in descriptions)
    rate = replacement_count / total_chars
    return rate > _MOJIBAKE_THRESHOLD, rate


def detect_encoding(file_bytes: bytes) -> tuple[str, float]:
    """Detect file encoding using charset-normalizer."""
    result = from_bytes(file_bytes).best()
    if result is None:
        return "utf-8", 0.0
    encoding = result.encoding
    # Normalize common encoding names
    if encoding.lower() in ("cp1251", "windows-1251"):
        encoding = "windows-1251"
    return encoding, result.coherence


def _decode_content(file_bytes: bytes, encoding: str) -> str:
    """Decode file bytes to string with the detected encoding."""
    return file_bytes.decode(encoding)


def _detect_delimiter(text: str) -> str:
    """Detect CSV delimiter using csv.Sniffer."""
    try:
        # Use first few lines for sniffing
        sample = "\n".join(text.splitlines()[:5])
        dialect = csv.Sniffer().sniff(sample, delimiters=";,\t")
        return dialect.delimiter
    except csv.Error:
        # Default to comma if sniffing fails
        return ","


def _parse_header(text: str, delimiter: str) -> list[str]:
    """Parse the header row from CSV text."""
    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    try:
        header = next(reader)
        return [col.strip() for col in header]
    except StopIteration:
        return []


def _check_monobank(header: list[str]) -> float:
    """Check if headers match Monobank CSV format. Returns confidence score.

    Uses substring fingerprints to handle Monobank's evolving export formats
    (column renames, Latin/Cyrillic i, quoting changes, encoding changes).
    Falls back to legacy exact-match for older exports.
    """
    joined = " ".join(header).lower()

    # Fingerprint matching — best score across language groups
    fp_score = 0.0
    for group in MONOBANK_FINGERPRINT_GROUPS:
        matched = sum(1 for fp in group if fp.lower() in joined)
        if matched >= 2:
            fp_score = max(fp_score, matched / len(group))

    # Legacy exact-match
    header_set = set(header)
    legacy_matched = MONOBANK_LEGACY_COLUMNS & header_set
    legacy_score = len(legacy_matched) / len(MONOBANK_LEGACY_COLUMNS) if legacy_matched else 0.0

    return max(fp_score, legacy_score)


def _check_privatbank(header: list[str]) -> float:
    """Check if headers match PrivatBank CSV format. Returns confidence score."""
    header_set = set(header)
    matched = PRIVATBANK_REQUIRED_COLUMNS & header_set
    if len(matched) == 0:
        return 0.0
    return len(matched) / len(PRIVATBANK_REQUIRED_COLUMNS)


def detect_format(
    file_bytes: bytes,
    encoding: str | None = None,
    encoding_confidence: float | None = None,
) -> FormatDetectionResult:
    """Detect bank format from CSV file bytes.

    Uses a registry pattern: each bank detector checks header patterns
    and returns a confidence score. The highest-scoring match wins.
    """
    if encoding is None:
        encoding, encoding_confidence = detect_encoding(file_bytes)
    if encoding_confidence is None:
        encoding_confidence = 0.0

    try:
        text = _decode_content(file_bytes, encoding)
    except (UnicodeDecodeError, LookupError):
        # Fallback to utf-8
        encoding = "utf-8"
        text = file_bytes.decode("utf-8", errors="replace")

    delimiter = _detect_delimiter(text)
    header = _parse_header(text, delimiter)

    # Check each bank format
    monobank_score = _check_monobank(header)
    privatbank_score = _check_privatbank(header)

    # Determine best match
    if monobank_score >= 0.6:
        bank_format = "monobank"
        confidence = monobank_score
    elif privatbank_score >= 0.8:
        bank_format = "privatbank"
        confidence = privatbank_score
    else:
        bank_format = "unknown"
        confidence = max(monobank_score, privatbank_score, 0.0)

    logger.info(
        "Format detection complete",
        extra={
            "bank_format": bank_format,
            "encoding": encoding,
            "encoding_coherence": encoding_confidence,
            "encoding_chaos": max(0.0, 1.0 - encoding_confidence),
            "delimiter": repr(delimiter),
            "column_count": len(header),
            "confidence": confidence,
        },
    )

    return FormatDetectionResult(
        bank_format=bank_format,
        encoding=encoding,
        delimiter=delimiter,
        column_count=len(header),
        confidence_score=confidence,
        header_row=header,
        amount_sign_convention=get_sign_convention(bank_format),
    )
