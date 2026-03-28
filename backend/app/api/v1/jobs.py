import uuid
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel
from sqlmodel.ext.asyncio.session import AsyncSession as SQLModelAsyncSession

from app.api.deps import get_current_user_id, get_db
from app.models.processing_job import ProcessingJob

router = APIRouter(prefix="/jobs", tags=["jobs"])


class JobError(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    code: str
    message: str


class JobResult(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    total_rows: int
    parsed_count: int
    flagged_count: int
    persisted_count: int


class JobStatusResponse(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    job_id: str
    status: str
    step: Optional[str] = None
    progress: int = 0
    error: Optional[JobError] = None
    result: Optional[JobResult] = None
    created_at: str
    updated_at: str


@router.get("/{job_id}", response_model=JobStatusResponse)
async def get_job_status(
    job_id: uuid.UUID,
    user_id: Annotated[uuid.UUID, Depends(get_current_user_id)],
    session: Annotated[SQLModelAsyncSession, Depends(get_db)],
) -> JobStatusResponse:
    job = await session.get(ProcessingJob, job_id)

    if job is None or job.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "JOB_NOT_FOUND", "message": "Job not found"}},
        )

    error = None
    if job.status == "failed" and job.error_code:
        error = JobError(code=job.error_code, message=job.error_message or "")

    result = None
    if job.status == "completed" and job.result_data:
        result = JobResult(
            total_rows=job.result_data.get("total_rows", 0),
            parsed_count=job.result_data.get("parsed_count", 0),
            flagged_count=job.result_data.get("flagged_count", 0),
            persisted_count=job.result_data.get("persisted_count", 0),
        )

    return JobStatusResponse(
        job_id=str(job.id),
        status=job.status,
        step=job.step,
        progress=job.progress,
        error=error,
        result=result,
        created_at=job.created_at.isoformat(),
        updated_at=job.updated_at.isoformat(),
    )
