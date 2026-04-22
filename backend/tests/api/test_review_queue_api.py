"""Review queue API tests (Story 11.8 AC #11 item 3).

Covers auth (401 without token), cross-user isolation (404 not 403), matrix
violation (400), happy paths (200 with camelCase), pagination cursor
roundtrip, and the /count endpoint.
"""
from __future__ import annotations

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

import app.models  # noqa: F401
from app.models.transaction import Transaction
from app.models.uncategorized_review_queue import UncategorizedReviewQueue
from app.models.upload import Upload
from app.models.user import User


@pytest_asyncio.fixture
async def rq_engine():
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
async def rq_session(rq_engine):
    async with SQLModelAsyncSession(rq_engine) as session:
        yield session


def _auth_override(cognito_sub: str):
    async def mock_payload():
        return {"sub": cognito_sub}
    return mock_payload


@pytest_asyncio.fixture
async def rq_client(rq_engine):
    from app.api.deps import get_cognito_service, get_db, get_rate_limiter
    from app.main import app

    async def override_get_db():
        async with SQLModelAsyncSession(rq_engine) as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_cognito_service] = lambda: MagicMock()
    mock_rate = AsyncMock()
    mock_rate.check_rate_limit.return_value = None
    mock_rate.check_upload_rate_limit.return_value = None
    app.dependency_overrides[get_rate_limiter] = lambda: mock_rate

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


async def _seed(session, cognito_sub: str, *, with_entry: bool = True, n: int = 1):
    user_id = uuid.uuid4()
    upload_id = uuid.uuid4()
    session.add(User(id=user_id, email=f"{uuid.uuid4()}@e.co", cognito_sub=cognito_sub))
    await session.flush()
    session.add(Upload(id=upload_id, user_id=user_id, file_name="t.csv", s3_key=f"{user_id}/t.csv", file_size=1, mime_type="text/csv"))
    await session.flush()

    entry_ids = []
    for i in range(n):
        txn_id = uuid.uuid4()
        session.add(Transaction(
            id=txn_id, user_id=user_id, upload_id=upload_id,
            date=datetime(2026, 4, 20 + i),
            description=f"merchant-{i}", amount=-1000 - i,
            currency_code=980, dedup_hash=f"h-{uuid.uuid4().hex}",
            category="uncategorized", transaction_kind="spending",
            confidence_score=0.45, is_flagged_for_review=True,
            uncategorized_reason="low_confidence",
        ))
        if with_entry:
            eid = uuid.uuid4()
            session.add(UncategorizedReviewQueue(
                id=eid, user_id=user_id, transaction_id=txn_id,
                categorization_confidence=0.45, suggested_category="shopping",
                suggested_kind="spending", status="pending",
            ))
            entry_ids.append(eid)
    await session.commit()
    return user_id, entry_ids


@pytest.mark.asyncio
async def test_list_requires_auth(rq_client):
    # No override — authentication dependency will reject.
    resp = await rq_client.get("/api/v1/transactions/review-queue")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_list_returns_pending_entries_with_camel_case(rq_client, rq_session):
    from app.core.security import get_current_user_payload
    from app.main import app

    sub = f"sub-{uuid.uuid4()}"
    await _seed(rq_session, sub, n=2)
    app.dependency_overrides[get_current_user_payload] = _auth_override(sub)
    try:
        resp = await rq_client.get("/api/v1/transactions/review-queue")
        assert resp.status_code == 200
        body = resp.json()
        assert body["hasMore"] is False
        assert len(body["items"]) == 2
        item = body["items"][0]
        # camelCase aliases
        for key in ("id", "transactionId", "suggestedCategory", "suggestedKind", "categorizationConfidence", "createdAt", "status"):
            assert key in item
        assert item["status"] == "pending"
    finally:
        app.dependency_overrides.pop(get_current_user_payload, None)


@pytest.mark.asyncio
async def test_count_endpoint(rq_client, rq_session):
    from app.core.security import get_current_user_payload
    from app.main import app

    sub = f"sub-{uuid.uuid4()}"
    await _seed(rq_session, sub, n=3)
    app.dependency_overrides[get_current_user_payload] = _auth_override(sub)
    try:
        resp = await rq_client.get("/api/v1/transactions/review-queue/count")
        assert resp.status_code == 200
        assert resp.json() == {"count": 3}
    finally:
        app.dependency_overrides.pop(get_current_user_payload, None)


@pytest.mark.asyncio
async def test_list_cross_user_isolation(rq_client, rq_session):
    from app.core.security import get_current_user_payload
    from app.main import app

    sub1, sub2 = f"sub-{uuid.uuid4()}", f"sub-{uuid.uuid4()}"
    await _seed(rq_session, sub1, n=2)
    await _seed(rq_session, sub2, n=1)

    app.dependency_overrides[get_current_user_payload] = _auth_override(sub1)
    try:
        resp = await rq_client.get("/api/v1/transactions/review-queue")
        assert resp.status_code == 200
        assert len(resp.json()["items"]) == 2
    finally:
        app.dependency_overrides.pop(get_current_user_payload, None)


@pytest.mark.asyncio
async def test_resolve_happy_path(rq_client, rq_session):
    from app.core.security import get_current_user_payload
    from app.main import app

    sub = f"sub-{uuid.uuid4()}"
    _, eids = await _seed(rq_session, sub, n=1)
    app.dependency_overrides[get_current_user_payload] = _auth_override(sub)
    try:
        resp = await rq_client.post(
            f"/api/v1/transactions/review-queue/{eids[0]}/resolve",
            json={"category": "groceries", "kind": "spending"},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["status"] == "resolved"
        assert body["resolvedCategory"] == "groceries"
        assert body["resolvedKind"] == "spending"
    finally:
        app.dependency_overrides.pop(get_current_user_payload, None)


@pytest.mark.asyncio
async def test_resolve_matrix_violation_is_400(rq_client, rq_session):
    from app.core.security import get_current_user_payload
    from app.main import app

    sub = f"sub-{uuid.uuid4()}"
    _, eids = await _seed(rq_session, sub, n=1)
    app.dependency_overrides[get_current_user_payload] = _auth_override(sub)
    try:
        resp = await rq_client.post(
            f"/api/v1/transactions/review-queue/{eids[0]}/resolve",
            json={"category": "groceries", "kind": "income"},
        )
        assert resp.status_code == 400
    finally:
        app.dependency_overrides.pop(get_current_user_payload, None)


@pytest.mark.asyncio
async def test_resolve_cross_user_is_404(rq_client, rq_session):
    from app.core.security import get_current_user_payload
    from app.main import app

    sub1, sub2 = f"sub-{uuid.uuid4()}", f"sub-{uuid.uuid4()}"
    _, eids = await _seed(rq_session, sub1, n=1)
    # Second user (no entries of their own).
    await _seed(rq_session, sub2, with_entry=False, n=0)
    app.dependency_overrides[get_current_user_payload] = _auth_override(sub2)
    try:
        resp = await rq_client.post(
            f"/api/v1/transactions/review-queue/{eids[0]}/resolve",
            json={"category": "groceries", "kind": "spending"},
        )
        assert resp.status_code == 404
    finally:
        app.dependency_overrides.pop(get_current_user_payload, None)


@pytest.mark.asyncio
async def test_dismiss_happy_path(rq_client, rq_session):
    from app.core.security import get_current_user_payload
    from app.main import app

    sub = f"sub-{uuid.uuid4()}"
    _, eids = await _seed(rq_session, sub, n=1)
    app.dependency_overrides[get_current_user_payload] = _auth_override(sub)
    try:
        resp = await rq_client.post(
            f"/api/v1/transactions/review-queue/{eids[0]}/dismiss",
            json={"reason": "not useful"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "dismissed"
    finally:
        app.dependency_overrides.pop(get_current_user_payload, None)


@pytest.mark.asyncio
async def test_pagination_cursor_roundtrips(rq_client, rq_session):
    from app.core.security import get_current_user_payload
    from app.main import app

    sub = f"sub-{uuid.uuid4()}"
    await _seed(rq_session, sub, n=3)
    app.dependency_overrides[get_current_user_payload] = _auth_override(sub)
    try:
        r1 = await rq_client.get("/api/v1/transactions/review-queue?limit=2")
        assert r1.status_code == 200
        b1 = r1.json()
        assert b1["hasMore"] is True
        assert b1["nextCursor"] is not None
        assert len(b1["items"]) == 2

        r2 = await rq_client.get(
            f"/api/v1/transactions/review-queue?limit=2&cursor={b1['nextCursor']}"
        )
        assert r2.status_code == 200
        b2 = r2.json()
        assert len(b2["items"]) == 1
        assert b2["hasMore"] is False

        seen = {i["id"] for i in b1["items"]} | {i["id"] for i in b2["items"]}
        assert len(seen) == 3
    finally:
        app.dependency_overrides.pop(get_current_user_payload, None)
