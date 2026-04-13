"""Tests for job status endpoint (Story 2.5)."""
import uuid

import pytest

from app.core.security import get_current_user_payload
from app.main import app
from app.models.processing_job import ProcessingJob
from app.models.upload import Upload
from app.models.user import User


async def _setup_user_and_auth(client, email="jobs@test.com", cognito_sub="test-cognito-sub-123"):
    """Create test user via signup flow and set auth override.

    Note: mock cognito service always creates user with cognito_sub="test-cognito-sub-123".
    """
    await client.post(
        "/api/v1/auth/signup",
        json={"email": email, "password": "StrongPass1!"},
    )
    await client.post(
        "/api/v1/auth/verify",
        json={"email": email, "code": "123456"},
    )
    await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "StrongPass1!"},
    )

    async def mock_payload():
        return {"sub": cognito_sub}

    app.dependency_overrides[get_current_user_payload] = mock_payload
    return cognito_sub


async def _create_upload_and_job(session, user_id, status="validated", result_data=None, error_code=None, error_message=None):
    """Create upload and processing job records for testing."""
    upload = Upload(
        id=uuid.uuid4(),
        user_id=user_id,
        file_name="test.csv",
        s3_key=f"{user_id}/test_original.csv",
        file_size=1024,
        mime_type="text/csv",
    )
    session.add(upload)
    await session.flush()

    job = ProcessingJob(
        id=uuid.uuid4(),
        user_id=user_id,
        upload_id=upload.id,
        status=status,
        step="done" if status == "completed" else None,
        progress=100 if status == "completed" else 0,
        result_data=result_data,
        error_code=error_code,
        error_message=error_message,
    )
    session.add(job)
    await session.commit()
    await session.refresh(job)
    return job


def test_processing_job_exposes_operator_fields():
    """ProcessingJob model has all fields an operator needs to query."""
    job = ProcessingJob(
        user_id=uuid.uuid4(),
        upload_id=uuid.uuid4(),
        status="pending",
    )
    required_fields = [
        "created_at", "started_at", "updated_at", "status",
        "step", "progress", "error_code", "error_message",
        "failed_step", "user_id", "result_data",
    ]
    for field in required_fields:
        assert hasattr(job, field), f"ProcessingJob missing field: {field}"


@pytest.mark.asyncio
async def test_get_job_status_success(client, async_session, mock_rate_limiter):
    """GET /api/v1/jobs/{id} returns correct status for completed job."""
    cognito_sub = await _setup_user_and_auth(client)

    from sqlmodel import select
    user = (await async_session.exec(select(User).where(User.cognito_sub == cognito_sub))).first()

    job = await _create_upload_and_job(
        async_session,
        user.id,
        status="completed",
        result_data={"total_rows": 10, "parsed_count": 8, "flagged_count": 2, "persisted_count": 10},
    )

    try:
        response = await client.get(f"/api/v1/jobs/{job.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["jobId"] == str(job.id)
        assert data["status"] == "completed"
        assert data["step"] == "done"
        assert data["progress"] == 100
        assert data["result"]["totalRows"] == 10
        assert data["result"]["parsedCount"] == 8
        assert data["result"]["flaggedCount"] == 2
        assert data["result"]["persistedCount"] == 10
        assert data["error"] is None
    finally:
        app.dependency_overrides.pop(get_current_user_payload, None)


@pytest.mark.asyncio
async def test_get_job_status_tenant_isolation(client, async_session, mock_rate_limiter, mock_cognito_service):
    """User A cannot see user B's job (returns 404)."""
    # Create user A (logged in via mock cognito_sub="test-cognito-sub-123")
    await _setup_user_and_auth(client, email="usera@test.com")

    # Create user B directly in DB (different user)
    user_b_id = uuid.uuid4()
    user_b = User(id=user_b_id, email="userb@test.com", cognito_sub="sub-user-b", locale="en")
    async_session.add(user_b)
    await async_session.commit()

    # Create a job owned by user B
    job = await _create_upload_and_job(async_session, user_b_id, status="completed")

    try:
        # User A tries to access user B's job
        response = await client.get(f"/api/v1/jobs/{job.id}")

        assert response.status_code == 404
        data = response.json()
        assert data["detail"]["error"]["code"] == "JOB_NOT_FOUND"
    finally:
        app.dependency_overrides.pop(get_current_user_payload, None)


@pytest.mark.asyncio
async def test_get_job_status_not_found(client, mock_rate_limiter):
    """Non-existent job returns 404."""
    await _setup_user_and_auth(client)

    try:
        fake_id = uuid.uuid4()
        response = await client.get(f"/api/v1/jobs/{fake_id}")

        assert response.status_code == 404
    finally:
        app.dependency_overrides.pop(get_current_user_payload, None)


@pytest.mark.asyncio
async def test_get_job_status_failed_includes_error(client, async_session, mock_rate_limiter):
    """Failed job includes error details in response."""
    cognito_sub = await _setup_user_and_auth(client)

    from sqlmodel import select
    user = (await async_session.exec(select(User).where(User.cognito_sub == cognito_sub))).first()

    job = await _create_upload_and_job(
        async_session,
        user.id,
        status="failed",
        error_code="UNSUPPORTED_FORMAT",
        error_message="This file format is not yet supported.",
    )

    try:
        response = await client.get(f"/api/v1/jobs/{job.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "failed"
        assert data["error"]["code"] == "UNSUPPORTED_FORMAT"
        assert data["error"]["message"] == "This file format is not yet supported."
        assert data["result"] is None
    finally:
        app.dependency_overrides.pop(get_current_user_payload, None)
