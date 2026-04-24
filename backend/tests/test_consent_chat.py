"""API tests for chat-processing consent — POST/GET/DELETE
/api/v1/users/me/consent?type=chat_processing (Story 10.1a)."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession as SQLModelAsyncSession

from app.api.deps import get_current_user
from app.core.consent import (
    CONSENT_TYPE_AI_PROCESSING,
    CONSENT_TYPE_CHAT_PROCESSING,
    CURRENT_CHAT_CONSENT_VERSION,
    CURRENT_CONSENT_VERSION,
)
from app.main import app
from app.models.consent import UserConsent
from app.models.user import User
from app.services import consent_service


@pytest_asyncio.fixture
async def user_a(async_engine) -> User:
    user = User(
        cognito_sub=f"chat-a-{uuid.uuid4()}",
        email=f"chat-a-{uuid.uuid4()}@example.com",
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
        cognito_sub=f"chat-b-{uuid.uuid4()}",
        email=f"chat-b-{uuid.uuid4()}@example.com",
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


# ==================== AC #9(a): grant chat consent ====================


@pytest.mark.asyncio
async def test_grant_chat_consent_inserts_row_and_get_reports_true(client, user_a):
    _override_current_user(user_a)
    try:
        resp = await client.post(
            "/api/v1/users/me/consent",
            json={
                "version": CURRENT_CHAT_CONSENT_VERSION,
                "locale": "en",
                "consentType": CONSENT_TYPE_CHAT_PROCESSING,
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["consentType"] == CONSENT_TYPE_CHAT_PROCESSING
        assert data["version"] == CURRENT_CHAT_CONSENT_VERSION

        get_resp = await client.get(
            "/api/v1/users/me/consent",
            params={"type": CONSENT_TYPE_CHAT_PROCESSING},
        )
        assert get_resp.status_code == 200
        body = get_resp.json()
        assert body["hasCurrentConsent"] is True
        assert body["version"] == CURRENT_CHAT_CONSENT_VERSION
        assert body["grantedAt"] is not None
        assert body["revokedAt"] is None
    finally:
        _clear_override()


# ==================== AC #9(b): revoke chat consent ====================


@pytest.mark.asyncio
async def test_revoke_chat_consent_inserts_revoked_row_and_get_reports_false(
    client, user_a, async_engine
):
    _override_current_user(user_a)
    try:
        grant_resp = await client.post(
            "/api/v1/users/me/consent",
            json={
                "version": CURRENT_CHAT_CONSENT_VERSION,
                "locale": "uk",
                "consentType": CONSENT_TYPE_CHAT_PROCESSING,
            },
        )
        assert grant_resp.status_code == 201

        del_resp = await client.delete(
            "/api/v1/users/me/consent",
            params={"type": CONSENT_TYPE_CHAT_PROCESSING},
        )
        assert del_resp.status_code == 204

        get_resp = await client.get(
            "/api/v1/users/me/consent",
            params={"type": CONSENT_TYPE_CHAT_PROCESSING},
        )
        assert get_resp.status_code == 200
        body = get_resp.json()
        assert body["hasCurrentConsent"] is False
        assert body["revokedAt"] is not None
        # H1: after revoke, grantedAt must be null (not the revoke-event
        # timestamp) — granted_at and revoked_at are mutually exclusive.
        assert body["grantedAt"] is None
    finally:
        _clear_override()

    # Two rows in DB: one grant (revoked_at NULL), one revoke (revoked_at set).
    async with SQLModelAsyncSession(async_engine) as session:
        result = await session.exec(
            select(UserConsent).where(
                UserConsent.user_id == user_a.id,
                UserConsent.consent_type == CONSENT_TYPE_CHAT_PROCESSING,
            )
        )
        rows = list(result.all())
        assert len(rows) == 2
        assert sum(1 for r in rows if r.revoked_at is None) == 1
        assert sum(1 for r in rows if r.revoked_at is not None) == 1


# ==================== AC #9(c): re-grant after revoke ====================


@pytest.mark.asyncio
async def test_regrant_after_revoke_most_recent_non_revoked_wins(
    client, user_a
):
    _override_current_user(user_a)
    try:
        # grant → revoke → re-grant
        r1 = await client.post(
            "/api/v1/users/me/consent",
            json={
                "version": CURRENT_CHAT_CONSENT_VERSION,
                "locale": "en",
                "consentType": CONSENT_TYPE_CHAT_PROCESSING,
            },
        )
        assert r1.status_code == 201
        r2 = await client.delete(
            "/api/v1/users/me/consent",
            params={"type": CONSENT_TYPE_CHAT_PROCESSING},
        )
        assert r2.status_code == 204
        r3 = await client.post(
            "/api/v1/users/me/consent",
            json={
                "version": CURRENT_CHAT_CONSENT_VERSION,
                "locale": "en",
                "consentType": CONSENT_TYPE_CHAT_PROCESSING,
            },
        )
        assert r3.status_code == 201

        get_resp = await client.get(
            "/api/v1/users/me/consent",
            params={"type": CONSENT_TYPE_CHAT_PROCESSING},
        )
        body = get_resp.json()
        assert body["hasCurrentConsent"] is True
        assert body["revokedAt"] is None
    finally:
        _clear_override()


# ==================== AC #9(d): independent streams ====================


@pytest.mark.asyncio
async def test_ai_grant_does_not_satisfy_chat_status(client, user_a):
    _override_current_user(user_a)
    try:
        # Grant only ai_processing
        r = await client.post(
            "/api/v1/users/me/consent",
            json={"version": CURRENT_CONSENT_VERSION, "locale": "en"},
        )
        assert r.status_code == 201

        chat_get = await client.get(
            "/api/v1/users/me/consent",
            params={"type": CONSENT_TYPE_CHAT_PROCESSING},
        )
        assert chat_get.status_code == 200
        assert chat_get.json()["hasCurrentConsent"] is False
    finally:
        _clear_override()


@pytest.mark.asyncio
async def test_chat_grant_does_not_satisfy_ai_status(client, user_a):
    _override_current_user(user_a)
    try:
        r = await client.post(
            "/api/v1/users/me/consent",
            json={
                "version": CURRENT_CHAT_CONSENT_VERSION,
                "locale": "en",
                "consentType": CONSENT_TYPE_CHAT_PROCESSING,
            },
        )
        assert r.status_code == 201

        ai_get = await client.get(
            "/api/v1/users/me/consent",
            params={"type": CONSENT_TYPE_AI_PROCESSING},
        )
        assert ai_get.status_code == 200
        assert ai_get.json()["hasCurrentConsent"] is False
    finally:
        _clear_override()


# ==================== AC #9(e): version mismatch on chat ====================


@pytest.mark.asyncio
async def test_chat_consent_version_mismatch_returns_422_with_consent_type(
    client, user_a
):
    _override_current_user(user_a)
    try:
        resp = await client.post(
            "/api/v1/users/me/consent",
            json={
                "version": "1999-01-01-v0",
                "locale": "en",
                "consentType": CONSENT_TYPE_CHAT_PROCESSING,
            },
        )
        assert resp.status_code == 422
        body = resp.json()
        detail = body.get("detail", {})
        error = detail.get("error", {}) if isinstance(detail, dict) else {}
        assert error.get("code") == "CONSENT_VERSION_MISMATCH"
        details = error.get("details", {})
        assert details.get("consentType") == CONSENT_TYPE_CHAT_PROCESSING
        assert details.get("expected") == CURRENT_CHAT_CONSENT_VERSION
    finally:
        _clear_override()


# ==================== AC #9(f): DELETE ai_processing rejected ====================


@pytest.mark.asyncio
async def test_delete_ai_processing_returns_400_not_revocable(client, user_a):
    _override_current_user(user_a)
    try:
        resp = await client.delete(
            "/api/v1/users/me/consent",
            params={"type": CONSENT_TYPE_AI_PROCESSING},
        )
        assert resp.status_code == 400
        body = resp.json()
        detail = body.get("detail", {})
        error = detail.get("error", {}) if isinstance(detail, dict) else {}
        assert error.get("code") == "CONSENT_TYPE_NOT_REVOCABLE"
    finally:
        _clear_override()


# ==================== AC #9(g): DROPPED (M3) ====================
# The tenant-isolation AC was dropped in code review: endpoints operate on
# ``current_user``, so cross-tenant access isn't reachable via the HTTP
# surface. Tenant safety lives at the query layer (all queries filter by
# ``user_id``) and is covered implicitly by the grant/revoke tests above.


# ==================== M2: revoke without prior grant → 409 ====================


@pytest.mark.asyncio
async def test_revoke_without_prior_grant_returns_409(client, user_a):
    """A DELETE from a user who has never granted chat consent must fail
    with 409 NO_ACTIVE_CONSENT_TO_REVOKE — no orphan row is inserted."""
    _override_current_user(user_a)
    try:
        resp = await client.delete(
            "/api/v1/users/me/consent",
            params={"type": CONSENT_TYPE_CHAT_PROCESSING},
        )
        assert resp.status_code == 409
        body = resp.json()
        detail = body.get("detail", {})
        error = detail.get("error", {}) if isinstance(detail, dict) else {}
        assert error.get("code") == "NO_ACTIVE_CONSENT_TO_REVOKE"
    finally:
        _clear_override()


# ==================== AC #9(h): integration hook exists ====================


@pytest.mark.asyncio
async def test_delete_calls_revoke_chat_consent_service(
    client, user_a, monkeypatch
):
    """The DELETE handler MUST call consent_service.revoke_chat_consent so
    10.1b has a single integration point to wire the chat_sessions cascade."""
    calls: list[dict] = []
    real = consent_service.revoke_chat_consent

    async def spy(**kwargs):
        calls.append(kwargs)
        return await real(**kwargs)

    monkeypatch.setattr(consent_service, "revoke_chat_consent", spy)
    # The consent endpoint imports the module attribute at call time via
    # ``consent_service.revoke_chat_consent(...)``, so monkeypatching the
    # module attribute is sufficient.

    _override_current_user(user_a)
    try:
        # Must grant first — otherwise the M2 guard returns 409 before the
        # service is called.
        grant_resp = await client.post(
            "/api/v1/users/me/consent",
            json={
                "version": CURRENT_CHAT_CONSENT_VERSION,
                "locale": "en",
                "consentType": CONSENT_TYPE_CHAT_PROCESSING,
            },
        )
        assert grant_resp.status_code == 201

        resp = await client.delete(
            "/api/v1/users/me/consent",
            params={"type": CONSENT_TYPE_CHAT_PROCESSING},
        )
        assert resp.status_code == 204
    finally:
        _clear_override()

    assert len(calls) == 1
    assert calls[0]["user"].id == user_a.id


# ==================== AC #9(i): shared rate limit ====================


@pytest.mark.asyncio
async def test_rate_limit_shared_across_grant_and_revoke(
    client, user_a, mock_rate_limiter
):
    """Grant + revoke share the same rate-limit bucket — both call
    ``check_consent_rate_limit`` with the same user_id key."""
    mock_rate_limiter.check_consent_rate_limit = AsyncMock(return_value=None)

    _override_current_user(user_a)
    try:
        await client.post(
            "/api/v1/users/me/consent",
            json={
                "version": CURRENT_CHAT_CONSENT_VERSION,
                "locale": "en",
                "consentType": CONSENT_TYPE_CHAT_PROCESSING,
            },
        )
        await client.delete(
            "/api/v1/users/me/consent",
            params={"type": CONSENT_TYPE_CHAT_PROCESSING},
        )
    finally:
        _clear_override()

    # Both grant and revoke hit the same rate-limit key.
    assert mock_rate_limiter.check_consent_rate_limit.await_count == 2
    for call in mock_rate_limiter.check_consent_rate_limit.await_args_list:
        assert call.args[0] == str(user_a.id)
