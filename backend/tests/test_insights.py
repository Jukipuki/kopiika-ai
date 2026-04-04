"""Tests for insights API endpoint and service (Story 3.4)."""
import os
import tempfile
import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession as SQLModelAsyncSession

from app.models.insight import Insight
from app.models.upload import Upload
from app.models.user import User


def _utcnow():
    return datetime.now(UTC).replace(tzinfo=None)


# ==================== Fixtures ====================


@pytest_asyncio.fixture
async def insight_async_engine():
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
async def insight_async_session(insight_async_engine) -> SQLModelAsyncSession:
    async with SQLModelAsyncSession(insight_async_engine) as session:
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


async def _create_upload(session: SQLModelAsyncSession, user_id: uuid.UUID):
    upload_id = uuid.uuid4()
    upload = Upload(
        id=upload_id, user_id=user_id, file_name="test.csv",
        s3_key=f"{user_id}/test.csv", file_size=100,
        mime_type="text/csv", detected_format="monobank",
    )
    session.add(upload)
    await session.flush()
    return upload_id


async def _create_insight(
    session: SQLModelAsyncSession,
    user_id: uuid.UUID,
    upload_id: uuid.UUID | None = None,
    severity: str = "medium",
    category: str = "spending",
    headline: str = "Test insight",
    created_at: datetime | None = None,
):
    insight = Insight(
        user_id=user_id,
        upload_id=upload_id,
        headline=headline,
        key_metric="100 UAH",
        why_it_matters="Important reason",
        deep_dive="Detailed explanation",
        severity=severity,
        category=category,
        created_at=created_at or _utcnow(),
    )
    session.add(insight)
    await session.flush()
    return insight


@pytest_asyncio.fixture
async def insight_client(insight_async_engine):
    from app.api.deps import get_db, get_cognito_service, get_rate_limiter
    from app.main import app
    from unittest.mock import AsyncMock

    async def override_get_db():
        async with SQLModelAsyncSession(insight_async_engine) as session:
            yield session

    mock_cognito = MagicMock()
    mock_rate = AsyncMock()
    mock_rate.check_rate_limit.return_value = None
    mock_rate.check_upload_rate_limit.return_value = None

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_cognito_service] = lambda: mock_cognito
    app.dependency_overrides[get_rate_limiter] = lambda: mock_rate

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


# ==================== API Endpoint Tests ====================


class TestInsightsEndpoint:
    """Test GET /api/v1/insights."""

    @pytest.mark.asyncio
    async def test_empty_state(self, insight_client, insight_async_session):
        """Empty state returns correct empty response."""
        from app.core.security import get_current_user_payload
        from app.main import app

        cognito_sub = "insight-empty-sub"
        user_id = await _create_user(insight_async_session, cognito_sub, "empty@test.com")
        await insight_async_session.commit()

        app.dependency_overrides[get_current_user_payload] = _auth_override(cognito_sub)
        try:
            response = await insight_client.get("/api/v1/insights")
            assert response.status_code == 200
            data = response.json()
            assert data == {"items": [], "total": 0, "nextCursor": None, "hasMore": False}
        finally:
            app.dependency_overrides.pop(get_current_user_payload, None)

    @pytest.mark.asyncio
    async def test_severity_sort_order(self, insight_client, insight_async_session):
        """Insights sorted by severity: high -> medium -> low."""
        from app.core.security import get_current_user_payload
        from app.main import app

        cognito_sub = "insight-sort-sub"
        user_id = await _create_user(insight_async_session, cognito_sub, "sort@test.com")
        upload_id = await _create_upload(insight_async_session, user_id)

        # Create in reverse order to verify sorting
        await _create_insight(insight_async_session, user_id, upload_id, severity="low", headline="Low insight")
        await _create_insight(insight_async_session, user_id, upload_id, severity="high", headline="High insight")
        await _create_insight(insight_async_session, user_id, upload_id, severity="medium", headline="Medium insight")
        await insight_async_session.commit()

        app.dependency_overrides[get_current_user_payload] = _auth_override(cognito_sub)
        try:
            response = await insight_client.get("/api/v1/insights")
            assert response.status_code == 200
            data = response.json()
            assert data["total"] == 3
            severities = [item["severity"] for item in data["items"]]
            assert severities == ["high", "medium", "low"]
        finally:
            app.dependency_overrides.pop(get_current_user_payload, None)

    @pytest.mark.asyncio
    async def test_camel_case_keys(self, insight_client, insight_async_session):
        """Response uses camelCase keys."""
        from app.core.security import get_current_user_payload
        from app.main import app

        cognito_sub = "insight-camel-sub"
        user_id = await _create_user(insight_async_session, cognito_sub, "camel@test.com")
        upload_id = await _create_upload(insight_async_session, user_id)
        await _create_insight(insight_async_session, user_id, upload_id)
        await insight_async_session.commit()

        app.dependency_overrides[get_current_user_payload] = _auth_override(cognito_sub)
        try:
            response = await insight_client.get("/api/v1/insights")
            data = response.json()
            item = data["items"][0]
            assert "keyMetric" in item
            assert "whyItMatters" in item
            assert "deepDive" in item
            assert "uploadId" in item
            assert "createdAt" in item
            # Verify no snake_case keys
            assert "key_metric" not in item
            assert "why_it_matters" not in item
        finally:
            app.dependency_overrides.pop(get_current_user_payload, None)

    @pytest.mark.asyncio
    async def test_pagination(self, insight_client, insight_async_session):
        """Cursor-based pagination works correctly."""
        from app.core.security import get_current_user_payload
        from app.main import app

        cognito_sub = "insight-page-sub"
        user_id = await _create_user(insight_async_session, cognito_sub, "page@test.com")
        upload_id = await _create_upload(insight_async_session, user_id)

        # Create 5 medium insights with different timestamps
        for i in range(5):
            await _create_insight(
                insight_async_session, user_id, upload_id,
                headline=f"Insight {i}",
                created_at=datetime(2026, 1, 1, 0, 0, i),
            )
        await insight_async_session.commit()

        app.dependency_overrides[get_current_user_payload] = _auth_override(cognito_sub)
        try:
            # First page
            response = await insight_client.get("/api/v1/insights?pageSize=2")
            assert response.status_code == 200
            data = response.json()
            assert len(data["items"]) == 2
            assert data["hasMore"] is True
            assert data["nextCursor"] is not None
            assert data["total"] == 5

            # Second page
            response2 = await insight_client.get(f"/api/v1/insights?pageSize=2&cursor={data['nextCursor']}")
            data2 = response2.json()
            assert len(data2["items"]) == 2
            assert data2["hasMore"] is True

            # Third page
            response3 = await insight_client.get(f"/api/v1/insights?pageSize=2&cursor={data2['nextCursor']}")
            data3 = response3.json()
            assert len(data3["items"]) == 1
            assert data3["hasMore"] is False
        finally:
            app.dependency_overrides.pop(get_current_user_payload, None)

    @pytest.mark.asyncio
    async def test_cross_upload_aggregation(self, insight_client, insight_async_session):
        """Insights from multiple uploads appear in unified feed."""
        from app.core.security import get_current_user_payload
        from app.main import app

        cognito_sub = "insight-multi-sub"
        user_id = await _create_user(insight_async_session, cognito_sub, "multi@test.com")
        upload_id1 = await _create_upload(insight_async_session, user_id)
        upload_id2 = await _create_upload(insight_async_session, user_id)

        await _create_insight(insight_async_session, user_id, upload_id1, headline="Upload 1 insight")
        await _create_insight(insight_async_session, user_id, upload_id2, headline="Upload 2 insight")
        await insight_async_session.commit()

        app.dependency_overrides[get_current_user_payload] = _auth_override(cognito_sub)
        try:
            response = await insight_client.get("/api/v1/insights")
            data = response.json()
            assert data["total"] == 2
            assert len(data["items"]) == 2
        finally:
            app.dependency_overrides.pop(get_current_user_payload, None)

    @pytest.mark.asyncio
    async def test_created_at_iso8601_format(self, insight_client, insight_async_session):
        """AC #4: createdAt is ISO 8601 UTC with trailing Z."""
        from app.core.security import get_current_user_payload
        from app.main import app

        cognito_sub = "insight-date-sub"
        user_id = await _create_user(insight_async_session, cognito_sub, "date@test.com")
        upload_id = await _create_upload(insight_async_session, user_id)
        await _create_insight(
            insight_async_session, user_id, upload_id,
            created_at=datetime(2026, 3, 15, 10, 30, 0),
        )
        await insight_async_session.commit()

        app.dependency_overrides[get_current_user_payload] = _auth_override(cognito_sub)
        try:
            response = await insight_client.get("/api/v1/insights")
            data = response.json()
            created_at = data["items"][0]["createdAt"]
            assert created_at.endswith("Z")
            assert "+" not in created_at  # no double timezone
            assert created_at == "2026-03-15T10:30:00Z"
        finally:
            app.dependency_overrides.pop(get_current_user_payload, None)

    @pytest.mark.asyncio
    async def test_invalid_cursor_ignored(self, insight_client, insight_async_session):
        """Invalid (non-UUID) cursor is silently ignored, returns full results."""
        from app.core.security import get_current_user_payload
        from app.main import app

        cognito_sub = "insight-badcursor-sub"
        user_id = await _create_user(insight_async_session, cognito_sub, "badcursor@test.com")
        upload_id = await _create_upload(insight_async_session, user_id)
        await _create_insight(insight_async_session, user_id, upload_id)
        await insight_async_session.commit()

        app.dependency_overrides[get_current_user_payload] = _auth_override(cognito_sub)
        try:
            response = await insight_client.get("/api/v1/insights?cursor=not-a-uuid")
            assert response.status_code == 200
            data = response.json()
            assert data["total"] == 1
            assert len(data["items"]) == 1
        finally:
            app.dependency_overrides.pop(get_current_user_payload, None)

    @pytest.mark.asyncio
    async def test_unauthenticated(self, insight_client):
        """Unauthenticated access returns 401/403."""
        response = await insight_client.get("/api/v1/insights")
        assert response.status_code in (401, 403)

    @pytest.mark.asyncio
    async def test_tenant_isolation(self, insight_client, insight_async_session):
        """User A cannot see user B's insights."""
        from app.core.security import get_current_user_payload
        from app.main import app

        user_a_id = await _create_user(insight_async_session, "insight-a-sub", "a@test.com")
        user_b_id = await _create_user(insight_async_session, "insight-b-sub", "b@test.com")
        upload_a = await _create_upload(insight_async_session, user_a_id)
        upload_b = await _create_upload(insight_async_session, user_b_id)

        await _create_insight(insight_async_session, user_a_id, upload_a, headline="A's insight")
        await _create_insight(insight_async_session, user_b_id, upload_b, headline="B's insight")
        await insight_async_session.commit()

        # User A sees only their insight
        app.dependency_overrides[get_current_user_payload] = _auth_override("insight-a-sub")
        try:
            response = await insight_client.get("/api/v1/insights")
            data = response.json()
            assert data["total"] == 1
            assert data["items"][0]["headline"] == "A's insight"
        finally:
            app.dependency_overrides.pop(get_current_user_payload, None)

        # User B sees only their insight
        app.dependency_overrides[get_current_user_payload] = _auth_override("insight-b-sub")
        try:
            response = await insight_client.get("/api/v1/insights")
            data = response.json()
            assert data["total"] == 1
            assert data["items"][0]["headline"] == "B's insight"
        finally:
            app.dependency_overrides.pop(get_current_user_payload, None)


# ==================== Service Unit Tests ====================


class TestInsightService:
    """Unit tests for get_insights_for_user."""

    @pytest.mark.asyncio
    async def test_severity_sort_order(self, insight_async_session):
        """Verify severity sort: high -> medium -> low."""
        from app.services.insight_service import get_insights_for_user

        user_id = await _create_user(insight_async_session, "svc-sort-sub", "svc-sort@test.com")
        upload_id = await _create_upload(insight_async_session, user_id)

        await _create_insight(insight_async_session, user_id, upload_id, severity="low", headline="Low")
        await _create_insight(insight_async_session, user_id, upload_id, severity="high", headline="High")
        await _create_insight(insight_async_session, user_id, upload_id, severity="medium", headline="Med")
        await insight_async_session.commit()

        result = await get_insights_for_user(insight_async_session, user_id)
        assert result.total == 3
        severities = [i.severity for i in result.items]
        assert severities == ["high", "medium", "low"]

    @pytest.mark.asyncio
    async def test_cursor_seek(self, insight_async_session):
        """Cursor pagination seeks past the cursor row."""
        from app.services.insight_service import get_insights_for_user

        user_id = await _create_user(insight_async_session, "svc-cursor-sub", "svc-cursor@test.com")
        upload_id = await _create_upload(insight_async_session, user_id)

        insights = []
        for i in range(4):
            ins = await _create_insight(
                insight_async_session, user_id, upload_id,
                headline=f"Insight {i}", created_at=datetime(2026, 1, 1, 0, 0, i),
            )
            insights.append(ins)
        await insight_async_session.commit()

        # First page
        result1 = await get_insights_for_user(insight_async_session, user_id, page_size=2)
        assert len(result1.items) == 2
        assert result1.has_more is True

        # Second page using cursor
        result2 = await get_insights_for_user(
            insight_async_session, user_id, cursor=result1.next_cursor, page_size=2,
        )
        assert len(result2.items) == 2
        assert result2.has_more is False

        # No overlap between pages
        page1_ids = {str(i.id) for i in result1.items}
        page2_ids = {str(i.id) for i in result2.items}
        assert page1_ids.isdisjoint(page2_ids)

    @pytest.mark.asyncio
    async def test_cross_upload_aggregation(self, insight_async_session):
        """Insights from multiple uploads aggregated."""
        from app.services.insight_service import get_insights_for_user

        user_id = await _create_user(insight_async_session, "svc-multi-sub", "svc-multi@test.com")
        upload_id1 = await _create_upload(insight_async_session, user_id)
        upload_id2 = await _create_upload(insight_async_session, user_id)

        await _create_insight(insight_async_session, user_id, upload_id1)
        await _create_insight(insight_async_session, user_id, upload_id2)
        await insight_async_session.commit()

        result = await get_insights_for_user(insight_async_session, user_id)
        assert result.total == 2
        assert len(result.items) == 2

    @pytest.mark.asyncio
    async def test_cross_severity_cursor_pagination(self, insight_async_session):
        """Cursor pagination correctly crosses severity boundaries."""
        from app.services.insight_service import get_insights_for_user

        user_id = await _create_user(insight_async_session, "svc-xsev-sub", "svc-xsev@test.com")
        upload_id = await _create_upload(insight_async_session, user_id)

        # 2 high, 2 medium, 1 low — page_size=2 should cross severity boundary
        await _create_insight(insight_async_session, user_id, upload_id, severity="high", headline="H1",
                              created_at=datetime(2026, 1, 1, 0, 0, 2))
        await _create_insight(insight_async_session, user_id, upload_id, severity="high", headline="H2",
                              created_at=datetime(2026, 1, 1, 0, 0, 1))
        await _create_insight(insight_async_session, user_id, upload_id, severity="medium", headline="M1",
                              created_at=datetime(2026, 1, 1, 0, 0, 2))
        await _create_insight(insight_async_session, user_id, upload_id, severity="medium", headline="M2",
                              created_at=datetime(2026, 1, 1, 0, 0, 1))
        await _create_insight(insight_async_session, user_id, upload_id, severity="low", headline="L1",
                              created_at=datetime(2026, 1, 1, 0, 0, 0))
        await insight_async_session.commit()

        # Page 1: should be H1, H2 (both high, ordered by created_at DESC)
        r1 = await get_insights_for_user(insight_async_session, user_id, page_size=2)
        assert [i.headline for i in r1.items] == ["H1", "H2"]
        assert r1.has_more is True

        # Page 2: should cross into medium — M1, M2
        r2 = await get_insights_for_user(insight_async_session, user_id, cursor=r1.next_cursor, page_size=2)
        assert [i.headline for i in r2.items] == ["M1", "M2"]
        assert r2.has_more is True

        # Page 3: should be L1
        r3 = await get_insights_for_user(insight_async_session, user_id, cursor=r2.next_cursor, page_size=2)
        assert [i.headline for i in r3.items] == ["L1"]
        assert r3.has_more is False

    @pytest.mark.asyncio
    async def test_empty_result(self, insight_async_session):
        """No insights returns empty PaginatedResult."""
        from app.services.insight_service import get_insights_for_user

        user_id = await _create_user(insight_async_session, "svc-empty-sub", "svc-empty@test.com")
        await insight_async_session.commit()

        result = await get_insights_for_user(insight_async_session, user_id)
        assert result.total == 0
        assert result.items == []
        assert result.has_more is False
        assert result.next_cursor is None
