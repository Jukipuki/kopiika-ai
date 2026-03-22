from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession as SQLModelAsyncSession

from app.api.deps import get_cognito_service, get_db, get_rate_limiter
from app.main import app
from app.services.cognito_service import CognitoService
from app.services.rate_limiter import RateLimiter

TEST_DATABASE_URL = "sqlite+aiosqlite:///./test.db"


@pytest_asyncio.fixture
async def async_engine():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def async_session(async_engine) -> AsyncGenerator[SQLModelAsyncSession, None]:
    async with SQLModelAsyncSession(async_engine) as session:
        yield session


@pytest.fixture
def mock_cognito_service():
    mock = MagicMock(spec=CognitoService)
    mock.sign_up.return_value = {
        "user_sub": "test-cognito-sub-123",
        "user_confirmed": False,
    }
    mock.confirm_sign_up.return_value = {"confirmed": True}
    mock.resend_confirmation_code.return_value = {"sent": True}
    mock.authenticate_user.return_value = {
        "access_token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ0ZXN0LWNvZ25pdG8tc3ViLTEyMyIsImVtYWlsIjoidGVzdEBleGFtcGxlLmNvbSIsImlzcyI6Imh0dHBzOi8vY29nbml0by1pZHAuZXUtY2VudHJhbC0xLmFtYXpvbmF3cy5jb20vdGVzdCIsImV4cCI6OTk5OTk5OTk5OX0.fake-signature",
        "refresh_token": "test-refresh-token",
        "expires_in": 900,
    }
    mock.refresh_tokens.return_value = {
        "access_token": "new-access-token",
        "expires_in": 900,
    }
    mock.global_sign_out.return_value = {"signed_out": True}
    return mock


@pytest.fixture
def mock_rate_limiter():
    mock = AsyncMock(spec=RateLimiter)
    mock.check_rate_limit.return_value = None
    mock.record_failed_attempt.return_value = None
    mock.clear_attempts.return_value = None
    return mock


@pytest_asyncio.fixture
async def client(
    async_engine, mock_cognito_service, mock_rate_limiter
) -> AsyncGenerator[AsyncClient, None]:
    async def override_get_db() -> AsyncGenerator[SQLModelAsyncSession, None]:
        async with SQLModelAsyncSession(async_engine) as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_cognito_service] = lambda: mock_cognito_service
    app.dependency_overrides[get_rate_limiter] = lambda: mock_rate_limiter

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()
