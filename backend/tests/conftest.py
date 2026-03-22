from collections.abc import AsyncGenerator
from unittest.mock import MagicMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession as SQLModelAsyncSession

from app.api.deps import get_cognito_service, get_db
from app.main import app
from app.services.cognito_service import CognitoService

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
    return mock


@pytest_asyncio.fixture
async def client(async_engine, mock_cognito_service) -> AsyncGenerator[AsyncClient, None]:
    async def override_get_db() -> AsyncGenerator[SQLModelAsyncSession, None]:
        async with SQLModelAsyncSession(async_engine) as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_cognito_service] = lambda: mock_cognito_service

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()
