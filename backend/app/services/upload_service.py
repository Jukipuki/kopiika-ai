import csv
import io
import logging
import re
import uuid
from datetime import UTC, datetime
from typing import Optional

import boto3
from botocore.exceptions import ClientError
from fastapi import UploadFile
from sqlmodel import col, func, select
from sqlmodel.ext.asyncio.session import AsyncSession as SQLModelAsyncSession

from app.core.config import settings
from app.core.exceptions import ValidationError
from app.models.processing_job import ProcessingJob
from app.models.transaction import Transaction
from app.models.upload import Upload
from app.services.format_detector import FormatDetectionResult, detect_format

logger = logging.getLogger(__name__)

ALLOWED_MIME_TYPES = {"text/csv", "application/pdf"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

# Magic bytes for file type verification
CSV_TEXT_CHARS = set(range(0x20, 0x7F)) | {0x09, 0x0A, 0x0D}  # printable + tab/LF/CR
PDF_MAGIC = b"%PDF"

# Maximum bytes to read for validation checks
VALIDATION_SAMPLE_SIZE = 8192


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _get_s3_client():
    return boto3.client("s3", region_name=settings.S3_REGION)


def validate_file_type(file: UploadFile) -> None:
    if file.content_type not in ALLOWED_MIME_TYPES:
        raise ValidationError(
            code="INVALID_FILE_TYPE",
            message="Only CSV and PDF files are supported.",
            status_code=400,
            details={"suggestions": ["Try exporting your bank statement as CSV."]},
        )


def validate_file_size(file_size: int) -> None:
    if file_size > MAX_FILE_SIZE:
        raise ValidationError(
            code="FILE_TOO_LARGE",
            message="This file is too large. Please upload files under 10MB.",
            status_code=400,
            details={"suggestions": []},
        )


def validate_magic_bytes(file_content: bytes, content_type: str) -> None:
    """Verify actual file content matches declared MIME type (not just header)."""
    if len(file_content) == 0:
        raise ValidationError(
            code="EMPTY_FILE",
            message="This file appears to be empty.",
            status_code=400,
            details={
                "suggestions": [
                    "Check that your bank statement has transaction data",
                    "Try downloading the statement again",
                ]
            },
        )

    if content_type == "application/pdf":
        if not file_content[:4].startswith(PDF_MAGIC):
            raise ValidationError(
                code="CORRUPTED_FILE",
                message="This file appears to be damaged.",
                status_code=400,
                details={
                    "suggestions": [
                        "Try downloading the statement again from your bank",
                    ]
                },
            )
    elif content_type == "text/csv":
        # Check that the file is actually text, not binary disguised as CSV
        sample = file_content[:VALIDATION_SAMPLE_SIZE]
        # Allow high-byte characters for non-ASCII encodings (Windows-1251, UTF-8, etc.)
        # But reject null bytes and control characters (except tab, LF, CR)
        if b"\x00" in sample:
            raise ValidationError(
                code="CORRUPTED_FILE",
                message="This file appears to be damaged.",
                status_code=400,
                details={
                    "suggestions": [
                        "Try downloading the statement again from your bank",
                    ]
                },
            )
        # Check for excessive non-text bytes (binary content)
        non_text_count = sum(
            1 for b in sample
            if b < 0x09 or (0x0E <= b < 0x20 and b != 0x1B)
        )
        if non_text_count > len(sample) * 0.1:
            raise ValidationError(
                code="CORRUPTED_FILE",
                message="This file appears to be damaged.",
                status_code=400,
                details={
                    "suggestions": [
                        "Try downloading the statement again from your bank",
                    ]
                },
            )


def validate_csv_structure(file_content: bytes, encoding: str | None = None) -> None:
    """Validate CSV structure: detect delimiter, verify header row exists."""
    if encoding is None:
        from app.services.format_detector import detect_encoding
        encoding, _ = detect_encoding(file_content)
    try:
        text = file_content.decode(encoding)
    except (UnicodeDecodeError, LookupError):
        raise ValidationError(
            code="ENCODING_ERROR",
            message="We had trouble reading this file.",
            status_code=400,
            details={
                "suggestions": [
                    "Try re-exporting the file from your bank",
                    "Make sure the file isn't corrupted",
                ]
            },
        )

    lines = text.strip().splitlines()
    if len(lines) < 1:
        raise ValidationError(
            code="EMPTY_FILE",
            message="This file appears to be empty.",
            status_code=400,
            details={
                "suggestions": [
                    "Check that your bank statement has transaction data",
                    "Try downloading the statement again",
                ]
            },
        )

    # Try to parse header row
    try:
        sample = "\n".join(lines[:5])
        dialect = csv.Sniffer().sniff(sample, delimiters=";,\t")
        reader = csv.reader(io.StringIO(lines[0]), delimiter=dialect.delimiter)
        header = next(reader)
        if len(header) < 2:
            raise ValidationError(
                code="INVALID_FILE_STRUCTURE",
                message="This file doesn't look like a bank statement.",
                status_code=400,
                details={
                    "suggestions": [
                        "Check that the file is a .csv with transaction data",
                        "Try re-exporting from your bank app",
                    ]
                },
            )
    except csv.Error:
        raise ValidationError(
            code="INVALID_FILE_STRUCTURE",
            message="This file doesn't look like a bank statement.",
            status_code=400,
            details={
                "suggestions": [
                    "Check that the file is a .csv with transaction data",
                    "Try re-exporting from your bank app",
                ]
            },
        )


def sanitize_content(file_content: bytes) -> bytes:
    """Sanitize file content: strip null bytes, reject embedded scripts."""
    # Strip null bytes
    sanitized = file_content.replace(b"\x00", b"")

    # Check for embedded script tags (HTML/JS injection in CSV)
    # Check in both raw bytes and decoded text
    lower_content = sanitized.lower()
    if b"<script" in lower_content or b"javascript:" in lower_content:
        raise ValidationError(
            code="CORRUPTED_FILE",
            message="This file appears to be damaged.",
            status_code=400,
            details={
                "suggestions": [
                    "Try downloading the statement again from your bank",
                ]
            },
        )

    return sanitized


def validate_and_detect_format(
    file_content: bytes, content_type: str
) -> Optional[FormatDetectionResult]:
    """Run full validation pipeline and detect format for CSV files.

    Returns FormatDetectionResult for CSV files, None for PDFs.
    """
    # 1. Magic byte validation
    validate_magic_bytes(file_content, content_type)

    # 2. Sanitize content
    sanitized = sanitize_content(file_content)

    # 3. CSV-specific validation and format detection
    if content_type == "text/csv":
        from app.services.format_detector import detect_encoding

        encoding, confidence = detect_encoding(sanitized)
        validate_csv_structure(sanitized, encoding=encoding)
        # NOTE: "unknown" bank format is accepted (not rejected) per AC#3.
        # UNSUPPORTED_BANK_FORMAT error code is reserved for when the product
        # decides to reject unknown formats in the future.
        return detect_format(sanitized, encoding=encoding, encoding_confidence=confidence)

    return None


def generate_s3_key(user_id: uuid.UUID, job_id: uuid.UUID, file_name: str) -> str:
    ext = file_name.rsplit(".", 1)[-1].lower() if "." in file_name else "bin"
    return f"{user_id}/{job_id}_original.{ext}"


async def upload_to_s3(s3_key: str, file_content: bytes, content_type: str) -> None:
    import asyncio

    client = _get_s3_client()
    try:
        await asyncio.to_thread(
            client.put_object,
            Bucket=settings.S3_UPLOADS_BUCKET,
            Key=s3_key,
            Body=file_content,
            ContentType=content_type,
        )
    except ClientError as e:
        logger.error("S3 upload failed", extra={"s3_key": s3_key, "error": str(e)})
        raise ValidationError(
            code="UPLOAD_FAILED",
            message="Something went wrong with the upload. Please try again.",
            status_code=500,
        ) from e


async def create_upload_record(
    session: SQLModelAsyncSession,
    user_id: uuid.UUID,
    file_name: str,
    s3_key: str,
    file_size: int,
    mime_type: str,
    job_id: uuid.UUID,
    detected_format: Optional[str] = None,
    detected_encoding: Optional[str] = None,
    detected_delimiter: Optional[str] = None,
) -> tuple[Upload, ProcessingJob]:
    upload = Upload(
        user_id=user_id,
        file_name=file_name,
        s3_key=s3_key,
        file_size=file_size,
        mime_type=mime_type,
        detected_format=detected_format,
        detected_encoding=detected_encoding,
        detected_delimiter=detected_delimiter,
    )
    session.add(upload)
    await session.flush()

    job = ProcessingJob(
        id=job_id,
        user_id=user_id,
        upload_id=upload.id,
        status="validated",
    )
    session.add(job)
    await session.commit()
    await session.refresh(upload)
    await session.refresh(job)

    return upload, job


async def get_uploads_for_user(
    session: SQLModelAsyncSession,
    user_id: uuid.UUID,
    cursor: str | None = None,
    page_size: int = 20,
) -> dict:
    """Get paginated upload history for a user with transaction counts and job status.

    Returns dict with items, total, next_cursor, has_more.
    """
    page_size = min(max(page_size, 1), 50)

    # Total count
    count_stmt = select(func.count()).select_from(Upload).where(Upload.user_id == user_id)
    total = (await session.exec(count_stmt)).one()

    # Main query with joined data
    # We need: upload fields + transaction count + job status + duplicates_skipped
    stmt = (
        select(Upload)
        .where(Upload.user_id == user_id)
        .order_by(col(Upload.created_at).desc())
    )

    if cursor:
        try:
            cursor_upload = await session.get(Upload, uuid.UUID(cursor))
        except ValueError:
            cursor_upload = None
        if cursor_upload:
            stmt = stmt.where(
                (col(Upload.created_at) < cursor_upload.created_at)
                | (
                    (col(Upload.created_at) == cursor_upload.created_at)
                    & (col(Upload.id) < cursor_upload.id)
                )
            )

    stmt = stmt.limit(page_size + 1)
    uploads = list((await session.exec(stmt)).all())

    has_more = len(uploads) > page_size
    uploads = uploads[:page_size]
    next_cursor = str(uploads[-1].id) if has_more and uploads else None

    if not uploads:
        return {"items": [], "total": total, "next_cursor": None, "has_more": False}

    upload_ids = [upload.id for upload in uploads]

    # Batch-load transaction counts — one query instead of N
    txn_counts_stmt = (
        select(Transaction.upload_id, func.count(Transaction.id).label("cnt"))
        .where(col(Transaction.upload_id).in_(upload_ids))
        .group_by(col(Transaction.upload_id))
    )
    txn_count_rows = (await session.exec(txn_counts_stmt)).all()
    txn_counts: dict[uuid.UUID, int] = {row[0]: row[1] for row in txn_count_rows}

    # Batch-load jobs — one query instead of N
    jobs_stmt = select(ProcessingJob).where(col(ProcessingJob.upload_id).in_(upload_ids))
    jobs = (await session.exec(jobs_stmt)).all()
    jobs_by_upload: dict[uuid.UUID, ProcessingJob] = {job.upload_id: job for job in jobs}

    items = []
    for upload in uploads:
        job = jobs_by_upload.get(upload.id)
        txn_count = txn_counts.get(upload.id, 0)
        duplicates_skipped = 0
        job_status = "unknown"
        if job:
            job_status = job.status
            if job.result_data and "duplicates_skipped" in job.result_data:
                duplicates_skipped = job.result_data["duplicates_skipped"]

        items.append({
            "id": str(upload.id),
            "file_name": upload.file_name,
            "detected_format": upload.detected_format,
            "created_at": upload.created_at.isoformat() + "Z",
            "transaction_count": txn_count,
            "duplicates_skipped": duplicates_skipped,
            "status": job_status,
        })

    return {
        "items": items,
        "total": total,
        "next_cursor": next_cursor,
        "has_more": has_more,
    }
