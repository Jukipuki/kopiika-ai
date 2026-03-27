import logging
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Request, UploadFile
from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel
from sqlmodel.ext.asyncio.session import AsyncSession as SQLModelAsyncSession

from app.api.deps import get_current_user_id, get_db, get_rate_limiter
from app.services import upload_service
from app.services.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/uploads", tags=["uploads"])


class UploadResponse(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    job_id: str
    status_url: str


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

    # Generate S3 key and upload
    job_id = uuid.uuid4()
    s3_key = upload_service.generate_s3_key(user_id, job_id, file.filename or "unknown.bin")

    await upload_service.upload_to_s3(s3_key, file_content, file.content_type or "application/octet-stream")

    # Create DB records
    upload_record, job = await upload_service.create_upload_record(
        session=session,
        user_id=user_id,
        file_name=file.filename or "unknown",
        s3_key=s3_key,
        file_size=file_size,
        mime_type=file.content_type or "application/octet-stream",
        job_id=job_id,
    )

    logger.info(
        "Upload created",
        extra={
            "action": "upload_created",
            "user_id": str(user_id),
            "upload_id": str(upload_record.id),
            "job_id": str(job.id),
            "file_size": file_size,
        },
    )

    return UploadResponse(
        job_id=str(job.id),
        status_url=f"/api/v1/jobs/{job.id}",
    )
