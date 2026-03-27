import logging
import uuid
from datetime import UTC, datetime

import boto3
from botocore.exceptions import ClientError
from fastapi import UploadFile
from sqlmodel.ext.asyncio.session import AsyncSession as SQLModelAsyncSession

from app.core.config import settings
from app.core.exceptions import ValidationError
from app.models.processing_job import ProcessingJob
from app.models.upload import Upload

logger = logging.getLogger(__name__)

ALLOWED_MIME_TYPES = {"text/csv", "application/pdf"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _get_s3_client():
    return boto3.client("s3", region_name=settings.S3_REGION)


def validate_file_type(file: UploadFile) -> None:
    if file.content_type not in ALLOWED_MIME_TYPES:
        raise ValidationError(
            code="INVALID_FILE_TYPE",
            message="Only CSV and PDF files are supported. Try exporting your bank statement as CSV.",
            status_code=400,
        )


def validate_file_size(file_size: int) -> None:
    if file_size > MAX_FILE_SIZE:
        raise ValidationError(
            code="FILE_TOO_LARGE",
            message="This file is too large. Please upload files under 10MB.",
            status_code=400,
        )


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
) -> tuple[Upload, ProcessingJob]:
    upload = Upload(
        user_id=user_id,
        file_name=file_name,
        s3_key=s3_key,
        file_size=file_size,
        mime_type=mime_type,
    )
    session.add(upload)
    await session.flush()

    job = ProcessingJob(
        id=job_id,
        user_id=user_id,
        upload_id=upload.id,
        status="pending",
    )
    session.add(job)
    await session.commit()
    await session.refresh(upload)
    await session.refresh(job)

    return upload, job
