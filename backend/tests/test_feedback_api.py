"""Tests for POST /api/v1/cards/interactions endpoint (Story 7.1)."""
import os
import tempfile
import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import SQLModel, func, select
from sqlmodel.ext.asyncio.session import AsyncSession as SQLModelAsyncSession

from app.models.feedback import CardInteraction
from app.models.insight import Insight
from app.models.user import User


def _utcnow():
    return datetime.now(UTC)


@pytest_asyncio.fixture
async def feedback_engine():
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
async def feedback_session(feedback_engine) -> SQLModelAsyncSession:
    async with SQLModelAsyncSession(feedback_engine) as session:
        yield session


def _auth_override(cognito_sub: str):
    async def mock_payload():
        return {"sub": cognito_sub}

    return mock_payload


async def _create_user(session: SQLModelAsyncSession, cognito_sub: str, email: str):
    user = User(email=email, cognito_sub=cognito_sub, locale="en")
    session.add(user)
    await session.flush()
    return user.id


async def _create_insight(session: SQLModelAsyncSession, user_id: uuid.UUID):
    insight = Insight(
        user_id=user_id,
        headline="Test",
        key_metric="100 UAH",
        why_it_matters="because",
        deep_dive="details",
        severity="medium",
        category="food",
    )
    session.add(insight)
    await session.flush()
    return insight.id


@pytest_asyncio.fixture
async def feedback_client(feedback_engine):
    from app.api.deps import get_cognito_service, get_db, get_rate_limiter
    from app.main import app

    async def override_get_db():
        async with SQLModelAsyncSession(feedback_engine) as session:
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


class TestCardInteractionsEndpoint:
    """AC #4: POST /api/v1/cards/interactions inserts rows and returns 204."""

    @pytest.mark.asyncio
    async def test_valid_batch_returns_204_and_inserts(
        self, feedback_client, feedback_session
    ):
        from app.core.security import get_current_user_payload
        from app.main import app

        cognito_sub = "feedback-insert-sub"
        user_id = await _create_user(feedback_session, cognito_sub, "fi@test.com")
        card_id = await _create_insight(feedback_session, user_id)
        await feedback_session.commit()

        app.dependency_overrides[get_current_user_payload] = _auth_override(cognito_sub)
        try:
            payload = {
                "interactions": [
                    {
                        "cardId": str(card_id),
                        "timeOnCardMs": 12000,
                        "educationExpanded": True,
                        "educationDepthReached": 2,
                        "swipeDirection": "right",
                        "cardPositionInFeed": 3,
                    }
                ]
            }
            resp = await feedback_client.post("/api/v1/cards/interactions", json=payload)
            assert resp.status_code == 204
            assert resp.content == b""

            total = (
                await feedback_session.exec(
                    select(func.count()).select_from(CardInteraction)
                )
            ).one()
            assert total == 1
            row = (await feedback_session.exec(select(CardInteraction))).first()
            assert row.engagement_score == 79
            assert row.card_id == card_id
            assert row.user_id == user_id
        finally:
            app.dependency_overrides.pop(get_current_user_payload, None)

    @pytest.mark.asyncio
    async def test_batch_over_20_rejected(self, feedback_client, feedback_session):
        from app.core.security import get_current_user_payload
        from app.main import app

        cognito_sub = "feedback-maxbatch-sub"
        user_id = await _create_user(feedback_session, cognito_sub, "max@test.com")
        card_id = await _create_insight(feedback_session, user_id)
        await feedback_session.commit()

        app.dependency_overrides[get_current_user_payload] = _auth_override(cognito_sub)
        try:
            item = {
                "cardId": str(card_id),
                "timeOnCardMs": 5000,
                "educationExpanded": False,
                "educationDepthReached": 0,
                "swipeDirection": "none",
                "cardPositionInFeed": 0,
            }
            payload = {"interactions": [item for _ in range(21)]}
            resp = await feedback_client.post("/api/v1/cards/interactions", json=payload)
            assert resp.status_code == 422
        finally:
            app.dependency_overrides.pop(get_current_user_payload, None)

    @pytest.mark.asyncio
    async def test_empty_batch_rejected(self, feedback_client, feedback_session):
        from app.core.security import get_current_user_payload
        from app.main import app

        cognito_sub = "feedback-empty-sub"
        await _create_user(feedback_session, cognito_sub, "empty@test.com")
        await feedback_session.commit()

        app.dependency_overrides[get_current_user_payload] = _auth_override(cognito_sub)
        try:
            resp = await feedback_client.post(
                "/api/v1/cards/interactions", json={"interactions": []}
            )
            assert resp.status_code == 422
        finally:
            app.dependency_overrides.pop(get_current_user_payload, None)

    @pytest.mark.asyncio
    async def test_invalid_swipe_direction_rejected(
        self, feedback_client, feedback_session
    ):
        from app.core.security import get_current_user_payload
        from app.main import app

        cognito_sub = "feedback-swipe-sub"
        user_id = await _create_user(feedback_session, cognito_sub, "sw@test.com")
        card_id = await _create_insight(feedback_session, user_id)
        await feedback_session.commit()

        app.dependency_overrides[get_current_user_payload] = _auth_override(cognito_sub)
        try:
            payload = {
                "interactions": [
                    {
                        "cardId": str(card_id),
                        "timeOnCardMs": 5000,
                        "educationExpanded": False,
                        "educationDepthReached": 0,
                        "swipeDirection": "diagonal",
                        "cardPositionInFeed": 0,
                    }
                ]
            }
            resp = await feedback_client.post("/api/v1/cards/interactions", json=payload)
            assert resp.status_code == 422
        finally:
            app.dependency_overrides.pop(get_current_user_payload, None)

    @pytest.mark.asyncio
    async def test_invalid_education_depth_rejected(
        self, feedback_client, feedback_session
    ):
        from app.core.security import get_current_user_payload
        from app.main import app

        cognito_sub = "feedback-depth-sub"
        user_id = await _create_user(feedback_session, cognito_sub, "dp@test.com")
        card_id = await _create_insight(feedback_session, user_id)
        await feedback_session.commit()

        app.dependency_overrides[get_current_user_payload] = _auth_override(cognito_sub)
        try:
            payload = {
                "interactions": [
                    {
                        "cardId": str(card_id),
                        "timeOnCardMs": 5000,
                        "educationExpanded": False,
                        "educationDepthReached": 3,  # out of range (le=2)
                        "swipeDirection": "none",
                        "cardPositionInFeed": 0,
                    }
                ]
            }
            resp = await feedback_client.post("/api/v1/cards/interactions", json=payload)
            assert resp.status_code == 422
        finally:
            app.dependency_overrides.pop(get_current_user_payload, None)

    @pytest.mark.asyncio
    async def test_unauthenticated_request_rejected(self, feedback_client):
        """Missing auth → 401/403."""
        resp = await feedback_client.post(
            "/api/v1/cards/interactions",
            json={"interactions": []},
        )
        assert resp.status_code in (401, 403)
