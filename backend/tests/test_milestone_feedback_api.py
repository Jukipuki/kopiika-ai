"""Tests for milestone feedback API (Story 7.7).

Covers GET /api/v1/milestone-feedback/pending and
POST /api/v1/milestone-feedback/respond, including triggers, frequency cap,
priority, and idempotency.
"""
import os
import tempfile
import uuid
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession as SQLModelAsyncSession
from unittest.mock import AsyncMock, MagicMock

from app.models.feedback_response import FeedbackResponse
from app.models.financial_health_score import FinancialHealthScore
from app.models.processing_job import ProcessingJob
from app.models.upload import Upload
from app.models.user import User


@pytest_asyncio.fixture
async def ms_engine():
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
async def ms_session(ms_engine) -> SQLModelAsyncSession:
    async with SQLModelAsyncSession(ms_engine) as session:
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


async def _create_upload_and_job(
    session: SQLModelAsyncSession, user_id: uuid.UUID, status: str = "completed"
) -> None:
    upload = Upload(
        user_id=user_id,
        file_name="statement.csv",
        s3_key=f"{user_id}/{uuid.uuid4()}.csv",
        file_size=1024,
        mime_type="text/csv",
    )
    session.add(upload)
    await session.flush()
    job = ProcessingJob(
        user_id=user_id,
        upload_id=upload.id,
        status=status,
    )
    session.add(job)
    await session.flush()


async def _create_health_score(
    session: SQLModelAsyncSession,
    user_id: uuid.UUID,
    score: int,
    calculated_at: datetime,
) -> None:
    row = FinancialHealthScore(
        user_id=user_id,
        score=score,
        calculated_at=calculated_at,
    )
    session.add(row)
    await session.flush()


async def _create_response(
    session: SQLModelAsyncSession,
    user_id: uuid.UUID,
    card_type: str,
    response_value: str = "dismissed",
    created_at: datetime | None = None,
) -> None:
    row = FeedbackResponse(
        user_id=user_id,
        feedback_card_type=card_type,
        response_value=response_value,
    )
    if created_at is not None:
        row.created_at = created_at
    session.add(row)
    await session.flush()


@pytest_asyncio.fixture
async def ms_client(ms_engine):
    from app.api.deps import get_cognito_service, get_db, get_rate_limiter
    from app.main import app

    async def override_get_db():
        async with SQLModelAsyncSession(ms_engine) as session:
            yield session

    mock_cognito = MagicMock()
    mock_rate = AsyncMock()
    mock_rate.check_feedback_rate_limit.return_value = None

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_cognito_service] = lambda: mock_cognito
    app.dependency_overrides[get_rate_limiter] = lambda: mock_rate

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


class TestGetPendingMilestoneCards:
    """Tests for GET /api/v1/milestone-feedback/pending."""

    @pytest.mark.asyncio
    async def test_no_cards_when_fewer_than_3_uploads(self, ms_client, ms_session):
        from app.core.security import get_current_user_payload
        from app.main import app

        cognito_sub = "ms-pending-lt3"
        user_id = await _create_user(ms_session, cognito_sub, "lt3@test.com")
        await _create_upload_and_job(ms_session, user_id)
        await _create_upload_and_job(ms_session, user_id)
        await ms_session.commit()

        app.dependency_overrides[get_current_user_payload] = _auth_override(cognito_sub)
        try:
            resp = await ms_client.get("/api/v1/milestone-feedback/pending")
            assert resp.status_code == 200
            assert resp.json() == {"cards": []}
        finally:
            app.dependency_overrides.pop(get_current_user_payload, None)

    @pytest.mark.asyncio
    async def test_returns_3rd_upload_card_when_3_uploads_exist(
        self, ms_client, ms_session
    ):
        from app.core.security import get_current_user_payload
        from app.main import app

        cognito_sub = "ms-pending-eq3"
        user_id = await _create_user(ms_session, cognito_sub, "eq3@test.com")
        for _ in range(3):
            await _create_upload_and_job(ms_session, user_id)
        await ms_session.commit()

        app.dependency_overrides[get_current_user_payload] = _auth_override(cognito_sub)
        try:
            resp = await ms_client.get("/api/v1/milestone-feedback/pending")
            assert resp.status_code == 200
            data = resp.json()
            assert len(data["cards"]) == 1
            assert data["cards"][0]["cardType"] == "milestone_3rd_upload"
            assert data["cards"][0]["variant"] == "emoji_rating"
        finally:
            app.dependency_overrides.pop(get_current_user_payload, None)

    @pytest.mark.asyncio
    async def test_no_card_when_already_responded(self, ms_client, ms_session):
        from app.core.security import get_current_user_payload
        from app.main import app

        cognito_sub = "ms-pending-answered"
        user_id = await _create_user(ms_session, cognito_sub, "ans@test.com")
        for _ in range(3):
            await _create_upload_and_job(ms_session, user_id)
        # Response was stored > 30d ago so frequency cap doesn't block;
        # the type-suppression path is what we're exercising.
        old = datetime.now(UTC) - timedelta(days=60)
        await _create_response(
            ms_session, user_id, "milestone_3rd_upload", "happy", created_at=old
        )
        await ms_session.commit()

        app.dependency_overrides[get_current_user_payload] = _auth_override(cognito_sub)
        try:
            resp = await ms_client.get("/api/v1/milestone-feedback/pending")
            assert resp.status_code == 200
            assert resp.json() == {"cards": []}
        finally:
            app.dependency_overrides.pop(get_current_user_payload, None)

    @pytest.mark.asyncio
    async def test_returns_health_score_card_when_delta_gte_5(
        self, ms_client, ms_session
    ):
        from app.core.security import get_current_user_payload
        from app.main import app

        cognito_sub = "ms-hsc-delta"
        user_id = await _create_user(ms_session, cognito_sub, "hsd@test.com")
        now = datetime.now(UTC).replace(tzinfo=None)
        await _create_health_score(ms_session, user_id, 70, now - timedelta(days=7))
        await _create_health_score(ms_session, user_id, 77, now)
        await ms_session.commit()

        app.dependency_overrides[get_current_user_payload] = _auth_override(cognito_sub)
        try:
            resp = await ms_client.get("/api/v1/milestone-feedback/pending")
            assert resp.status_code == 200
            data = resp.json()
            assert len(data["cards"]) == 1
            assert data["cards"][0]["cardType"] == "health_score_change"
            assert data["cards"][0]["variant"] == "yes_no"
        finally:
            app.dependency_overrides.pop(get_current_user_payload, None)

    @pytest.mark.asyncio
    async def test_no_health_score_card_when_delta_lt_5(self, ms_client, ms_session):
        from app.core.security import get_current_user_payload
        from app.main import app

        cognito_sub = "ms-hsc-small"
        user_id = await _create_user(ms_session, cognito_sub, "hss@test.com")
        now = datetime.now(UTC).replace(tzinfo=None)
        await _create_health_score(ms_session, user_id, 70, now - timedelta(days=7))
        await _create_health_score(ms_session, user_id, 73, now)
        await ms_session.commit()

        app.dependency_overrides[get_current_user_payload] = _auth_override(cognito_sub)
        try:
            resp = await ms_client.get("/api/v1/milestone-feedback/pending")
            assert resp.status_code == 200
            assert resp.json() == {"cards": []}
        finally:
            app.dependency_overrides.pop(get_current_user_payload, None)

    @pytest.mark.asyncio
    async def test_monthly_cap_suppresses_card(self, ms_client, ms_session):
        from app.core.security import get_current_user_payload
        from app.main import app

        cognito_sub = "ms-cap"
        user_id = await _create_user(ms_session, cognito_sub, "cap@test.com")
        # Eligible for 3rd-upload trigger
        for _ in range(3):
            await _create_upload_and_job(ms_session, user_id)
        # But a different response was stored 5 days ago — cap applies
        recent = datetime.now(UTC) - timedelta(days=5)
        await _create_response(
            ms_session,
            user_id,
            "health_score_change",
            "yes",
            created_at=recent,
        )
        await ms_session.commit()

        app.dependency_overrides[get_current_user_payload] = _auth_override(cognito_sub)
        try:
            resp = await ms_client.get("/api/v1/milestone-feedback/pending")
            assert resp.status_code == 200
            assert resp.json() == {"cards": []}
        finally:
            app.dependency_overrides.pop(get_current_user_payload, None)

    @pytest.mark.asyncio
    async def test_priority_3rd_upload_over_health_score(
        self, ms_client, ms_session
    ):
        from app.core.security import get_current_user_payload
        from app.main import app

        cognito_sub = "ms-priority"
        user_id = await _create_user(ms_session, cognito_sub, "prio@test.com")
        for _ in range(3):
            await _create_upload_and_job(ms_session, user_id)
        now = datetime.now(UTC).replace(tzinfo=None)
        await _create_health_score(ms_session, user_id, 60, now - timedelta(days=7))
        await _create_health_score(ms_session, user_id, 80, now)
        await ms_session.commit()

        app.dependency_overrides[get_current_user_payload] = _auth_override(cognito_sub)
        try:
            resp = await ms_client.get("/api/v1/milestone-feedback/pending")
            data = resp.json()
            assert len(data["cards"]) == 1
            assert data["cards"][0]["cardType"] == "milestone_3rd_upload"
        finally:
            app.dependency_overrides.pop(get_current_user_payload, None)

    @pytest.mark.asyncio
    async def test_requires_auth(self, ms_client):
        resp = await ms_client.get("/api/v1/milestone-feedback/pending")
        assert resp.status_code == 401


class TestPostMilestoneResponse:
    """Tests for POST /api/v1/milestone-feedback/respond."""

    @pytest.mark.asyncio
    async def test_saves_response_with_emoji_value(self, ms_client, ms_session):
        from app.core.security import get_current_user_payload
        from app.main import app
        from sqlmodel import select

        cognito_sub = "ms-save-emoji"
        user_id = await _create_user(ms_session, cognito_sub, "emo@test.com")
        await ms_session.commit()

        app.dependency_overrides[get_current_user_payload] = _auth_override(cognito_sub)
        try:
            resp = await ms_client.post(
                "/api/v1/milestone-feedback/respond",
                json={
                    "cardType": "milestone_3rd_upload",
                    "responseValue": "happy",
                },
            )
            assert resp.status_code == 200
            assert resp.json() == {"ok": True}
        finally:
            app.dependency_overrides.pop(get_current_user_payload, None)

        # Verify persisted row
        async with SQLModelAsyncSession(ms_session.bind) as verify_session:
            rows = (
                await verify_session.exec(
                    select(FeedbackResponse).where(
                        FeedbackResponse.user_id == user_id
                    )
                )
            ).all()
            assert len(rows) == 1
            assert rows[0].feedback_card_type == "milestone_3rd_upload"
            assert rows[0].response_value == "happy"

    @pytest.mark.asyncio
    async def test_saves_response_with_free_text(self, ms_client, ms_session):
        from app.core.security import get_current_user_payload
        from app.main import app
        from sqlmodel import select

        cognito_sub = "ms-save-text"
        user_id = await _create_user(ms_session, cognito_sub, "txt@test.com")
        await ms_session.commit()

        app.dependency_overrides[get_current_user_payload] = _auth_override(cognito_sub)
        try:
            resp = await ms_client.post(
                "/api/v1/milestone-feedback/respond",
                json={
                    "cardType": "health_score_change",
                    "responseValue": "yes",
                    "freeText": "Good app",
                },
            )
            assert resp.status_code == 200
        finally:
            app.dependency_overrides.pop(get_current_user_payload, None)

        async with SQLModelAsyncSession(ms_session.bind) as verify_session:
            row = (
                await verify_session.exec(
                    select(FeedbackResponse).where(
                        FeedbackResponse.user_id == user_id
                    )
                )
            ).one()
            assert row.free_text == "Good app"

    @pytest.mark.asyncio
    async def test_idempotent_second_response(self, ms_client, ms_session):
        """Unique-constraint duplicate is caught and the first response wins (AC #4)."""
        from app.core.security import get_current_user_payload
        from app.main import app
        from sqlmodel import select

        cognito_sub = "ms-idemp"
        user_id = await _create_user(ms_session, cognito_sub, "idm@test.com")
        await ms_session.commit()

        app.dependency_overrides[get_current_user_payload] = _auth_override(cognito_sub)
        try:
            first = await ms_client.post(
                "/api/v1/milestone-feedback/respond",
                json={
                    "cardType": "milestone_3rd_upload",
                    "responseValue": "happy",
                },
            )
            second = await ms_client.post(
                "/api/v1/milestone-feedback/respond",
                json={
                    "cardType": "milestone_3rd_upload",
                    "responseValue": "sad",
                },
            )
            assert first.status_code == 200
            assert second.status_code == 200
        finally:
            app.dependency_overrides.pop(get_current_user_payload, None)

        # "Never again" guarantee: the stored row must be the FIRST response
        # ("happy"), not overwritten by the duplicate "sad" POST.
        async with SQLModelAsyncSession(ms_session.bind) as verify_session:
            rows = (
                await verify_session.exec(
                    select(FeedbackResponse).where(
                        FeedbackResponse.user_id == user_id
                    )
                )
            ).all()
            assert len(rows) == 1
            assert rows[0].response_value == "happy"

    @pytest.mark.asyncio
    async def test_rejects_unknown_card_type(self, ms_client, ms_session):
        from app.core.security import get_current_user_payload
        from app.main import app

        cognito_sub = "ms-badtype"
        await _create_user(ms_session, cognito_sub, "bad@test.com")
        await ms_session.commit()

        app.dependency_overrides[get_current_user_payload] = _auth_override(cognito_sub)
        try:
            resp = await ms_client.post(
                "/api/v1/milestone-feedback/respond",
                json={
                    "cardType": "invalid",
                    "responseValue": "happy",
                },
            )
            assert resp.status_code == 422
        finally:
            app.dependency_overrides.pop(get_current_user_payload, None)

    @pytest.mark.asyncio
    async def test_requires_auth(self, ms_client):
        resp = await ms_client.post(
            "/api/v1/milestone-feedback/respond",
            json={"cardType": "milestone_3rd_upload", "responseValue": "happy"},
        )
        assert resp.status_code == 401
