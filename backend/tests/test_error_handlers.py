import pytest
from httpx import ASGITransport, AsyncClient
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel

from app.core.exceptions import (
    unhandled_exception_handler,
    request_validation_error_handler,
)


def create_test_app() -> FastAPI:
    """Create a minimal FastAPI app for testing error handlers."""
    test_app = FastAPI()
    test_app.add_exception_handler(
        RequestValidationError, request_validation_error_handler
    )
    test_app.add_exception_handler(Exception, unhandled_exception_handler)

    class ItemRequest(BaseModel):
        name: str
        count: int

    @test_app.post("/validate")
    async def validate_endpoint(item: ItemRequest):
        return {"name": item.name}

    @test_app.get("/crash")
    async def crash_endpoint():
        raise RuntimeError("unexpected database failure")

    return test_app


@pytest.mark.asyncio
async def test_catch_all_returns_sanitized_500():
    app = create_test_app()
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/crash")

    assert response.status_code == 500
    data = response.json()
    assert data["error"]["code"] == "INTERNAL_ERROR"
    assert data["error"]["message"] == "Something went wrong"
    assert "database" not in str(data)
    assert "RuntimeError" not in str(data)


@pytest.mark.asyncio
async def test_request_validation_error_returns_friendly_format():
    app = create_test_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/validate",
            json={"name": 123},  # missing 'count', wrong type for 'name'
        )

    assert response.status_code == 422
    data = response.json()
    assert data["error"]["code"] == "VALIDATION_ERROR"
    assert data["error"]["message"] == "Please check your input and try again"
    assert "fields" in data["error"]["details"]


@pytest.mark.asyncio
async def test_catch_all_does_not_leak_stack_trace():
    app = create_test_app()
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/crash")

    body = response.text
    assert "Traceback" not in body
    assert "File" not in body
    assert "line" not in body


@pytest.mark.asyncio
async def test_real_app_has_catch_all_handler_registered():
    """Verify that the real app has the catch-all Exception handler registered."""
    from app.main import app

    exception_handlers = app.exception_handlers
    assert Exception in exception_handlers, (
        "catch-all Exception handler not registered on the real app"
    )
    assert RequestValidationError in exception_handlers, (
        "RequestValidationError handler not registered on the real app"
    )
