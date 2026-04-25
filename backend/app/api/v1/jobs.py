import asyncio
import json
import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel
from sqlmodel.ext.asyncio.session import AsyncSession as SQLModelAsyncSession

from app.api.deps import get_current_user_id, get_db
from app.api.v1._sse import SSE_RESPONSE_HEADERS
from app.core.redis import get_job_state, subscribe_job_progress
from app.core.security import verify_token
from app.models.processing_job import ProcessingJob

router = APIRouter(prefix="/jobs", tags=["jobs"])

SSE_HEARTBEAT_INTERVAL = 15  # seconds


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
    is_retryable: bool = True
    retry_count: int = 0
    created_at: str
    updated_at: str


class RetryResponse(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    job_id: str
    status: str


@router.post("/{job_id}/retry", response_model=RetryResponse, status_code=status.HTTP_202_ACCEPTED)
async def retry_job(
    job_id: uuid.UUID,
    user_id: Annotated[uuid.UUID, Depends(get_current_user_id)],
    session: Annotated[SQLModelAsyncSession, Depends(get_db)],
) -> RetryResponse:
    """Retry a failed processing job by resuming from its last checkpoint."""
    job = await session.get(ProcessingJob, job_id)

    if job is None or job.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "JOB_NOT_FOUND", "message": "Job not found"}},
        )

    if job.status != "failed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": {"code": "JOB_NOT_FAILED", "message": "Only failed jobs can be retried"}},
        )

    if not job.is_retryable:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": {"code": "JOB_NOT_RETRYABLE", "message": "This job cannot be retried"}},
        )

    # Reset job to pending and queue resume task
    job.status = "pending"
    job.error_code = None
    job.error_message = None
    job.retry_count += 1
    job.updated_at = datetime.now(UTC).replace(tzinfo=None)
    session.add(job)
    await session.commit()

    from app.tasks.processing_tasks import resume_upload
    resume_upload.delay(str(job_id))

    return RetryResponse(job_id=str(job_id), status="pending")


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
        is_retryable=job.is_retryable,
        retry_count=job.retry_count,
        created_at=job.created_at.isoformat(),
        updated_at=job.updated_at.isoformat(),
    )


async def _get_user_id_from_token(
    token: str,
    session: SQLModelAsyncSession,
) -> uuid.UUID:
    """Extract user_id from a JWT token (for SSE query-param auth).

    NOTE: Duplicates cognito_sub→user_id lookup from deps.get_current_user_id.
    Needed because EventSource doesn't support Authorization headers.
    If deps.py auth logic changes, update this function too.
    Story 10.5 extracted a shared equivalent at ``app.api.v1._sse``; jobs
    still uses this local helper so the existing ``patch("app.api.v1.jobs.
    verify_token", ...)`` test pattern continues to work.
    """
    from sqlmodel import select

    from app.models.user import User

    payload = await verify_token(token)
    cognito_sub = payload.get("sub")
    if not cognito_sub:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "INVALID_TOKEN", "message": "Token missing sub claim"}},
        )
    result = await session.exec(select(User.id).where(User.cognito_sub == cognito_sub))
    user_id = result.first()
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "USER_NOT_FOUND", "message": "User not found"}},
        )
    return user_id


@router.get("/{job_id}/stream")
async def stream_job_progress(
    job_id: uuid.UUID,
    request: Request,
    token: str,
    session: Annotated[SQLModelAsyncSession, Depends(get_db)],
) -> StreamingResponse:
    """SSE endpoint for real-time job progress updates.

    Auth via query param: ?token=<JWT> (EventSource doesn't support headers).
    """
    user_id = await _get_user_id_from_token(token, session)

    # Verify job exists and belongs to user (tenant isolation)
    job = await session.get(ProcessingJob, job_id)
    if job is None or job.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "JOB_NOT_FOUND", "message": "Job not found"}},
        )

    job_id_str = str(job_id)

    async def event_generator() -> AsyncGenerator[str, None]:
        # Await subscribe_job_progress so the Redis subscription is ACTIVE
        # before we read stored state — prevents the race condition where a
        # fast-completing task publishes job-complete between state-check and
        # subscribe, causing the stream to hang indefinitely.
        subscriber = await subscribe_job_progress(job_id_str)
        try:
            # Send current state immediately (supports reconnection — AC #5)
            current_state = await get_job_state(job_id_str)
            if current_state:
                event_type = current_state.get("event", "pipeline-progress")
                yield f"event: {event_type}\ndata: {json.dumps(current_state)}\n\n"
                # If job already terminal, close stream
                if event_type in ("job-complete", "job-failed"):
                    return

            # If the DB already shows a terminal status and no Redis state,
            # send a synthetic terminal event
            if job.status == "retrying":
                retrying_payload = {
                    "event": "job-retrying",
                    "jobId": job_id_str,
                    "retryCount": job.retry_count,
                    "maxRetries": job.max_retries,
                }
                yield f"event: job-retrying\ndata: {json.dumps(retrying_payload)}\n\n"
            if job.status == "completed":
                rd = job.result_data or {}
                ds = rd.get("date_range_start")
                de = rd.get("date_range_end")
                synthetic_payload = {
                    # Frontend handler is gated on data.event === "job-complete";
                    # the SSE event header alone is not enough.
                    "event": "job-complete",
                    "jobId": job_id_str,
                    "status": "completed",
                    "totalInsights": rd.get("insight_count", 0),
                    "bankName": rd.get("bank_name"),
                    "transactionCount": rd.get("new_transactions"),
                    "dateRange": {"start": ds, "end": de} if ds and de else None,
                    "duplicatesSkipped": rd.get("duplicates_skipped"),
                    "newTransactions": rd.get("new_transactions"),
                }
                yield f"event: job-complete\ndata: {json.dumps(synthetic_payload)}\n\n"
                return
            if job.status == "failed":
                failed_payload = {
                    "event": "job-failed",
                    "jobId": job_id_str,
                    "status": "failed",
                    "error": {
                        "code": job.error_code or "UNKNOWN_ERROR",
                        "message": job.error_message or "Processing failed",
                    },
                }
                yield f"event: job-failed\ndata: {json.dumps(failed_payload)}\n\n"
                return

            # Stream live progress events
            while True:
                if await request.is_disconnected():
                    break
                try:
                    data = await asyncio.wait_for(
                        subscriber.__anext__(), timeout=SSE_HEARTBEAT_INTERVAL
                    )
                    event_type = data.get("event", "pipeline-progress")
                    yield f"event: {event_type}\ndata: {json.dumps(data)}\n\n"
                    if event_type in ("job-complete", "job-failed"):
                        break
                    # job-retrying and job-resumed are non-terminal — keep streaming
                except asyncio.TimeoutError:
                    # Fallback: re-check Redis state in case an event was
                    # published in the window before subscription was active.
                    latest = await get_job_state(job_id_str)
                    if latest and latest.get("event") in ("job-complete", "job-failed"):
                        event_type = latest["event"]
                        yield f"event: {event_type}\ndata: {json.dumps(latest)}\n\n"
                        break
                    yield ": heartbeat\n\n"
                except StopAsyncIteration:
                    break
        finally:
            await subscriber.aclose()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers=SSE_RESPONSE_HEADERS,
    )
