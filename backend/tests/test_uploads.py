import io
import uuid
from unittest.mock import AsyncMock, patch

import pytest

from app.core.security import get_current_user_payload
from app.main import app
from app.models.user import User


# ==================== Helper: create test user and auth ====================


async def _create_test_user(client):
    """Create a test user via signup+verify+login flow and return cognito_sub."""
    from app.core.exceptions import RegistrationError

    await client.post(
        "/api/v1/auth/signup",
        json={"email": "uploader@example.com", "password": "StrongPass1!"},
    )
    await client.post(
        "/api/v1/auth/verify",
        json={"email": "uploader@example.com", "code": "123456"},
    )
    await client.post(
        "/api/v1/auth/login",
        json={"email": "uploader@example.com", "password": "StrongPass1!"},
    )
    return "test-cognito-sub-123"


def _auth_override(cognito_sub: str):
    async def mock_payload():
        return {"sub": cognito_sub}
    return mock_payload


def _csv_file(content: bytes = b"date,amount\n2024-01-01,100", name: str = "statement.csv"):
    return {"file": (name, io.BytesIO(content), "text/csv")}


def _pdf_file(content: bytes = b"%PDF-1.4 fake content", name: str = "statement.pdf"):
    return {"file": (name, io.BytesIO(content), "application/pdf")}


# ==================== Upload Tests (Story 2.1) ====================


@pytest.mark.asyncio
@patch("app.services.upload_service._get_s3_client")
async def test_upload_csv_success(mock_s3_factory, client, mock_rate_limiter):
    """Successful CSV upload returns 202 with jobId and statusUrl."""
    mock_s3 = mock_s3_factory.return_value
    mock_s3.put_object.return_value = {}

    cognito_sub = await _create_test_user(client)
    app.dependency_overrides[get_current_user_payload] = _auth_override(cognito_sub)

    try:
        response = await client.post("/api/v1/uploads", files=_csv_file())

        assert response.status_code == 202
        data = response.json()
        assert "jobId" in data
        assert "statusUrl" in data
        assert data["statusUrl"].startswith("/api/v1/jobs/")
        mock_s3.put_object.assert_called_once()
    finally:
        app.dependency_overrides.pop(get_current_user_payload, None)


@pytest.mark.asyncio
@patch("app.services.upload_service._get_s3_client")
async def test_upload_pdf_success(mock_s3_factory, client, mock_rate_limiter):
    """Successful PDF upload returns 202."""
    mock_s3 = mock_s3_factory.return_value
    mock_s3.put_object.return_value = {}

    cognito_sub = await _create_test_user(client)
    app.dependency_overrides[get_current_user_payload] = _auth_override(cognito_sub)

    try:
        response = await client.post("/api/v1/uploads", files=_pdf_file())

        assert response.status_code == 202
        data = response.json()
        assert "jobId" in data
    finally:
        app.dependency_overrides.pop(get_current_user_payload, None)


@pytest.mark.asyncio
async def test_upload_invalid_file_type(client, mock_rate_limiter):
    """Uploading unsupported file type returns 400 INVALID_FILE_TYPE."""
    cognito_sub = await _create_test_user(client)
    app.dependency_overrides[get_current_user_payload] = _auth_override(cognito_sub)

    try:
        response = await client.post(
            "/api/v1/uploads",
            files={"file": ("image.png", io.BytesIO(b"fake image"), "image/png")},
        )

        assert response.status_code == 400
        data = response.json()
        assert data["error"]["code"] == "INVALID_FILE_TYPE"
    finally:
        app.dependency_overrides.pop(get_current_user_payload, None)


@pytest.mark.asyncio
async def test_upload_file_too_large(client, mock_rate_limiter):
    """Uploading file > 10MB returns 400 FILE_TOO_LARGE."""
    cognito_sub = await _create_test_user(client)
    app.dependency_overrides[get_current_user_payload] = _auth_override(cognito_sub)

    try:
        large_content = b"x" * (11 * 1024 * 1024)  # 11MB
        response = await client.post(
            "/api/v1/uploads",
            files={"file": ("big.csv", io.BytesIO(large_content), "text/csv")},
        )

        assert response.status_code == 400
        data = response.json()
        assert data["error"]["code"] == "FILE_TOO_LARGE"
    finally:
        app.dependency_overrides.pop(get_current_user_payload, None)


@pytest.mark.asyncio
@patch("app.services.upload_service._get_s3_client")
async def test_upload_rate_limited(mock_s3_factory, client, mock_rate_limiter):
    """Rate limited upload returns 429 RATE_LIMITED."""
    from app.core.exceptions import ValidationError

    mock_s3 = mock_s3_factory.return_value
    mock_s3.put_object.return_value = {}

    cognito_sub = await _create_test_user(client)
    app.dependency_overrides[get_current_user_payload] = _auth_override(cognito_sub)

    # Make the rate limiter raise ValidationError for uploads
    mock_rate_limiter.check_upload_rate_limit.side_effect = ValidationError(
        code="RATE_LIMITED",
        message="You've uploaded a lot of files recently. Please try again in a few minutes.",
        status_code=429,
    )

    try:
        response = await client.post("/api/v1/uploads", files=_csv_file())

        assert response.status_code == 429
        data = response.json()
        assert data["error"]["code"] == "RATE_LIMITED"
    finally:
        app.dependency_overrides.pop(get_current_user_payload, None)


@pytest.mark.asyncio
async def test_upload_unauthenticated(client):
    """Upload without auth token returns 401/403."""
    response = await client.post("/api/v1/uploads", files=_csv_file())

    assert response.status_code in (401, 403)


@pytest.mark.asyncio
@patch("app.services.upload_service._get_s3_client")
async def test_upload_s3_failure(mock_s3_factory, client, mock_rate_limiter):
    """S3 upload failure returns 500 UPLOAD_FAILED."""
    from botocore.exceptions import ClientError

    mock_s3 = mock_s3_factory.return_value
    mock_s3.put_object.side_effect = ClientError(
        {"Error": {"Code": "InternalError", "Message": "S3 failed"}},
        "PutObject",
    )

    cognito_sub = await _create_test_user(client)
    app.dependency_overrides[get_current_user_payload] = _auth_override(cognito_sub)

    try:
        response = await client.post("/api/v1/uploads", files=_csv_file())

        assert response.status_code == 500
        data = response.json()
        assert data["error"]["code"] == "UPLOAD_FAILED"
    finally:
        app.dependency_overrides.pop(get_current_user_payload, None)


@pytest.mark.asyncio
@patch("app.services.upload_service._get_s3_client")
async def test_upload_creates_db_records(mock_s3_factory, client, async_session, mock_rate_limiter):
    """Upload creates both upload and processing_job records in DB."""
    mock_s3 = mock_s3_factory.return_value
    mock_s3.put_object.return_value = {}

    cognito_sub = await _create_test_user(client)
    app.dependency_overrides[get_current_user_payload] = _auth_override(cognito_sub)

    try:
        response = await client.post("/api/v1/uploads", files=_csv_file())

        assert response.status_code == 202

        # Verify DB records via a second query
        from sqlmodel import select
        from app.models.upload import Upload
        from app.models.processing_job import ProcessingJob

        uploads = (await async_session.exec(select(Upload))).all()
        assert len(uploads) == 1
        assert uploads[0].file_name == "statement.csv"
        assert uploads[0].mime_type == "text/csv"

        jobs = (await async_session.exec(select(ProcessingJob))).all()
        assert len(jobs) == 1
        assert jobs[0].upload_id == uploads[0].id
        assert jobs[0].status == "validated"
    finally:
        app.dependency_overrides.pop(get_current_user_payload, None)


@pytest.mark.asyncio
@patch("app.services.upload_service._get_s3_client")
async def test_upload_s3_key_format(mock_s3_factory, client, mock_rate_limiter):
    """S3 key follows {user_id}/{job_id}_original.{ext} pattern."""
    mock_s3 = mock_s3_factory.return_value
    mock_s3.put_object.return_value = {}

    cognito_sub = await _create_test_user(client)
    app.dependency_overrides[get_current_user_payload] = _auth_override(cognito_sub)

    try:
        response = await client.post("/api/v1/uploads", files=_csv_file())

        assert response.status_code == 202

        # Check the S3 key format
        call_kwargs = mock_s3.put_object.call_args[1]
        s3_key = call_kwargs["Key"]
        parts = s3_key.split("/")
        assert len(parts) == 2
        # First part is user_id (UUID format)
        uuid.UUID(parts[0])
        # Second part is {job_id}_original.csv
        assert parts[1].endswith("_original.csv")
    finally:
        app.dependency_overrides.pop(get_current_user_payload, None)
