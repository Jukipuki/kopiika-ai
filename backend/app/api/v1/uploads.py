import logging
import uuid
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Request, UploadFile
from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel
from sqlmodel.ext.asyncio.session import AsyncSession as SQLModelAsyncSession

from app.api.deps import get_current_user_id, get_db, get_rate_limiter
from app.services import upload_service
from app.services.rate_limiter import RateLimiter
from app.tasks.processing_tasks import process_upload

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/uploads", tags=["uploads"])


class UploadResponse(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    job_id: str
    status_url: str
    detected_format: Optional[str] = None
    encoding: Optional[str] = None
    column_count: Optional[int] = None


@router.post("", status_code=202, response_model=UploadResponse)
async def create_upload(
    file: UploadFile,
    request: Request,
    user_id: Annotated[uuid.UUID, Depends(get_current_user_id)],
    session: Annotated[SQLModelAsyncSession, Depends(get_db)],
    rate_limiter: Annotated[RateLimiter, Depends(get_rate_limiter)],
) -> UploadResponse:
    # Validate file type before reading content into memory
    upload_service.validate_file_type(file)

    # Check rate limit (20 uploads/user/hour)
    await rate_limiter.check_upload_rate_limit(str(user_id))

    # Read file content and validate size
    file_content = await file.read()
    file_size = len(file_content)
    upload_service.validate_file_size(file_size)

    # Enhanced validation: magic bytes, sanitization, CSV structure, format detection
    format_result = upload_service.validate_and_detect_format(
        file_content, file.content_type or "application/octet-stream"
    )

    # Generate S3 key and upload
    job_id = uuid.uuid4()
    s3_key = upload_service.generate_s3_key(user_id, job_id, file.filename or "unknown.bin")

    await upload_service.upload_to_s3(s3_key, file_content, file.content_type or "application/octet-stream")

    # Create DB records with format detection results
    upload_record, job = await upload_service.create_upload_record(
        session=session,
        user_id=user_id,
        file_name=file.filename or "unknown",
        s3_key=s3_key,
        file_size=file_size,
        mime_type=file.content_type or "application/octet-stream",
        job_id=job_id,
        detected_format=format_result.bank_format if format_result else None,
        detected_encoding=format_result.encoding if format_result else None,
        detected_delimiter=format_result.delimiter if format_result else None,
    )

    # Dispatch Celery task AFTER DB commit so worker can find the ProcessingJob
    process_upload.delay(str(job.id))

    logger.info(
        "Upload created",
        extra={
            "action": "upload_created",
            "user_id": str(user_id),
            "upload_id": str(upload_record.id),
            "job_id": str(job.id),
            "file_size": file_size,
            "detected_format": format_result.bank_format if format_result else None,
        },
    )

    return UploadResponse(
        job_id=str(job.id),
        status_url=f"/api/v1/jobs/{job.id}",
        detected_format=format_result.bank_format if format_result else None,
        encoding=format_result.encoding if format_result else None,
        column_count=format_result.column_count if format_result else None,
    )
