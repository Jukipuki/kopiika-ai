"""Tests for GET /api/v1/users/me/data-summary endpoint (Story 5.4)."""
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

from app.models.consent import UserConsent
from app.models.feedback import CardFeedback
from app.models.financial_health_score import FinancialHealthScore
from app.models.financial_profile import FinancialProfile
from app.models.insight import Insight
from app.models.transaction import Transaction
from app.models.upload import Upload
from app.models.user import User


# ==================== Fixtures ====================


@pytest_asyncio.fixture
async def ds_api_engine():
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
async def ds_api_session(ds_api_engine) -> SQLModelAsyncSession:
    async with SQLModelAsyncSession(ds_api_engine) as session:
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
async def ds_client(ds_api_engine):
    from app.api.deps import get_db, get_cognito_service, get_rate_limiter
    from app.main import app

    async def override_get_db():
        async with SQLModelAsyncSession(ds_api_engine) as session:
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


# ==================== Tests ====================


class TestDataSummaryEndpoint:
    """Test GET /api/v1/users/me/data-summary."""

    @pytest.mark.asyncio
    async def test_returns_correct_shape_with_data(self, ds_client, ds_api_session):
        """Returns 200 with full data summary when user has data."""
        from app.core.security import get_current_user_payload
        from app.main import app

        cognito_sub = "ds-full-sub"
        user_id = await _create_user(ds_api_session, cognito_sub, "ds@test.com")
        upload_id = uuid.uuid4()

        # Create upload
        ds_api_session.add(Upload(
            id=upload_id, user_id=user_id, file_name="test.csv",
            s3_key="s3/test.csv", file_size=1024, mime_type="text/csv",
        ))

        # Create transactions
        ds_api_session.add(Transaction(
            user_id=user_id, upload_id=upload_id, date=datetime(2026, 1, 15),
            description="Groceries", amount=-5000, dedup_hash="h1", category="groceries",
        ))
        ds_api_session.add(Transaction(
            user_id=user_id, upload_id=upload_id, date=datetime(2026, 3, 20),
            description="Transport", amount=-2000, dedup_hash="h2", category="transport",
        ))

        # Create two insights — capture ids before commit (post-commit attribute expiry).
        # Two cards needed because card_feedback has UNIQUE (user_id, card_id, feedback_source).
        insight_a = Insight(
            user_id=user_id, upload_id=upload_id, headline="Save more",
            key_metric="50%", why_it_matters="Important", deep_dive="Details",
            category="spending",
        )
        insight_b = Insight(
            user_id=user_id, upload_id=upload_id, headline="Review subscriptions",
            key_metric="10%", why_it_matters="Hidden cost", deep_dive="Details",
            category="spending",
        )
        ds_api_session.add(insight_a)
        ds_api_session.add(insight_b)
        await ds_api_session.flush()
        insight_a_id = insight_a.id
        insight_b_id = insight_b.id

        # Feedback rows: one up vote, one down vote with free_text, one issue report
        ds_api_session.add(CardFeedback(
            user_id=user_id, card_id=insight_a_id, card_type="spending",
            vote="up", feedback_source="card_vote",
        ))
        ds_api_session.add(CardFeedback(
            user_id=user_id, card_id=insight_b_id, card_type="spending",
            vote="down", free_text="Too complex", feedback_source="card_vote",
        ))
        ds_api_session.add(CardFeedback(
            user_id=user_id, card_id=insight_a_id, card_type="spending",
            feedback_source="issue_report", issue_category="confusing",
        ))

        # Create financial profile
        ds_api_session.add(FinancialProfile(
            user_id=user_id, total_income=100000, total_expenses=70000,
            category_totals={"groceries": 50000, "transport": 20000},
        ))

        # Create health scores
        ds_api_session.add(FinancialHealthScore(
            user_id=user_id, score=72,
            calculated_at=datetime(2026, 2, 1), breakdown={"savings_ratio": 80},
        ))
        ds_api_session.add(FinancialHealthScore(
            user_id=user_id, score=78,
            calculated_at=datetime(2026, 3, 1), breakdown={"savings_ratio": 85},
        ))

        # Create consent
        ds_api_session.add(UserConsent(
            user_id=user_id, consent_type="ai_processing", version="1",
            granted_at=datetime(2026, 1, 1), locale="en",
        ))

        await ds_api_session.commit()

        app.dependency_overrides[get_current_user_payload] = _auth_override(cognito_sub)
        try:
            response = await ds_client.get("/api/v1/users/me/data-summary")
            assert response.status_code == 200
            data = response.json()

            assert data["uploadCount"] == 1
            assert data["transactionCount"] == 2
            assert data["transactionDateRange"]["earliest"] == "2026-01-15T00:00:00"
            assert data["transactionDateRange"]["latest"] == "2026-03-20T00:00:00"
            assert sorted(data["categoriesDetected"]) == ["groceries", "transport"]
            assert data["insightCount"] == 2
            assert data["financialProfile"]["totalIncome"] == 100000
            assert data["financialProfile"]["totalExpenses"] == 70000
            assert len(data["healthScoreHistory"]) == 2
            assert data["healthScoreHistory"][0]["score"] == 72
            assert data["healthScoreHistory"][1]["score"] == 78
            assert len(data["consentRecords"]) == 1
            assert data["consentRecords"][0]["consentType"] == "ai_processing"

            # Feedback summary assertions (Story 7.4)
            assert data["feedbackSummary"]["voteCounts"]["up"] == 1
            assert data["feedbackSummary"]["voteCounts"]["down"] == 1
            assert data["feedbackSummary"]["issueReportCount"] == 1
            assert len(data["feedbackSummary"]["freeTextEntries"]) == 1
            assert data["feedbackSummary"]["freeTextEntries"][0]["freeText"] == "Too complex"
            assert data["feedbackSummary"]["freeTextEntries"][0]["feedbackSource"] == "card_vote"
            # AC #4: feedback_responses placeholder (table arrives in Story 7.7)
            assert data["feedbackSummary"]["feedbackResponses"] == []
        finally:
            app.dependency_overrides.pop(get_current_user_payload, None)

    @pytest.mark.asyncio
    async def test_empty_state(self, ds_client, ds_api_session):
        """New user with no data returns zero counts, null profile, empty arrays."""
        from app.core.security import get_current_user_payload
        from app.main import app

        cognito_sub = "ds-empty-sub"
        await _create_user(ds_api_session, cognito_sub, "empty@test.com")
        await ds_api_session.commit()

        app.dependency_overrides[get_current_user_payload] = _auth_override(cognito_sub)
        try:
            response = await ds_client.get("/api/v1/users/me/data-summary")
            assert response.status_code == 200
            data = response.json()

            assert data["uploadCount"] == 0
            assert data["transactionCount"] == 0
            assert data["transactionDateRange"] is None
            assert data["categoriesDetected"] == []
            assert data["insightCount"] == 0
            assert data["financialProfile"] is None
            assert data["healthScoreHistory"] == []
            assert data["consentRecords"] == []
            assert data["feedbackSummary"]["voteCounts"]["up"] == 0
            assert data["feedbackSummary"]["voteCounts"]["down"] == 0
            assert data["feedbackSummary"]["issueReportCount"] == 0
            assert data["feedbackSummary"]["freeTextEntries"] == []
            assert data["feedbackSummary"]["feedbackResponses"] == []
        finally:
            app.dependency_overrides.pop(get_current_user_payload, None)

    @pytest.mark.asyncio
    async def test_tenant_isolation(self, ds_client, ds_api_session):
        """User A cannot see user B's data summary."""
        from app.core.security import get_current_user_payload
        from app.main import app

        # Create user A with data
        user_a_id = await _create_user(ds_api_session, "ds-user-a", "a@test.com")
        upload_id = uuid.uuid4()
        ds_api_session.add(Upload(
            id=upload_id, user_id=user_a_id, file_name="a.csv",
            s3_key="s3/a.csv", file_size=512, mime_type="text/csv",
        ))
        ds_api_session.add(Transaction(
            user_id=user_a_id, upload_id=upload_id, date=datetime(2026, 2, 1),
            description="Food", amount=-3000, dedup_hash="ha1", category="groceries",
        ))
        ds_api_session.add(Insight(
            user_id=user_a_id, headline="A insight", key_metric="10%",
            why_it_matters="A", deep_dive="A", category="spending",
        ))

        # Create user B (no data)
        await _create_user(ds_api_session, "ds-user-b", "b@test.com")
        await ds_api_session.commit()

        # Query as user B
        app.dependency_overrides[get_current_user_payload] = _auth_override("ds-user-b")
        try:
            response = await ds_client.get("/api/v1/users/me/data-summary")
            assert response.status_code == 200
            data = response.json()

            # User B should see no data
            assert data["uploadCount"] == 0
            assert data["transactionCount"] == 0
            assert data["insightCount"] == 0
        finally:
            app.dependency_overrides.pop(get_current_user_payload, None)

    @pytest.mark.asyncio
    async def test_unauthenticated(self, ds_client):
        """Unauthenticated access returns 401/403."""
        response = await ds_client.get("/api/v1/users/me/data-summary")
        assert response.status_code in (401, 403)

    @pytest.mark.asyncio
    async def test_camel_case_keys(self, ds_client, ds_api_session):
        """Response uses camelCase keys throughout."""
        from app.core.security import get_current_user_payload
        from app.main import app

        cognito_sub = "ds-camel-sub"
        await _create_user(ds_api_session, cognito_sub, "camel@test.com")
        await ds_api_session.commit()

        app.dependency_overrides[get_current_user_payload] = _auth_override(cognito_sub)
        try:
            response = await ds_client.get("/api/v1/users/me/data-summary")
            data = response.json()

            # camelCase keys present
            assert "uploadCount" in data
            assert "transactionCount" in data
            assert "transactionDateRange" in data
            assert "categoriesDetected" in data
            assert "insightCount" in data
            assert "financialProfile" in data
            assert "healthScoreHistory" in data
            assert "consentRecords" in data
            assert "feedbackSummary" in data
            assert "voteCounts" in data["feedbackSummary"]
            assert "issueReportCount" in data["feedbackSummary"]
            assert "freeTextEntries" in data["feedbackSummary"]
            assert "feedbackResponses" in data["feedbackSummary"]

            # No snake_case keys
            assert "upload_count" not in data
            assert "transaction_count" not in data
            assert "insight_count" not in data
            assert "feedback_summary" not in data
        finally:
            app.dependency_overrides.pop(get_current_user_payload, None)
