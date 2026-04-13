"""Tests for retry API endpoint (Story 6.2, AC #2)."""

import uuid
from unittest.mock import patch

import pytest

from app.core.security import get_current_user_payload
from app.main import app
from app.models.processing_job import ProcessingJob
from app.models.upload import Upload
from app.models.user import User


async def _setup_user_and_auth(client, email="retry@test.com", cognito_sub="test-cognito-sub-123"):
    """Create test user and set auth override."""
    await client.post("/api/v1/auth/signup", json={"email": email, "password": "StrongPass1!"})
    await client.post("/api/v1/auth/verify", json={"email": email, "code": "123456"})
    await client.post("/api/v1/auth/login", json={"email": email, "password": "StrongPass1!"})

    async def mock_payload():
        return {"sub": cognito_sub}

    app.dependency_overrides[get_current_user_payload] = mock_payload
    return cognito_sub


async def _create_failed_job(session, user_id, is_retryable=True):
    """Create a failed processing job."""
    upload = Upload(
        id=uuid.uuid4(),
        user_id=user_id,
        file_name="test.csv",
        s3_key=f"{user_id}/test.csv",
        file_size=1024,
        mime_type="text/csv",
    )
    session.add(upload)
    await session.flush()

    job = ProcessingJob(
        id=uuid.uuid4(),
        user_id=user_id,
        upload_id=upload.id,
        status="failed",
        error_code="LLM_ERROR",
        error_message="LLM timeout",
        is_retryable=is_retryable,
        failed_step="categorization",
    )
    session.add(job)
    await session.commit()
    await session.refresh(job)
    return job


@pytest.mark.asyncio
async def test_retry_failed_job_returns_202(client, async_session, mock_rate_limiter):
    """POST /api/v1/jobs/{id}/retry returns 202 for a retryable failed job."""
    cognito_sub = await _setup_user_and_auth(client)

    from sqlmodel import select
    user = (await async_session.exec(select(User).where(User.cognito_sub == cognito_sub))).first()
    job = await _create_failed_job(async_session, user.id)

    try:
        with patch("app.tasks.processing_tasks.resume_upload") as mock_task:
            response = await client.post(f"/api/v1/jobs/{job.id}/retry")

        assert response.status_code == 202
        data = response.json()
        assert data["jobId"] == str(job.id)
        assert data["status"] == "pending"
        # Verify the Celery resume task was actually queued
        mock_task.delay.assert_called_once_with(str(job.id))
    finally:
        app.dependency_overrides.pop(get_current_user_payload, None)


@pytest.mark.asyncio
async def test_retry_non_retryable_job_returns_422(client, async_session, mock_rate_limiter):
    """POST /api/v1/jobs/{id}/retry returns 422 for non-retryable job."""
    cognito_sub = await _setup_user_and_auth(client)

    from sqlmodel import select
    user = (await async_session.exec(select(User).where(User.cognito_sub == cognito_sub))).first()
    job = await _create_failed_job(async_session, user.id, is_retryable=False)

    try:
        response = await client.post(f"/api/v1/jobs/{job.id}/retry")

        assert response.status_code == 422
        data = response.json()
        assert data["detail"]["error"]["code"] == "JOB_NOT_RETRYABLE"
    finally:
        app.dependency_overrides.pop(get_current_user_payload, None)


async def _create_completed_job(session, user_id):
    """Create a completed processing job."""
    upload = Upload(
        id=uuid.uuid4(), user_id=user_id, file_name="test.csv",
        s3_key=f"{user_id}/test.csv", file_size=1024, mime_type="text/csv",
    )
    session.add(upload)
    await session.flush()

    job = ProcessingJob(
        id=uuid.uuid4(), user_id=user_id, upload_id=upload.id,
        status="completed", step="done", progress=100,
    )
    session.add(job)
    await session.commit()
    await session.refresh(job)
    return job


@pytest.mark.asyncio
async def test_retry_completed_job_returns_409(client, async_session, mock_rate_limiter):
    """POST /api/v1/jobs/{id}/retry returns 409 for non-failed job."""
    cognito_sub = await _setup_user_and_auth(client)

    from sqlmodel import select
    user = (await async_session.exec(select(User).where(User.cognito_sub == cognito_sub))).first()
    job = await _create_completed_job(async_session, user.id)

    try:
        response = await client.post(f"/api/v1/jobs/{job.id}/retry")

        assert response.status_code == 409
        data = response.json()
        assert data["detail"]["error"]["code"] == "JOB_NOT_FAILED"
    finally:
        app.dependency_overrides.pop(get_current_user_payload, None)


@pytest.mark.asyncio
async def test_retry_other_users_job_returns_404(client, async_session, mock_rate_limiter):
    """Tenant isolation: cannot retry another user's job."""
    await _setup_user_and_auth(client)

    other_user_id = uuid.uuid4()
    other_user = User(id=other_user_id, email="other@test.com", cognito_sub="other-sub", locale="en")
    async_session.add(other_user)
    await async_session.flush()

    job = await _create_failed_job(async_session, other_user_id)

    try:
        response = await client.post(f"/api/v1/jobs/{job.id}/retry")
        assert response.status_code == 404
    finally:
        app.dependency_overrides.pop(get_current_user_payload, None)


@pytest.mark.asyncio
async def test_retry_nonexistent_job_returns_404(client, mock_rate_limiter):
    """Non-existent job returns 404."""
    await _setup_user_and_auth(client)

    try:
        response = await client.post(f"/api/v1/jobs/{uuid.uuid4()}/retry")
        assert response.status_code == 404
    finally:
        app.dependency_overrides.pop(get_current_user_payload, None)
