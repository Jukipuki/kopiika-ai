"""API tests for POST/GET /api/v1/users/me/consent (Story 5.2)."""

from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession as SQLModelAsyncSession

from app.api.deps import get_current_user
from app.core.consent import CONSENT_TYPE_AI_PROCESSING, CURRENT_CONSENT_VERSION
from app.main import app
from app.models.consent import UserConsent
from app.models.user import User


@pytest_asyncio.fixture
async def user_a(async_engine) -> User:
    user = User(
        cognito_sub=f"sub-a-{uuid.uuid4()}",
        email=f"a-{uuid.uuid4()}@example.com",
        is_verified=True,
    )
    async with SQLModelAsyncSession(async_engine) as session:
        session.add(user)
        await session.commit()
        await session.refresh(user)
    return user


@pytest_asyncio.fixture
async def user_b(async_engine) -> User:
    user = User(
        cognito_sub=f"sub-b-{uuid.uuid4()}",
        email=f"b-{uuid.uuid4()}@example.com",
        is_verified=True,
    )
    async with SQLModelAsyncSession(async_engine) as session:
        session.add(user)
        await session.commit()
        await session.refresh(user)
    return user


def _override_current_user(user: User) -> None:
    async def _get() -> User:
        return user

    app.dependency_overrides[get_current_user] = _get


def _clear_override() -> None:
    app.dependency_overrides.pop(get_current_user, None)


# ==================== Success path ====================


@pytest.mark.asyncio
async def test_post_consent_success(client, user_a):
    """10(a) POST /users/me/consent grants a new consent row and returns 201."""
    _override_current_user(user_a)
    try:
        response = await client.post(
            "/api/v1/users/me/consent",
            json={"version": CURRENT_CONSENT_VERSION, "locale": "en"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["version"] == CURRENT_CONSENT_VERSION
        assert data["consentType"] == CONSENT_TYPE_AI_PROCESSING
        assert data["locale"] == "en"
        assert data["userId"] == str(user_a.id)
        assert "id" in data
        assert "grantedAt" in data
    finally:
        _clear_override()


@pytest.mark.asyncio
async def test_get_consent_has_current_true(client, user_a):
    """5 GET /users/me/consent returns hasCurrentConsent=true after grant."""
    _override_current_user(user_a)
    try:
        await client.post(
            "/api/v1/users/me/consent",
            json={"version": CURRENT_CONSENT_VERSION, "locale": "uk"},
        )
        response = await client.get(
            "/api/v1/users/me/consent",
            params={"type": CONSENT_TYPE_AI_PROCESSING},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["hasCurrentConsent"] is True
        assert data["version"] == CURRENT_CONSENT_VERSION
        assert data["locale"] == "uk"
        assert data["grantedAt"] is not None
    finally:
        _clear_override()


@pytest.mark.asyncio
async def test_get_consent_has_current_false_when_none(client, user_a):
    """5 GET /users/me/consent returns hasCurrentConsent=false with no row."""
    _override_current_user(user_a)
    try:
        response = await client.get(
            "/api/v1/users/me/consent",
            params={"type": CONSENT_TYPE_AI_PROCESSING},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["hasCurrentConsent"] is False
        assert data["version"] == CURRENT_CONSENT_VERSION
        assert data["grantedAt"] is None
    finally:
        _clear_override()


# ==================== 401 unauthenticated ====================


@pytest.mark.asyncio
async def test_post_consent_unauthenticated(client):
    """10(b) Unauthenticated POST returns 401."""
    response = await client.post(
        "/api/v1/users/me/consent",
        json={"version": CURRENT_CONSENT_VERSION, "locale": "en"},
    )
    assert response.status_code in (401, 403)


@pytest.mark.asyncio
async def test_get_consent_unauthenticated(client):
    """10(b) Unauthenticated GET returns 401."""
    response = await client.get("/api/v1/users/me/consent")
    assert response.status_code in (401, 403)


# ==================== Tenant isolation ====================


@pytest.mark.asyncio
async def test_tenant_isolation_user_b_cannot_see_user_a_consent(
    client, user_a, user_b
):
    """10(c) User B cannot see User A's consent record."""
    # User A grants consent
    _override_current_user(user_a)
    try:
        resp_a = await client.post(
            "/api/v1/users/me/consent",
            json={"version": CURRENT_CONSENT_VERSION, "locale": "en"},
        )
        assert resp_a.status_code == 201
    finally:
        _clear_override()

    # User B asks for their own status — must be false
    _override_current_user(user_b)
    try:
        resp_b = await client.get("/api/v1/users/me/consent")
        assert resp_b.status_code == 200
        data = resp_b.json()
        assert data["hasCurrentConsent"] is False
    finally:
        _clear_override()


# ==================== Append-only ====================


@pytest.mark.asyncio
async def test_append_only_second_post_creates_second_row(client, user_a, async_engine):
    """10(d) Two sequential POSTs for same user+version create two rows."""
    _override_current_user(user_a)
    try:
        r1 = await client.post(
            "/api/v1/users/me/consent",
            json={"version": CURRENT_CONSENT_VERSION, "locale": "en"},
        )
        r2 = await client.post(
            "/api/v1/users/me/consent",
            json={"version": CURRENT_CONSENT_VERSION, "locale": "uk"},
        )
        assert r1.status_code == 201
        assert r2.status_code == 201
        assert r1.json()["id"] != r2.json()["id"]
    finally:
        _clear_override()

    async with SQLModelAsyncSession(async_engine) as session:
        result = await session.exec(
            select(UserConsent).where(UserConsent.user_id == user_a.id)
        )
        rows = result.all()
        assert len(rows) == 2


# ==================== Version bump ====================


@pytest.mark.asyncio
async def test_version_bump_old_row_does_not_satisfy_new_version(
    client, user_a, async_engine
):
    """10(e) An old-version row does not satisfy hasCurrentConsent for a new version."""
    # Insert an old-version row directly
    async with SQLModelAsyncSession(async_engine) as session:
        old_row = UserConsent(
            user_id=user_a.id,
            consent_type=CONSENT_TYPE_AI_PROCESSING,
            version="2020-01-01-v0",
            locale="en",
            ip=None,
            user_agent=None,
        )
        session.add(old_row)
        await session.commit()

    _override_current_user(user_a)
    try:
        response = await client.get("/api/v1/users/me/consent")
        assert response.status_code == 200
        data = response.json()
        # Old version should NOT satisfy the current version gate
        assert data["hasCurrentConsent"] is False
        assert data["version"] == CURRENT_CONSENT_VERSION
    finally:
        _clear_override()


# ==================== Version mismatch on POST ====================


@pytest.mark.asyncio
async def test_post_consent_rejects_stale_version(client, user_a):
    """POST with a version != CURRENT_CONSENT_VERSION is rejected (422)."""
    _override_current_user(user_a)
    try:
        response = await client.post(
            "/api/v1/users/me/consent",
            json={"version": "1999-01-01-v0", "locale": "en"},
        )
        assert response.status_code == 422
    finally:
        _clear_override()
