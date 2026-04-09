"""Tests for GET /api/v1/profile endpoint (Story 4.4)."""
import os
import tempfile
import uuid
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession as SQLModelAsyncSession

from app.models.financial_profile import FinancialProfile
from app.models.user import User


# ==================== Fixtures ====================


@pytest_asyncio.fixture
async def profile_api_engine():
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)
    await engine.dispose()
    os.unlink(db_path)


@pytest_asyncio.fixture
async def profile_api_session(profile_api_engine) -> SQLModelAsyncSession:
    async with SQLModelAsyncSession(profile_api_engine) as session:
        yield session


def _auth_override(cognito_sub: str):
    async def mock_payload():
        return {"sub": cognito_sub}
    return mock_payload


async def _create_user(session: SQLModelAsyncSession, cognito_sub: str, email: str):
    user_id = uuid.uuid4()
    user = User(id=user_id, email=email, cognito_sub=cognito_sub, locale="en")
    session.add(user)
    await session.flush()
    return user_id


@pytest_asyncio.fixture
async def profile_client(profile_api_engine):
    from app.api.deps import get_db, get_cognito_service, get_rate_limiter
    from app.main import app

    async def override_get_db():
        async with SQLModelAsyncSession(profile_api_engine) as session:
            yield session

    mock_cognito = MagicMock()
    mock_rate = AsyncMock()
    mock_rate.check_rate_limit.return_value = None

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_cognito_service] = lambda: mock_cognito
    app.dependency_overrides[get_rate_limiter] = lambda: mock_rate

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


# ==================== API Endpoint Tests ====================


class TestProfileEndpoint:
    """Test GET /api/v1/profile."""

    @pytest.mark.asyncio
    async def test_returns_profile(self, profile_client, profile_api_session):
        """Returns 200 with profile data when profile exists."""
        from app.core.security import get_current_user_payload
        from app.main import app

        cognito_sub = "profile-get-sub"
        user_id = await _create_user(profile_api_session, cognito_sub, "profile@test.com")

        profile = FinancialProfile(
            user_id=user_id,
            total_income=50000,
            total_expenses=-20000,
            category_totals={"food": -15000, "transport": -5000},
            period_start=datetime(2026, 1, 1),
            period_end=datetime(2026, 3, 31),
        )
        profile_api_session.add(profile)
        await profile_api_session.commit()

        app.dependency_overrides[get_current_user_payload] = _auth_override(cognito_sub)
        try:
            response = await profile_client.get("/api/v1/profile")
            assert response.status_code == 200
            data = response.json()
            assert data["totalIncome"] == 50000
            assert data["totalExpenses"] == -20000
            assert data["categoryTotals"]["food"] == -15000
            assert data["categoryTotals"]["transport"] == -5000
            assert data["periodStart"] is not None
            assert data["periodEnd"] is not None
            assert data["updatedAt"] is not None
        finally:
            app.dependency_overrides.pop(get_current_user_payload, None)

    @pytest.mark.asyncio
    async def test_404_when_no_profile(self, profile_client, profile_api_session):
        """Returns 404 when no profile exists for user."""
        from app.core.security import get_current_user_payload
        from app.main import app

        cognito_sub = "profile-404-sub"
        await _create_user(profile_api_session, cognito_sub, "no-profile@test.com")
        await profile_api_session.commit()

        app.dependency_overrides[get_current_user_payload] = _auth_override(cognito_sub)
        try:
            response = await profile_client.get("/api/v1/profile")
            assert response.status_code == 404
        finally:
            app.dependency_overrides.pop(get_current_user_payload, None)

    @pytest.mark.asyncio
    async def test_camel_case_keys(self, profile_client, profile_api_session):
        """Response uses camelCase keys."""
        from app.core.security import get_current_user_payload
        from app.main import app

        cognito_sub = "profile-camel-sub"
        user_id = await _create_user(profile_api_session, cognito_sub, "camel@test.com")

        profile = FinancialProfile(
            user_id=user_id,
            total_income=10000,
            total_expenses=-5000,
            category_totals={"food": -5000},
        )
        profile_api_session.add(profile)
        await profile_api_session.commit()

        app.dependency_overrides[get_current_user_payload] = _auth_override(cognito_sub)
        try:
            response = await profile_client.get("/api/v1/profile")
            data = response.json()
            assert "totalIncome" in data
            assert "totalExpenses" in data
            assert "categoryTotals" in data
            assert "periodStart" in data
            assert "periodEnd" in data
            assert "updatedAt" in data
            # No snake_case keys
            assert "total_income" not in data
            assert "total_expenses" not in data
            assert "category_totals" not in data
        finally:
            app.dependency_overrides.pop(get_current_user_payload, None)

    @pytest.mark.asyncio
    async def test_unauthenticated(self, profile_client):
        """Unauthenticated access returns 401/403."""
        response = await profile_client.get("/api/v1/profile")
        assert response.status_code in (401, 403)

    @pytest.mark.asyncio
    async def test_tenant_isolation(self, profile_client, profile_api_session):
        """User A cannot see user B's profile."""
        from app.core.security import get_current_user_payload
        from app.main import app

        user_a_id = await _create_user(profile_api_session, "profile-a-sub", "a@test.com")
        user_b_id = await _create_user(profile_api_session, "profile-b-sub", "b@test.com")

        profile_a = FinancialProfile(
            user_id=user_a_id, total_income=100000, total_expenses=-50000,
            category_totals={"salary": 100000},
        )
        profile_b = FinancialProfile(
            user_id=user_b_id, total_income=200000, total_expenses=-80000,
            category_totals={"salary": 200000},
        )
        profile_api_session.add(profile_a)
        profile_api_session.add(profile_b)
        await profile_api_session.commit()

        # User A sees only their profile
        app.dependency_overrides[get_current_user_payload] = _auth_override("profile-a-sub")
        try:
            response = await profile_client.get("/api/v1/profile")
            data = response.json()
            assert data["totalIncome"] == 100000
        finally:
            app.dependency_overrides.pop(get_current_user_payload, None)

        # User B sees only their profile
        app.dependency_overrides[get_current_user_payload] = _auth_override("profile-b-sub")
        try:
            response = await profile_client.get("/api/v1/profile")
            data = response.json()
            assert data["totalIncome"] == 200000
        finally:
            app.dependency_overrides.pop(get_current_user_payload, None)
