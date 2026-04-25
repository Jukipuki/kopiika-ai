"""AI-assisted schema detection for bank-statement CSVs.

Story 11.7 / ADR-0002. Given a header row + a few sample rows, the LLM returns
a structural column mapping (date/amount/description/etc). Mappings are keyed
by a SHA-256 fingerprint of the canonical header form and cached in
`bank_format_registry` — so each NEW format costs one LLM call total, and every
subsequent upload of the same format hits the cache.

Public surface:
    header_fingerprint(header_row)         -> str (hex SHA-256)
    detect_schema(header_row, sample_rows, encoding) -> DetectedSchema
    resolve_bank_format(...)               -> ResolvedFormat
    SchemaDetectionFailed                  exception

Out of scope (per story Anti-Scope): consuming counterparty fields in the
categorization pipeline (TD-049), operator UI, auto-repairing suspect
detections.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
import time
import unicodedata
from dataclasses import dataclass
from typing import Literal, Optional

from sqlalchemy import select
from sqlmodel import Session

from app.agents.circuit_breaker import (
    CircuitBreakerOpenError,
    record_failure,
    record_success,
)
from app.agents.llm import get_llm_client
from app.models.bank_format_registry import BankFormatRegistry, _utcnow

logger = logging.getLogger(__name__)

# Maximum number of sample rows to include in the prompt. More rows = better
# structural inference, but also more tokens and more chance of exposing
# transaction values. Five is the sweet spot observed during spike work.
_MAX_SAMPLE_ROWS = 5

# Mapping keys that MUST appear in every persisted mapping per tech spec §2.4.
_REQUIRED_MAPPING_KEYS: tuple[str, ...] = (
    "date_column",
    "date_format",
    "amount_column",
    "amount_sign_convention",
    "description_column",
    "currency_column",
    "mcc_column",
    "balance_column",
    "encoding_hint",
)

# Optional counterparty keys — persisted verbatim if the LLM returns them, but
# not consumed by the downstream pipeline in this story (TD-049 territory).
_COUNTERPARTY_KEYS: tuple[str, ...] = (
    "counterparty_name_column",
    "counterparty_tax_id_column",
    "counterparty_account_column",
    "counterparty_currency_column",
)

_VALID_SIGN_CONVENTIONS: frozenset[str] = frozenset(
    ("positive_is_income", "negative_is_outflow")
)


class SchemaDetectionFailed(Exception):
    """Raised when AI schema detection cannot produce a usable mapping.

    The caller is expected to catch this and fall back to `generic.py`.
    """


@dataclass
class DetectedSchema:
    detected_mapping: dict
    detection_confidence: float
    detected_bank_hint: Optional[str]


@dataclass
class ResolvedFormat:
    mapping: dict
    source: Literal["cached_override", "cached_detected", "llm_detected"]


def header_fingerprint(header_row: list[str]) -> str:
    """SHA-256 hex of the canonical header form per tech spec §6.1.

    Canonical form: each header NFKC-normalized, stripped, lowercased, joined
    with `|`. Column ORDER is preserved — a reordered header IS a different
    format because it changes which column index means which field.
    """
    canonical = "|".join(
        unicodedata.normalize("NFKC", col).strip().lower() for col in header_row
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _build_prompt(
    header_row: list[str], sample_rows: list[list[str]], encoding: str
) -> str:
    header_lines = "\n".join(
        f'  {i}. "{col}"' for i, col in enumerate(header_row)
    )
    sample_lines = "\n".join(
        "  " + " | ".join(cell for cell in row)
        for row in sample_rows[:_MAX_SAMPLE_ROWS]
    )
    return f"""You are inferring the column structure of a bank-statement CSV.
Use the sample rows as format exemplars — they tell you the date format,
decimal separator, currency code shape, and sign convention. Do not
categorize or interpret transaction content; only produce the column mapping.

Headers (positional, 0-indexed):
{header_lines}

Sample rows (up to {_MAX_SAMPLE_ROWS}, same order as headers):
{sample_lines}

Detected encoding: {encoding}

Return ONLY a JSON object matching this shape:
{{
  "date_column": "<exact header string from the list above>",
  "date_format": "<Python strptime format string, e.g. %d.%m.%Y %H:%M:%S>",
  "amount_column": "<header>",
  "amount_sign_convention": "positive_is_income" | "negative_is_outflow",
  "description_column": "<header>",
  "currency_column": "<header>" | null,
  "mcc_column": "<header>" | null,
  "balance_column": "<header>" | null,
  "encoding_hint": "<encoding>",
  "counterparty_name_column": "<header>" | null,
  "counterparty_tax_id_column": "<header>" | null,
  "counterparty_account_column": "<header>" | null,
  "counterparty_currency_column": "<header>" | null,
  "confidence": <float 0.0-1.0>,
  "bank_hint": "<your best guess of the bank/format name, or null>"
}}

Do not invent columns that are not in the header list.
If a concept has no matching header, set it to null.
If you cannot determine the format at all, return {{"confidence": 0.0}} with
all other fields set to null — this triggers the fallback parser."""


_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(.+?)\s*```", re.DOTALL)


def _extract_json(raw: str) -> dict:
    """Parse the first JSON object from raw LLM text.

    Accepts bare JSON or JSON wrapped in a ```json ... ``` fence. Raises
    ValueError on anything that isn't a valid JSON object.
    """
    match = _JSON_FENCE_RE.search(raw)
    body = match.group(1) if match else raw
    body = body.strip()
    # Trim any leading prose before the first '{'.
    start = body.find("{")
    end = body.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("no JSON object found in response")
    return json.loads(body[start : end + 1])


def _validate_mapping_shape(payload: dict, header_row: list[str]) -> None:
    """Verify the LLM payload has the required keys and consistent values."""
    missing = [k for k in _REQUIRED_MAPPING_KEYS if k not in payload]
    if missing:
        raise ValueError(f"missing required keys: {missing}")

    # amount_sign_convention must be one of the two known sentinels.
    conv = payload.get("amount_sign_convention")
    if conv not in _VALID_SIGN_CONVENTIONS:
        raise ValueError(f"invalid amount_sign_convention: {conv!r}")

    # Every named column must actually appear in the header row.
    header_set = set(header_row)
    for key in (
        "date_column",
        "amount_column",
        "description_column",
        "currency_column",
        "mcc_column",
        "balance_column",
        *_COUNTERPARTY_KEYS,
    ):
        value = payload.get(key)
        if value is not None and value not in header_set:
            raise ValueError(
                f"{key}={value!r} not in header row"
            )


def detect_schema(
    header_row: list[str],
    sample_rows: list[list[str]],
    encoding: str,
) -> DetectedSchema:
    """Call the LLM to infer a column mapping for this header.

    Raises:
        SchemaDetectionFailed: if the LLM is unreachable, returns invalid JSON,
            returns a shape that violates the contract, or reports confidence
            of 0.0 (explicit giveup).
    """
    prompt = _build_prompt(header_row, sample_rows, encoding)

    try:
        llm = get_llm_client()
    except CircuitBreakerOpenError as exc:
        raise SchemaDetectionFailed(
            f"circuit breaker open: {exc}"
        ) from exc

    try:
        response = llm.invoke(prompt)
        record_success("anthropic")
    except CircuitBreakerOpenError as exc:
        raise SchemaDetectionFailed(
            f"circuit breaker open: {exc}"
        ) from exc
    except Exception as exc:
        record_failure("anthropic")
        raise SchemaDetectionFailed(
            f"LLM invocation failed: {exc}"
        ) from exc

    raw_text = getattr(response, "content", response)
    if isinstance(raw_text, list):
        # LangChain may return a list of content blocks; concatenate text.
        raw_text = "".join(
            block.get("text", "") if isinstance(block, dict) else str(block)
            for block in raw_text
        )

    try:
        payload = _extract_json(raw_text)
    except (ValueError, json.JSONDecodeError) as exc:
        raise SchemaDetectionFailed(
            f"LLM returned invalid JSON: {exc}"
        ) from exc

    confidence = payload.get("confidence")
    if confidence is None or not isinstance(confidence, (int, float)):
        raise SchemaDetectionFailed("confidence missing or not numeric")
    if confidence <= 0.0:
        raise SchemaDetectionFailed("LLM reported zero confidence (giveup)")

    try:
        _validate_mapping_shape(payload, header_row)
    except ValueError as exc:
        raise SchemaDetectionFailed(
            f"LLM response shape invalid: {exc}"
        ) from exc

    bank_hint = payload.get("bank_hint")
    # Defensive truncation: the column is VARCHAR(255) (widened from 64 on
    # 2026-04-22). LLM prompts evolve; cap the free-text hint so any future
    # prompt drift can't surface as a StringDataRightTruncation at write time.
    if isinstance(bank_hint, str) and len(bank_hint) > 255:
        bank_hint = bank_hint[:255]
    # Assemble the canonical mapping: required keys first, then any
    # counterparty keys the LLM populated. Drop `confidence` and `bank_hint`
    # from the persisted mapping itself — those live on their own columns.
    mapping: dict = {k: payload.get(k) for k in _REQUIRED_MAPPING_KEYS}
    for k in _COUNTERPARTY_KEYS:
        if k in payload:
            mapping[k] = payload.get(k)

    return DetectedSchema(
        detected_mapping=mapping,
        detection_confidence=float(confidence),
        detected_bank_hint=bank_hint,
    )


def _emit_detection_event(
    *,
    upload_id: Optional[str],
    user_id: Optional[str],
    fingerprint: str,
    source: str,
    detection_confidence: Optional[float],
    latency_ms: int,
    suspect_detection: bool = False,
    extra: Optional[dict] = None,
) -> None:
    payload = {
        "upload_id": upload_id,
        "user_id": user_id,
        "fingerprint": fingerprint,
        "source": source,
        "detection_confidence": detection_confidence,
        "latency_ms": latency_ms,
    }
    if suspect_detection:
        payload["suspect_detection"] = True
    if extra:
        payload.update(extra)
    logger.info("parser.schema_detection", extra=payload)


def resolve_bank_format(
    header_row: list[str],
    sample_rows: list[list[str]],
    encoding: str,
    db_session: Session,
    *,
    upload_id: Optional[str] = None,
    user_id: Optional[str] = None,
) -> ResolvedFormat:
    """Lookup-then-detect: check the registry first, detect + persist on miss.

    See tech spec §6.3 for the full flow. Raises `SchemaDetectionFailed` if
    the LLM path fails on a cache miss — the caller falls back to `generic.py`.
    """
    fingerprint = header_fingerprint(header_row)
    stmt = select(BankFormatRegistry).where(
        BankFormatRegistry.header_fingerprint == fingerprint
    )
    existing = db_session.execute(stmt).scalar_one_or_none()

    if existing is not None:
        if existing.override_mapping is not None:
            mapping = existing.override_mapping
            source: Literal[
                "cached_override", "cached_detected", "llm_detected"
            ] = "cached_override"
            confidence = existing.detection_confidence
        else:
            mapping = existing.detected_mapping
            source = "cached_detected"
            confidence = existing.detection_confidence

        existing.use_count = (existing.use_count or 0) + 1
        existing.last_used_at = _utcnow()
        db_session.add(existing)
        db_session.flush()

        _emit_detection_event(
            upload_id=upload_id,
            user_id=user_id,
            fingerprint=fingerprint,
            source=source,
            detection_confidence=confidence,
            latency_ms=0,
        )
        return ResolvedFormat(mapping=mapping, source=source)

    # Cache miss — invoke the LLM and persist.
    start = time.monotonic()
    try:
        detected = detect_schema(header_row, sample_rows, encoding)
    except SchemaDetectionFailed as exc:
        latency_ms = int(round((time.monotonic() - start) * 1000))
        # AC #4 requires the fallback event to carry the error reason; without
        # it the operator has no signal for why detection failed (quota, bad
        # JSON, shape violation, circuit breaker) beyond the raw exception log.
        _emit_detection_event(
            upload_id=upload_id,
            user_id=user_id,
            fingerprint=fingerprint,
            source="fallback_generic",
            detection_confidence=None,
            latency_ms=latency_ms,
            extra={"error_reason": str(exc)},
        )
        raise
    latency_ms = int(round((time.monotonic() - start) * 1000))

    sample_header_text = " | ".join(header_row)
    row = BankFormatRegistry(
        header_fingerprint=fingerprint,
        detected_mapping=detected.detected_mapping,
        detection_confidence=detected.detection_confidence,
        detected_bank_hint=detected.detected_bank_hint,
        sample_header=sample_header_text,
        use_count=1,
    )
    db_session.add(row)
    db_session.flush()

    _emit_detection_event(
        upload_id=upload_id,
        user_id=user_id,
        fingerprint=fingerprint,
        source="llm_detected",
        detection_confidence=detected.detection_confidence,
        latency_ms=latency_ms,
    )
    return ResolvedFormat(
        mapping=detected.detected_mapping, source="llm_detected"
    )


def emit_suspect_detection_event(
    *,
    upload_id: Optional[str],
    user_id: Optional[str],
    fingerprint: str,
    source: str,
    rejected_count: int,
    total_count: int,
) -> None:
    """Emit the `suspect_detection: true` variant per AC #9.

    Called after the validation layer runs, when > 30% of rows were rejected
    and the mapping came from the registry (cached or llm-detected). Does NOT
    mutate the registry — auto-repair is deferred per Dev Notes.
    """
    _emit_detection_event(
        upload_id=upload_id,
        user_id=user_id,
        fingerprint=fingerprint,
        source=source,
        detection_confidence=None,
        latency_ms=0,
        suspect_detection=True,
        extra={
            "rejected_count": rejected_count,
            "total_count": total_count,
        },
    )
