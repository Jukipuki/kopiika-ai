import csv
import io
import logging
import uuid
from dataclasses import dataclass, field

from sqlmodel import Session, select
from sqlmodel.ext.asyncio.session import AsyncSession as SQLModelAsyncSession

from app.agents.ingestion.parsers.ai_detected import AIDetectedParser
from app.agents.ingestion.parsers.base import AbstractParser
from app.agents.ingestion.parsers.generic import GenericParser
from app.agents.ingestion.parsers.monobank import MonobankParser
from app.agents.ingestion.parsers.privatbank import PrivatBankParser
from app.models.flagged_import_row import FlaggedImportRow
from app.models.transaction import Transaction
from app.services.format_detector import FormatDetectionResult, detect_mojibake
from app.services.parse_validator import validate_parsed_rows
from app.services.schema_detection import (
    SchemaDetectionFailed,
    emit_suspect_detection_event,
    header_fingerprint,
    resolve_bank_format,
)
from app.services.transaction_service import compute_dedup_hash

logger = logging.getLogger(__name__)

_PARSERS: dict[str, type[AbstractParser]] = {
    "monobank": MonobankParser,
    "privatbank": PrivatBankParser,
}

# Story 11.7: rate above which a detected mapping is flagged as "suspect"
# (AC #9). Matches the tech-spec threshold; Story 11.5 already rejects rows.
_SUSPECT_REJECTION_RATE = 0.30

# Max sample rows handed to the LLM for schema detection.
_MAX_SAMPLE_ROWS = 5


@dataclass
class ParseAndStoreResult:
    total_rows: int
    parsed_count: int
    flagged_count: int
    persisted_count: int
    duplicates_skipped: int = 0
    validation_rejected_count: int = 0
    validation_warnings_count: int = 0
    rejected_rows: list[dict] = field(default_factory=list)
    warnings: list[dict] = field(default_factory=list)
    mojibake_detected: bool = False
    mojibake_replacement_rate: float = 0.0
    # Story 11.7: which code path produced the parsed output. Values:
    #   "known_bank_parser" — Monobank/PrivatBank deterministic parser
    #   "cached_override"   — bank_format_registry hit with operator override
    #   "cached_detected"   — bank_format_registry hit with LLM-detected mapping
    #   "llm_detected"      — registry miss, LLM call produced a fresh mapping
    #   "fallback_generic"  — generic heuristic parser (known parser missing OR
    #                         LLM detection failed)
    schema_detection_source: str = "known_bank_parser"


def _register_self_counterparty_ibans(
    session: Session,
    user_id: uuid.UUID,
    upload_id: uuid.UUID,
    transactions: list,
) -> None:
    """Per Story 11.10 Task 5.2: register PE-statement self-transfer IBANs.

    For rows where `counterparty_name` matches the user's `full_name`
    (NFKC + casefold), insert the counterparty's IBAN into `user_iban_registry`.
    Batches into one flush to avoid N+1. Idempotent via the service.
    """
    import unicodedata

    from app.models.user import User
    from app.services.user_iban_registry import UserIbanRegistryService, iban_fingerprint

    user = session.get(User, user_id)
    if user is None or not getattr(user, "full_name", None):
        return

    user_name_canon = unicodedata.normalize("NFKC", user.full_name).strip().casefold()
    if not user_name_canon:
        return

    # Make pending new_txns visible to the registry's lookup SELECT regardless
    # of session-level autoflush settings.
    session.flush()

    svc = UserIbanRegistryService(session)
    seen_fingerprints: set[str] = set()
    for txn in transactions:
        name = (txn.counterparty_name or "").strip()
        account = (txn.counterparty_account or "").strip()
        if not name or not account:
            continue
        if unicodedata.normalize("NFKC", name).strip().casefold() != user_name_canon:
            continue
        fp = iban_fingerprint(account)
        if fp in seen_fingerprints:
            continue
        seen_fingerprints.add(fp)
        svc.register(
            user_id=user_id,
            iban_plaintext=account,
            label="PE counterparty (self)",
            first_seen_upload_id=upload_id,
        )


class UnsupportedFormatError(Exception):
    """Raised when no parser is available for the detected bank format."""


class WholesaleRejectionError(Exception):
    """Raised when validation rejects the entire parser output (e.g. suspicious_duplicate_rate)."""

    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(f"Wholesale rejection: {reason}")


def _extract_header_and_samples(
    file_bytes: bytes, encoding: str, delimiter: str
) -> tuple[list[str], list[list[str]]]:
    """Pull the header row and up to _MAX_SAMPLE_ROWS data rows out of raw bytes.

    Used to feed `resolve_bank_format` without paying for a full parse first.
    """
    try:
        text = file_bytes.decode(encoding)
    except (UnicodeDecodeError, LookupError):
        text = file_bytes.decode("utf-8", errors="replace")
    if text.startswith("\ufeff"):
        text = text[1:]
    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    try:
        header = [col.strip() for col in next(reader)]
    except StopIteration:
        return [], []
    samples: list[list[str]] = []
    for row in reader:
        if not row or all(cell.strip() == "" for cell in row):
            continue
        samples.append(row)
        if len(samples) >= _MAX_SAMPLE_ROWS:
            break
    return header, samples


def _select_parser_and_parse(
    session: Session | None,
    file_bytes: bytes,
    format_result: FormatDetectionResult,
    *,
    upload_id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
) -> tuple[object, str, FormatDetectionResult, str | None]:
    """Choose the parser for this upload per Story 11.7 precedence.

    Returns (parse_result, schema_detection_source, effective_format_result,
    fingerprint_or_none). `fingerprint_or_none` is populated only when a
    registry-backed mapping was used (needed for AC #9 suspect logging).
    """
    known = _PARSERS.get(format_result.bank_format)
    if known is not None:
        parser = known()
        result = parser.parse(
            file_bytes=file_bytes,
            encoding=format_result.encoding,
            delimiter=format_result.delimiter,
        )
        return result, "known_bank_parser", format_result, None

    # Unknown format — try AI-assisted schema detection first.
    if session is not None:
        header, samples = _extract_header_and_samples(
            file_bytes, format_result.encoding, format_result.delimiter
        )
        if header:
            try:
                resolved = resolve_bank_format(
                    header_row=header,
                    sample_rows=samples,
                    encoding=format_result.encoding,
                    db_session=session,
                    upload_id=str(upload_id) if upload_id else None,
                    user_id=str(user_id) if user_id else None,
                )
            except SchemaDetectionFailed:
                # resolve_bank_format already emitted a
                # `parser.schema_detection` event with source="fallback_generic"
                # and error_reason before raising. Don't double-log.
                pass
            else:
                ai_parser = AIDetectedParser(mapping=resolved.mapping)
                # Delimiter comes from the format detector, which sniffed the
                # raw bytes. The LLM only sees pre-parsed cells serialized with
                # " | " in the prompt, so anything it claimed about delimiters
                # was a guess based on our own serialization — don't trust it.
                effective = FormatDetectionResult(
                    bank_format=format_result.bank_format,
                    encoding=format_result.encoding,
                    delimiter=format_result.delimiter,
                    column_count=len(header),
                    confidence_score=format_result.confidence_score,
                    header_row=header,
                    amount_sign_convention=resolved.mapping.get(
                        "amount_sign_convention"
                    ),
                )
                result = ai_parser.parse(
                    file_bytes=file_bytes,
                    encoding=effective.encoding,
                    delimiter=effective.delimiter,
                )
                return (
                    result,
                    resolved.source,
                    effective,
                    header_fingerprint(header),
                )

    # Fallback — generic heuristic parser (either no session, empty header, or
    # LLM detection failed).
    generic = GenericParser()
    result = generic.parse(
        file_bytes=file_bytes,
        encoding=format_result.encoding,
        delimiter=format_result.delimiter,
    )
    if result.parsed_count == 0:
        raise UnsupportedFormatError(
            "This file format is not yet supported. "
            "Currently supported: Monobank CSV, PrivatBank CSV."
        )
    return result, "fallback_generic", format_result, None


def _parse_and_build_records(
    user_id: uuid.UUID,
    upload_id: uuid.UUID,
    file_bytes: bytes,
    format_result: FormatDetectionResult,
    session: Session | None,
) -> tuple[list[Transaction], list[FlaggedImportRow], ParseAndStoreResult]:
    """Parse file and build ORM objects. Shared by async and sync store functions."""
    result, schema_source, effective_format, fingerprint = _select_parser_and_parse(
        session=session,
        file_bytes=file_bytes,
        format_result=format_result,
        upload_id=upload_id,
        user_id=user_id,
    )

    validation = validate_parsed_rows(
        rows=result.transactions,
        amount_sign_convention=effective_format.amount_sign_convention,
    )
    if validation.wholesale_rejected:
        raise WholesaleRejectionError(validation.wholesale_rejection_reason or "unknown")

    # Story 11.7 AC #9: log a suspect-detection event when a registry-backed
    # mapping produced > 30% validation rejections. Do NOT mutate the registry —
    # auto-repair is deferred to an operator-facing story.
    if fingerprint and schema_source in ("cached_override", "cached_detected", "llm_detected"):
        total = len(result.transactions) + len(validation.rejected_rows)
        rejected = len(validation.rejected_rows)
        if total > 0 and (rejected / total) > _SUSPECT_REJECTION_RATE:
            emit_suspect_detection_event(
                upload_id=str(upload_id),
                user_id=str(user_id),
                fingerprint=fingerprint,
                source=schema_source,
                rejected_count=rejected,
                total_count=total,
            )

    descriptions = [txn.description or "" for txn in validation.accepted]
    mojibake_flag, mojibake_rate = detect_mojibake(descriptions)
    if mojibake_flag:
        # Detection-time event — fires the moment mojibake is spotted so an
        # operator can open the offending upload. An aggregate summary event
        # with the same name is emitted from processing_tasks.py at upload
        # completion; the two are deliberately kept distinct (Story 11.9).
        logger.warning(
            "parser.mojibake_detected",
            extra={
                "user_id": str(user_id),
                "upload_id": str(upload_id),
                "encoding": effective_format.encoding,
                "replacement_char_rate": mojibake_rate,
                "transaction_count": len(validation.accepted),
            },
        )

    transactions = [
        Transaction(
            user_id=user_id,
            upload_id=upload_id,
            date=txn_data.date,
            description=txn_data.description,
            mcc=txn_data.mcc,
            amount=txn_data.amount,
            balance=txn_data.balance,
            currency_code=txn_data.currency_code,
            raw_data=txn_data.raw_data,
            dedup_hash=compute_dedup_hash(
                user_id, txn_data.date, txn_data.amount, txn_data.description,
            ),
            is_flagged_for_review=txn_data.currency_unknown_raw is not None,
            uncategorized_reason=(
                "currency_unknown" if txn_data.currency_unknown_raw is not None else None
            ),
            counterparty_name=txn_data.counterparty_name,
            counterparty_tax_id=txn_data.counterparty_tax_id,
            counterparty_account=txn_data.counterparty_account,
        )
        for txn_data in validation.accepted
    ]

    validation_flagged = [
        FlaggedImportRow(
            user_id=user_id,
            upload_id=upload_id,
            row_number=fr.row_number,
            raw_data=fr.raw_data if isinstance(fr.raw_data, dict) else {"raw": fr.raw_data},
            reason=fr.reason,
        )
        for fr in validation.rejected_rows
    ]
    # Story 11.9: one structured event per rejected row so operators can chart
    # validation rejection rate by reason in CloudWatch Insights.
    for fr in validation.rejected_rows:
        logger.info(
            "parser.validation_rejected",
            extra={
                "user_id": str(user_id),
                "upload_id": str(upload_id),
                "row_number": fr.row_number,
                "reason": fr.reason,
            },
        )

    parser_flagged = [
        FlaggedImportRow(
            user_id=user_id,
            upload_id=upload_id,
            row_number=flagged.row_number,
            raw_data=flagged.raw_data if isinstance(flagged.raw_data, dict) else {"raw": flagged.raw_data},
            reason=flagged.reason,
        )
        for flagged in result.flagged_rows
    ]
    flagged_records = parser_flagged + validation_flagged

    rejected_rows_payload = [
        {
            "row_number": fr.row_number,
            "reason": fr.reason,
            "raw_row": fr.raw_data if isinstance(fr.raw_data, dict) else {"raw": fr.raw_data},
        }
        for fr in validation.rejected_rows
    ]
    warnings_payload = [
        {"row_number": fr.row_number, "reason": fr.reason}
        for fr in validation.warnings
    ]

    persisted_count = len(transactions) + len(flagged_records)
    store_result = ParseAndStoreResult(
        total_rows=result.total_rows,
        parsed_count=result.parsed_count,
        flagged_count=result.flagged_count + len(validation.rejected_rows),
        persisted_count=persisted_count,
        validation_rejected_count=len(validation.rejected_rows),
        validation_warnings_count=len(validation.warnings),
        rejected_rows=rejected_rows_payload,
        warnings=warnings_payload,
        mojibake_detected=mojibake_flag,
        mojibake_replacement_rate=mojibake_rate,
        schema_detection_source=schema_source,
    )

    return transactions, flagged_records, store_result


def _filter_duplicates(
    transactions: list[Transaction],
    existing_hashes: set[str],
) -> tuple[list[Transaction], int]:
    """Filter out transactions whose dedup_hash already exists.

    Returns (new_transactions, duplicates_skipped_count).
    """
    new_txns = []
    seen: set[str] = set()
    duplicates = 0
    for txn in transactions:
        if txn.dedup_hash in existing_hashes or txn.dedup_hash in seen:
            duplicates += 1
        else:
            seen.add(txn.dedup_hash)
            new_txns.append(txn)
    return new_txns, duplicates


async def parse_and_store_transactions(
    session: SQLModelAsyncSession,
    user_id: uuid.UUID,
    upload_id: uuid.UUID,
    file_bytes: bytes,
    format_result: FormatDetectionResult,
) -> ParseAndStoreResult:
    """Select parser based on format, parse transactions, and add to session.

    Deduplicates against existing transactions for this user.
    NOTE: Does NOT commit the session — caller controls the transaction boundary.
    """
    # The async path is only used by FastAPI request handlers where schema
    # detection isn't yet wired in (upload flow runs detection in Celery). Pass
    # session=None so the flow falls through to GenericParser on unknown format.
    transactions, flagged_records, result = _parse_and_build_records(
        user_id, upload_id, file_bytes, format_result, session=None,
    )

    # Query existing dedup hashes for this user
    stmt = select(Transaction.dedup_hash).where(Transaction.user_id == user_id)
    rows = await session.exec(stmt)
    existing_hashes = set(rows.all())

    new_txns, duplicates_skipped = _filter_duplicates(transactions, existing_hashes)
    result.duplicates_skipped = duplicates_skipped
    result.persisted_count = len(new_txns) + len(flagged_records)

    session.add_all(new_txns)
    session.add_all(flagged_records)

    logger.info(
        "Parse and store complete",
        extra={
            "upload_id": str(upload_id),
            "total_rows": result.total_rows,
            "parsed": result.parsed_count,
            "flagged": result.flagged_count,
            "persisted": result.persisted_count,
            "duplicates_skipped": duplicates_skipped,
            "validation_rejected": result.validation_rejected_count,
            "validation_warnings": result.validation_warnings_count,
            "schema_detection_source": result.schema_detection_source,
        },
    )

    return result


def sync_parse_and_store_transactions(
    session: Session,
    user_id: uuid.UUID,
    upload_id: uuid.UUID,
    file_bytes: bytes,
    format_result: FormatDetectionResult,
) -> ParseAndStoreResult:
    """Synchronous version for Celery worker context.

    Deduplicates against existing transactions for this user.
    NOTE: Does NOT commit the session — caller controls the transaction boundary.
    """
    transactions, flagged_records, result = _parse_and_build_records(
        user_id, upload_id, file_bytes, format_result, session=session,
    )

    # Query existing dedup hashes for this user
    stmt = select(Transaction.dedup_hash).where(Transaction.user_id == user_id)
    existing_hashes = set(session.exec(stmt).all())

    new_txns, duplicates_skipped = _filter_duplicates(transactions, existing_hashes)
    result.duplicates_skipped = duplicates_skipped
    result.persisted_count = len(new_txns) + len(flagged_records)

    session.add_all(new_txns)
    session.add_all(flagged_records)

    # Story 11.10: populate user_iban_registry with self-counterparty IBANs
    # from PE statements. Best-effort — registry failures must NOT fail the
    # upload path.
    try:
        _register_self_counterparty_ibans(
            session, user_id, upload_id, new_txns,
        )
    except Exception as exc:
        logger.warning(
            "user_iban_registry.register_failed",
            extra={"upload_id": str(upload_id), "error": str(exc)},
        )

    logger.info(
        "Sync parse and store complete",
        extra={
            "upload_id": str(upload_id),
            "total_rows": result.total_rows,
            "parsed": result.parsed_count,
            "flagged": result.flagged_count,
            "persisted": result.persisted_count,
            "duplicates_skipped": duplicates_skipped,
            "validation_rejected": result.validation_rejected_count,
            "validation_warnings": result.validation_warnings_count,
            "schema_detection_source": result.schema_detection_source,
        },
    )

    return result
