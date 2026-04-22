"""Tests for GET /api/v1/health-score endpoint (Story 4.5)."""
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

from app.models.financial_health_score import FinancialHealthScore
from app.models.user import User


# ==================== Fixtures ====================


@pytest_asyncio.fixture
async def hs_api_engine():
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
async def hs_api_session(hs_api_engine) -> SQLModelAsyncSession:
    async with SQLModelAsyncSession(hs_api_engine) as session:
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
async def hs_client(hs_api_engine):
    from app.api.deps import get_db, get_cognito_service, get_rate_limiter
    from app.main import app

    async def override_get_db():
        async with SQLModelAsyncSession(hs_api_engine) as session:
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


class TestHealthScoreEndpoint:
    """Test GET /api/v1/health-score."""

    @pytest.mark.asyncio
    async def test_returns_health_score(self, hs_client, hs_api_session):
        """Returns 200 with health score data when score exists."""
        from app.core.security import get_current_user_payload
        from app.main import app

        cognito_sub = "hs-get-sub"
        user_id = await _create_user(hs_api_session, cognito_sub, "hs@test.com")

        score = FinancialHealthScore(
            user_id=user_id,
            score=72,
            calculated_at=datetime(2026, 3, 15, 10, 0, 0),
            breakdown={
                "savings_ratio": 80,
                "category_diversity": 65,
                "expense_regularity": 70,
                "income_coverage": 60,
            },
        )
        hs_api_session.add(score)
        await hs_api_session.commit()

        app.dependency_overrides[get_current_user_payload] = _auth_override(cognito_sub)
        try:
            response = await hs_client.get("/api/v1/health-score")
            assert response.status_code == 200
            data = response.json()
            assert data["score"] == 72
            assert data["breakdown"]["savings_ratio"] == 80
            assert data["calculatedAt"] is not None
        finally:
            app.dependency_overrides.pop(get_current_user_payload, None)

    @pytest.mark.asyncio
    async def test_404_when_no_score(self, hs_client, hs_api_session):
        """Returns 404 when no health score exists."""
        from app.core.security import get_current_user_payload
        from app.main import app

        cognito_sub = "hs-404-sub"
        await _create_user(hs_api_session, cognito_sub, "no-hs@test.com")
        await hs_api_session.commit()

        app.dependency_overrides[get_current_user_payload] = _auth_override(cognito_sub)
        try:
            response = await hs_client.get("/api/v1/health-score")
            assert response.status_code == 404
        finally:
            app.dependency_overrides.pop(get_current_user_payload, None)

    @pytest.mark.asyncio
    async def test_camel_case_keys(self, hs_client, hs_api_session):
        """Response uses camelCase keys."""
        from app.core.security import get_current_user_payload
        from app.main import app

        cognito_sub = "hs-camel-sub"
        user_id = await _create_user(hs_api_session, cognito_sub, "camel-hs@test.com")

        score = FinancialHealthScore(
            user_id=user_id,
            score=50,
            calculated_at=datetime(2026, 3, 15),
            breakdown={"savings_ratio": 50, "category_diversity": 50, "expense_regularity": 50, "income_coverage": 50},
        )
        hs_api_session.add(score)
        await hs_api_session.commit()

        app.dependency_overrides[get_current_user_payload] = _auth_override(cognito_sub)
        try:
            response = await hs_client.get("/api/v1/health-score")
            data = response.json()
            assert "score" in data
            assert "breakdown" in data
            assert "calculatedAt" in data
            # No snake_case keys at top level
            assert "calculated_at" not in data
        finally:
            app.dependency_overrides.pop(get_current_user_payload, None)

    @pytest.mark.asyncio
    async def test_unauthenticated(self, hs_client):
        """Unauthenticated access returns 401/403."""
        response = await hs_client.get("/api/v1/health-score")
        assert response.status_code in (401, 403)

    @pytest.mark.asyncio
    async def test_savings_ratio_null_serializes_as_json_null(self, hs_client, hs_api_session):
        """Story 4.9 AC #2: a null savings_ratio in the stored breakdown round-trips as JSON `null`."""
        from app.core.security import get_current_user_payload
        from app.main import app

        cognito_sub = "hs-null-sub"
        user_id = await _create_user(hs_api_session, cognito_sub, "null-hs@test.com")

        score = FinancialHealthScore(
            user_id=user_id,
            score=60,
            calculated_at=datetime(2026, 3, 15),
            breakdown={
                "savings_ratio": None,
                "category_diversity": 60,
                "expense_regularity": 60,
                "income_coverage": 60,
            },
        )
        hs_api_session.add(score)
        await hs_api_session.commit()

        app.dependency_overrides[get_current_user_payload] = _auth_override(cognito_sub)
        try:
            response = await hs_client.get("/api/v1/health-score")
            assert response.status_code == 200
            data = response.json()
            assert "savings_ratio" in data["breakdown"]
            assert data["breakdown"]["savings_ratio"] is None
        finally:
            app.dependency_overrides.pop(get_current_user_payload, None)


class TestHealthScoreHistoryEndpoint:
    """Test GET /api/v1/health-score/history."""

    @pytest.mark.asyncio
    async def test_returns_history_list(self, hs_client, hs_api_session):
        """Returns 200 with array of score history items."""
        from app.core.security import get_current_user_payload
        from app.main import app

        cognito_sub = "hist-get-sub"
        user_id = await _create_user(hs_api_session, cognito_sub, "hist@test.com")

        breakdown = {"savings_ratio": 50, "category_diversity": 50, "expense_regularity": 50, "income_coverage": 50}
        hs_api_session.add(FinancialHealthScore(user_id=user_id, score=40, calculated_at=datetime(2026, 1, 1), breakdown=breakdown))
        hs_api_session.add(FinancialHealthScore(user_id=user_id, score=70, calculated_at=datetime(2026, 2, 1), breakdown=breakdown))
        await hs_api_session.commit()

        app.dependency_overrides[get_current_user_payload] = _auth_override(cognito_sub)
        try:
            response = await hs_client.get("/api/v1/health-score/history")
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 2
            assert data[0]["score"] == 40  # Ordered ASC
            assert data[1]["score"] == 70
            # camelCase keys
            assert "calculatedAt" in data[0]
            assert "calculated_at" not in data[0]
        finally:
            app.dependency_overrides.pop(get_current_user_payload, None)

    @pytest.mark.asyncio
    async def test_returns_empty_array_when_no_scores(self, hs_client, hs_api_session):
        """Returns empty array (not 404) when no scores exist."""
        from app.core.security import get_current_user_payload
        from app.main import app

        cognito_sub = "hist-empty-sub"
        await _create_user(hs_api_session, cognito_sub, "hist-empty@test.com")
        await hs_api_session.commit()

        app.dependency_overrides[get_current_user_payload] = _auth_override(cognito_sub)
        try:
            response = await hs_client.get("/api/v1/health-score/history")
            assert response.status_code == 200
            assert response.json() == []
        finally:
            app.dependency_overrides.pop(get_current_user_payload, None)

    @pytest.mark.asyncio
    async def test_unauthenticated(self, hs_client):
        """Unauthenticated access returns 401/403."""
        response = await hs_client.get("/api/v1/health-score/history")
        assert response.status_code in (401, 403)
