"""Tests for POST/GET /api/v1/feedback/cards/... endpoints (Story 7.2)."""
import os
import tempfile
import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession as SQLModelAsyncSession
from unittest.mock import AsyncMock, MagicMock

from app.models.insight import Insight
from app.models.user import User


@pytest_asyncio.fixture
async def vote_engine():
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
async def vote_session(vote_engine) -> SQLModelAsyncSession:
    async with SQLModelAsyncSession(vote_engine) as session:
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
async def vote_client(vote_engine):
    from app.api.deps import get_cognito_service, get_db, get_rate_limiter
    from app.main import app

    async def override_get_db():
        async with SQLModelAsyncSession(vote_engine) as session:
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


class TestSubmitVoteEndpoint:
    """Tests for POST /api/v1/feedback/cards/{cardId}/vote."""

    @pytest.mark.asyncio
    async def test_submit_vote_returns_201(self, vote_client, vote_session):
        from app.core.security import get_current_user_payload
        from app.main import app

        cognito_sub = "vote-201-sub"
        user_id = await _create_user(vote_session, cognito_sub, "v201@test.com")
        card_id = await _create_insight(vote_session, user_id)
        await vote_session.commit()

        app.dependency_overrides[get_current_user_payload] = _auth_override(cognito_sub)
        try:
            resp = await vote_client.post(
                f"/api/v1/feedback/cards/{card_id}/vote",
                json={"vote": "up"},
            )
            assert resp.status_code == 201
            data = resp.json()
            assert data["vote"] == "up"
            assert data["cardId"] == str(card_id)
            assert "id" in data
            assert "createdAt" in data
        finally:
            app.dependency_overrides.pop(get_current_user_payload, None)

    @pytest.mark.asyncio
    async def test_submit_vote_rejects_invalid_vote(self, vote_client, vote_session):
        from app.core.security import get_current_user_payload
        from app.main import app

        cognito_sub = "vote-invalid-sub"
        user_id = await _create_user(vote_session, cognito_sub, "vinv@test.com")
        card_id = await _create_insight(vote_session, user_id)
        await vote_session.commit()

        app.dependency_overrides[get_current_user_payload] = _auth_override(cognito_sub)
        try:
            resp = await vote_client.post(
                f"/api/v1/feedback/cards/{card_id}/vote",
                json={"vote": "maybe"},
            )
            assert resp.status_code == 422
        finally:
            app.dependency_overrides.pop(get_current_user_payload, None)

    @pytest.mark.asyncio
    async def test_submit_vote_requires_auth(self, vote_client):
        """Missing auth → 401/403."""
        resp = await vote_client.post(
            f"/api/v1/feedback/cards/{uuid.uuid4()}/vote",
            json={"vote": "up"},
        )
        assert resp.status_code in (401, 403)

    @pytest.mark.asyncio
    async def test_submit_vote_unknown_card_returns_404(
        self, vote_client, vote_session
    ):
        """Voting on a card that doesn't exist returns 404."""
        from app.core.security import get_current_user_payload
        from app.main import app

        cognito_sub = "vote-404-card-sub"
        await _create_user(vote_session, cognito_sub, "v404card@test.com")
        await vote_session.commit()

        app.dependency_overrides[get_current_user_payload] = _auth_override(cognito_sub)
        try:
            resp = await vote_client.post(
                f"/api/v1/feedback/cards/{uuid.uuid4()}/vote",
                json={"vote": "up"},
            )
            assert resp.status_code == 404
        finally:
            app.dependency_overrides.pop(get_current_user_payload, None)

    @pytest.mark.asyncio
    async def test_submit_vote_rate_limited(self, vote_engine, vote_session):
        """Rate-limited POST returns 429 and invokes check_feedback_rate_limit."""
        from app.api.deps import get_cognito_service, get_db, get_rate_limiter
        from app.core.exceptions import ValidationError
        from app.core.security import get_current_user_payload
        from app.main import app

        cognito_sub = "vote-429-sub"
        user_id = await _create_user(vote_session, cognito_sub, "v429@test.com")
        await _create_insight(vote_session, user_id)
        await vote_session.commit()

        async def override_get_db():
            async with SQLModelAsyncSession(vote_engine) as session:
                yield session

        mock_rate = AsyncMock()
        mock_rate.check_feedback_rate_limit.side_effect = ValidationError(
            code="RATE_LIMITED",
            message="Too many.",
            status_code=429,
        )

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_cognito_service] = lambda: MagicMock()
        app.dependency_overrides[get_rate_limiter] = lambda: mock_rate
        app.dependency_overrides[get_current_user_payload] = _auth_override(cognito_sub)

        transport = ASGITransport(app=app)
        try:
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                resp = await ac.post(
                    f"/api/v1/feedback/cards/{uuid.uuid4()}/vote",
                    json={"vote": "up"},
                )
            assert resp.status_code == 429
            mock_rate.check_feedback_rate_limit.assert_awaited_once_with(str(user_id))
        finally:
            app.dependency_overrides.clear()


class TestGetCardFeedbackEndpoint:
    """Tests for GET /api/v1/feedback/cards/{cardId}."""

    @pytest.mark.asyncio
    async def test_get_feedback_returns_vote(self, vote_client, vote_session):
        from app.core.security import get_current_user_payload
        from app.main import app

        cognito_sub = "vote-get-sub"
        user_id = await _create_user(vote_session, cognito_sub, "vget@test.com")
        card_id = await _create_insight(vote_session, user_id)
        await vote_session.commit()

        app.dependency_overrides[get_current_user_payload] = _auth_override(cognito_sub)
        try:
            # First submit a vote
            post_resp = await vote_client.post(
                f"/api/v1/feedback/cards/{card_id}/vote",
                json={"vote": "down"},
            )
            feedback_id = post_resp.json()["id"]
            # Then retrieve it
            resp = await vote_client.get(f"/api/v1/feedback/cards/{card_id}")
            assert resp.status_code == 200
            data = resp.json()
            assert data["vote"] == "down"
            assert data["reasonChip"] is None
            assert data["id"] == feedback_id
            assert "createdAt" in data
        finally:
            app.dependency_overrides.pop(get_current_user_payload, None)

    @pytest.mark.asyncio
    async def test_get_feedback_returns_404_when_absent(self, vote_client, vote_session):
        from app.core.security import get_current_user_payload
        from app.main import app

        cognito_sub = "vote-404-sub"
        await _create_user(vote_session, cognito_sub, "v404@test.com")
        await vote_session.commit()

        app.dependency_overrides[get_current_user_payload] = _auth_override(cognito_sub)
        try:
            resp = await vote_client.get(f"/api/v1/feedback/cards/{uuid.uuid4()}")
            assert resp.status_code == 404
        finally:
            app.dependency_overrides.pop(get_current_user_payload, None)

    @pytest.mark.asyncio
    async def test_get_feedback_requires_auth(self, vote_client):
        resp = await vote_client.get(f"/api/v1/feedback/cards/{uuid.uuid4()}")
        assert resp.status_code in (401, 403)


# ==================== Issue Report Endpoint Tests (Story 7.3) ====================


class TestSubmitIssueReportEndpoint:
    """Tests for POST /api/v1/feedback/cards/{cardId}/report."""

    @pytest.mark.asyncio
    async def test_submit_report_returns_201(self, vote_client, vote_session):
        from app.core.security import get_current_user_payload
        from app.main import app

        cognito_sub = "report-201-sub"
        user_id = await _create_user(vote_session, cognito_sub, "r201@test.com")
        card_id = await _create_insight(vote_session, user_id)
        await vote_session.commit()

        app.dependency_overrides[get_current_user_payload] = _auth_override(cognito_sub)
        try:
            resp = await vote_client.post(
                f"/api/v1/feedback/cards/{card_id}/report",
                json={
                    "issueCategory": "incorrect_info",
                    "freeText": "Amount seems wrong",
                },
            )
            assert resp.status_code == 201
            data = resp.json()
            assert data["issueCategory"] == "incorrect_info"
            assert data["cardId"] == str(card_id)
            assert "id" in data
        finally:
            app.dependency_overrides.pop(get_current_user_payload, None)

    @pytest.mark.asyncio
    async def test_submit_report_accepts_without_free_text(
        self, vote_client, vote_session
    ):
        """freeText is optional — category alone is sufficient."""
        from app.core.security import get_current_user_payload
        from app.main import app

        cognito_sub = "report-nofree-sub"
        user_id = await _create_user(vote_session, cognito_sub, "rnofree@test.com")
        card_id = await _create_insight(vote_session, user_id)
        await vote_session.commit()

        app.dependency_overrides[get_current_user_payload] = _auth_override(cognito_sub)
        try:
            resp = await vote_client.post(
                f"/api/v1/feedback/cards/{card_id}/report",
                json={"issueCategory": "bug"},
            )
            assert resp.status_code == 201
        finally:
            app.dependency_overrides.pop(get_current_user_payload, None)

    @pytest.mark.asyncio
    async def test_submit_report_duplicate_returns_409(
        self, vote_client, vote_session
    ):
        """AC #4: second report on the same card returns 409 already_reported."""
        from app.core.security import get_current_user_payload
        from app.main import app

        cognito_sub = "report-409-sub"
        user_id = await _create_user(vote_session, cognito_sub, "r409@test.com")
        card_id = await _create_insight(vote_session, user_id)
        await vote_session.commit()

        app.dependency_overrides[get_current_user_payload] = _auth_override(cognito_sub)
        try:
            first = await vote_client.post(
                f"/api/v1/feedback/cards/{card_id}/report",
                json={"issueCategory": "bug"},
            )
            assert first.status_code == 201

            second = await vote_client.post(
                f"/api/v1/feedback/cards/{card_id}/report",
                json={"issueCategory": "other"},
            )
            assert second.status_code == 409
            assert second.json()["detail"] == "already_reported"
        finally:
            app.dependency_overrides.pop(get_current_user_payload, None)

    @pytest.mark.asyncio
    async def test_submit_report_requires_auth(self, vote_client):
        resp = await vote_client.post(
            f"/api/v1/feedback/cards/{uuid.uuid4()}/report",
            json={"issueCategory": "bug"},
        )
        assert resp.status_code in (401, 403)

    @pytest.mark.asyncio
    async def test_submit_report_unknown_card_returns_404(
        self, vote_client, vote_session
    ):
        from app.core.security import get_current_user_payload
        from app.main import app

        cognito_sub = "report-404-sub"
        await _create_user(vote_session, cognito_sub, "r404@test.com")
        await vote_session.commit()

        app.dependency_overrides[get_current_user_payload] = _auth_override(cognito_sub)
        try:
            resp = await vote_client.post(
                f"/api/v1/feedback/cards/{uuid.uuid4()}/report",
                json={"issueCategory": "bug"},
            )
            assert resp.status_code == 404
        finally:
            app.dependency_overrides.pop(get_current_user_payload, None)

    @pytest.mark.asyncio
    async def test_submit_report_rejects_invalid_category(
        self, vote_client, vote_session
    ):
        from app.core.security import get_current_user_payload
        from app.main import app

        cognito_sub = "report-422-sub"
        user_id = await _create_user(vote_session, cognito_sub, "r422@test.com")
        card_id = await _create_insight(vote_session, user_id)
        await vote_session.commit()

        app.dependency_overrides[get_current_user_payload] = _auth_override(cognito_sub)
        try:
            resp = await vote_client.post(
                f"/api/v1/feedback/cards/{card_id}/report",
                json={"issueCategory": "spam"},
            )
            assert resp.status_code == 422
        finally:
            app.dependency_overrides.pop(get_current_user_payload, None)

    @pytest.mark.asyncio
    async def test_submit_report_rejects_oversized_free_text(
        self, vote_client, vote_session
    ):
        """freeText capped at 500 chars → 422."""
        from app.core.security import get_current_user_payload
        from app.main import app

        cognito_sub = "report-long-sub"
        user_id = await _create_user(vote_session, cognito_sub, "rlong@test.com")
        card_id = await _create_insight(vote_session, user_id)
        await vote_session.commit()

        app.dependency_overrides[get_current_user_payload] = _auth_override(cognito_sub)
        try:
            resp = await vote_client.post(
                f"/api/v1/feedback/cards/{card_id}/report",
                json={"issueCategory": "bug", "freeText": "x" * 501},
            )
            assert resp.status_code == 422
        finally:
            app.dependency_overrides.pop(get_current_user_payload, None)

    @pytest.mark.asyncio
    async def test_submit_report_rate_limited(self, vote_engine, vote_session):
        from app.api.deps import get_cognito_service, get_db, get_rate_limiter
        from app.core.exceptions import ValidationError
        from app.core.security import get_current_user_payload
        from app.main import app

        cognito_sub = "report-429-sub"
        user_id = await _create_user(vote_session, cognito_sub, "r429@test.com")
        await _create_insight(vote_session, user_id)
        await vote_session.commit()

        async def override_get_db():
            async with SQLModelAsyncSession(vote_engine) as session:
                yield session

        mock_rate = AsyncMock()
        mock_rate.check_feedback_rate_limit.side_effect = ValidationError(
            code="RATE_LIMITED",
            message="Too many.",
            status_code=429,
        )

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_cognito_service] = lambda: MagicMock()
        app.dependency_overrides[get_rate_limiter] = lambda: mock_rate
        app.dependency_overrides[get_current_user_payload] = _auth_override(cognito_sub)

        transport = ASGITransport(app=app)
        try:
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                resp = await ac.post(
                    f"/api/v1/feedback/cards/{uuid.uuid4()}/report",
                    json={"issueCategory": "bug"},
                )
            assert resp.status_code == 429
            mock_rate.check_feedback_rate_limit.assert_awaited_once_with(str(user_id))
        finally:
            app.dependency_overrides.clear()


# ==================== Reason Chip PATCH Endpoint Tests (Story 7.5) ====================


class TestPatchReasonChipEndpoint:
    """Tests for PATCH /api/v1/feedback/{feedbackId}."""

    @pytest.mark.asyncio
    async def test_patch_reason_chip_returns_200(self, vote_client, vote_session):
        from app.core.security import get_current_user_payload
        from app.main import app

        cognito_sub = "chip-200-sub"
        user_id = await _create_user(vote_session, cognito_sub, "chip200@test.com")
        card_id = await _create_insight(vote_session, user_id)
        await vote_session.commit()

        app.dependency_overrides[get_current_user_payload] = _auth_override(cognito_sub)
        try:
            vote_resp = await vote_client.post(
                f"/api/v1/feedback/cards/{card_id}/vote",
                json={"vote": "down"},
            )
            assert vote_resp.status_code == 201
            feedback_id = vote_resp.json()["id"]

            resp = await vote_client.patch(
                f"/api/v1/feedback/{feedback_id}",
                json={"reasonChip": "not_relevant"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["reasonChip"] == "not_relevant"
            assert data["id"] == feedback_id
        finally:
            app.dependency_overrides.pop(get_current_user_payload, None)

    @pytest.mark.asyncio
    async def test_patch_reason_chip_returns_404_when_absent(
        self, vote_client, vote_session
    ):
        from app.core.security import get_current_user_payload
        from app.main import app

        cognito_sub = "chip-404-sub"
        await _create_user(vote_session, cognito_sub, "chip404@test.com")
        await vote_session.commit()

        app.dependency_overrides[get_current_user_payload] = _auth_override(cognito_sub)
        try:
            resp = await vote_client.patch(
                f"/api/v1/feedback/{uuid.uuid4()}",
                json={"reasonChip": "not_relevant"},
            )
            assert resp.status_code == 404
        finally:
            app.dependency_overrides.pop(get_current_user_payload, None)

    @pytest.mark.asyncio
    async def test_patch_reason_chip_rejects_invalid_chip(
        self, vote_client, vote_session
    ):
        from app.core.security import get_current_user_payload
        from app.main import app

        cognito_sub = "chip-422-sub"
        user_id = await _create_user(vote_session, cognito_sub, "chip422@test.com")
        card_id = await _create_insight(vote_session, user_id)
        await vote_session.commit()

        app.dependency_overrides[get_current_user_payload] = _auth_override(cognito_sub)
        try:
            vote_resp = await vote_client.post(
                f"/api/v1/feedback/cards/{card_id}/vote",
                json={"vote": "down"},
            )
            feedback_id = vote_resp.json()["id"]

            resp = await vote_client.patch(
                f"/api/v1/feedback/{feedback_id}",
                json={"reasonChip": "wrong_chip"},
            )
            assert resp.status_code == 422
        finally:
            app.dependency_overrides.pop(get_current_user_payload, None)

    @pytest.mark.asyncio
    async def test_patch_reason_chip_requires_auth(self, vote_client):
        resp = await vote_client.patch(
            f"/api/v1/feedback/{uuid.uuid4()}",
            json={"reasonChip": "not_relevant"},
        )
        assert resp.status_code in (401, 403)

    @pytest.mark.asyncio
    async def test_patch_reason_chip_cannot_access_other_users_record(
        self, vote_client, vote_session
    ):
        """Ownership check: user B PATCHing user A's feedback_id → 404."""
        from app.core.security import get_current_user_payload
        from app.main import app

        sub_a = "chip-owner-a"
        sub_b = "chip-owner-b"
        user_a_id = await _create_user(vote_session, sub_a, "chipa@test.com")
        await _create_user(vote_session, sub_b, "chipb@test.com")
        card_id = await _create_insight(vote_session, user_a_id)
        await vote_session.commit()

        app.dependency_overrides[get_current_user_payload] = _auth_override(sub_a)
        try:
            vote_resp = await vote_client.post(
                f"/api/v1/feedback/cards/{card_id}/vote",
                json={"vote": "down"},
            )
            feedback_id = vote_resp.json()["id"]
        finally:
            app.dependency_overrides.pop(get_current_user_payload, None)

        app.dependency_overrides[get_current_user_payload] = _auth_override(sub_b)
        try:
            resp = await vote_client.patch(
                f"/api/v1/feedback/{feedback_id}",
                json={"reasonChip": "already_knew"},
            )
            assert resp.status_code == 404
        finally:
            app.dependency_overrides.pop(get_current_user_payload, None)

    @pytest.mark.asyncio
    async def test_patch_reason_chip_rate_limited(self, vote_engine, vote_session):
        """Rate-limited PATCH returns 429 and invokes check_feedback_rate_limit."""
        from app.api.deps import get_cognito_service, get_db, get_rate_limiter
        from app.core.exceptions import ValidationError
        from app.core.security import get_current_user_payload
        from app.main import app

        cognito_sub = "chip-429-sub"
        user_id = await _create_user(vote_session, cognito_sub, "chip429@test.com")
        await vote_session.commit()

        async def override_get_db():
            async with SQLModelAsyncSession(vote_engine) as session:
                yield session

        mock_rate = AsyncMock()
        mock_rate.check_feedback_rate_limit.side_effect = ValidationError(
            code="RATE_LIMITED",
            message="Too many.",
            status_code=429,
        )

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_cognito_service] = lambda: MagicMock()
        app.dependency_overrides[get_rate_limiter] = lambda: mock_rate
        app.dependency_overrides[get_current_user_payload] = _auth_override(cognito_sub)

        transport = ASGITransport(app=app)
        try:
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                resp = await ac.patch(
                    f"/api/v1/feedback/{uuid.uuid4()}",
                    json={"reasonChip": "not_relevant"},
                )
            assert resp.status_code == 429
            mock_rate.check_feedback_rate_limit.assert_awaited_once_with(str(user_id))
        finally:
            app.dependency_overrides.clear()
