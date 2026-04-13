"""Tests for RequestLoggingMiddleware (Story 6.4)."""

import logging
import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.main import app

_MW_LOGGER = "app.core.middleware"


@pytest.fixture(autouse=True)
def _enable_app_propagation():
    """Enable propagation on the app logger so caplog (root-attached) captures records."""
    app_logger = logging.getLogger("app")
    app_logger.propagate = True
    yield
    app_logger.propagate = False


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_health_endpoint_no_log_entry(client, caplog):
    """GET /health returns 200 without generating a request log entry."""
    with caplog.at_level(logging.INFO, logger=_MW_LOGGER):
        response = await client.get("/health")

    assert response.status_code == 200
    middleware_messages = [r.message for r in caplog.records if r.name == _MW_LOGGER]
    assert len(middleware_messages) == 0, "Health endpoint should not produce middleware log"


@pytest.mark.asyncio
async def test_request_returns_x_request_id_header(client):
    """A standard API request returns X-Request-ID response header."""
    response = await client.get("/api/v1/health-check-nonexistent")
    assert "X-Request-ID" in response.headers


@pytest.mark.asyncio
async def test_x_request_id_is_valid_uuid(client):
    """X-Request-ID value is a valid UUID string."""
    response = await client.get("/api/v1/health-check-nonexistent")
    request_id = response.headers.get("X-Request-ID", "")
    parsed = uuid.UUID(request_id)
    assert str(parsed) == request_id


@pytest.mark.asyncio
async def test_request_log_entry_contains_required_fields(client, caplog):
    """The request log entry contains method, path, status_code, duration_ms, request_id."""
    with caplog.at_level(logging.INFO, logger=_MW_LOGGER):
        await client.get("/health-nonexistent")

    middleware_records = [r for r in caplog.records if r.name == _MW_LOGGER]
    assert len(middleware_records) >= 1, "Expected at least one middleware log record"

    record = middleware_records[0]
    assert hasattr(record, "method")
    assert hasattr(record, "path")
    assert hasattr(record, "status_code")
    assert hasattr(record, "duration_ms")
    assert hasattr(record, "request_id")
    assert record.method == "GET"
    assert record.path == "/health-nonexistent"
    assert isinstance(record.duration_ms, int)
