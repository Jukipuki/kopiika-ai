"""Unit tests for consent_service (Story 5.2).

These tests exercise ``consent_service`` directly (no FastAPI request path)
and use the shared ``async_engine`` fixture from ``conftest.py``. Each test
opens its own ``SQLModelAsyncSession`` context — matching the shape the
FastAPI request handler uses — so the SQLAlchemy async greenlet machinery
is set up the same way it is in production.
"""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession as SQLModelAsyncSession

from app.core.consent import (
    CONSENT_TYPE_AI_PROCESSING,
    CONSENT_TYPE_CHAT_PROCESSING,
    CURRENT_CHAT_CONSENT_VERSION,
    CURRENT_CONSENT_VERSION,
)
from app.models.consent import UserConsent
from app.models.user import User
from app.services import consent_service
from sqlmodel import select


@asynccontextmanager
async def _session_ctx(async_engine):
    # expire_on_commit=False keeps instance attributes accessible after commit
    # without a refresh round-trip (refresh interacts poorly with aiosqlite
    # under the pytest-asyncio event loop).
    async with SQLModelAsyncSession(
        async_engine, expire_on_commit=False
    ) as session:
        yield session


async def _make_user(session: SQLModelAsyncSession) -> User:
    user = User(
        cognito_sub=f"sub-{uuid.uuid4()}",
        email=f"{uuid.uuid4()}@example.com",
        is_verified=True,
    )
    session.add(user)
    await session.commit()
    return user


@pytest.mark.asyncio
async def test_grant_consent_creates_row(async_engine):
    async with _session_ctx(async_engine) as session:
        user = await _make_user(session)
        record = await consent_service.grant_consent(
            session=session,
            user=user,
            consent_type=CONSENT_TYPE_AI_PROCESSING,
            version=CURRENT_CONSENT_VERSION,
            locale="en",
            ip="10.0.0.1",
            user_agent="pytest/1.0",
        )

    assert record.id is not None
    assert record.user_id == user.id
    assert record.consent_type == CONSENT_TYPE_AI_PROCESSING
    assert record.version == CURRENT_CONSENT_VERSION
    assert record.locale == "en"
    assert record.ip == "10.0.0.1"
    assert record.user_agent == "pytest/1.0"
    assert record.granted_at is not None


@pytest.mark.asyncio
async def test_grant_consent_is_append_only(async_engine):
    async with _session_ctx(async_engine) as session:
        user = await _make_user(session)
        r1 = await consent_service.grant_consent(
            session=session,
            user=user,
            consent_type=CONSENT_TYPE_AI_PROCESSING,
            version=CURRENT_CONSENT_VERSION,
            locale="en",
            ip=None,
            user_agent=None,
        )
        r2 = await consent_service.grant_consent(
            session=session,
            user=user,
            consent_type=CONSENT_TYPE_AI_PROCESSING,
            version=CURRENT_CONSENT_VERSION,
            locale="uk",
            ip=None,
            user_agent=None,
        )

    assert r1.id != r2.id
    assert r1.locale == "en"
    assert r2.locale == "uk"


@pytest.mark.asyncio
async def test_get_current_consent_status_no_row(async_engine):
    async with _session_ctx(async_engine) as session:
        user = await _make_user(session)
        status = await consent_service.get_current_consent_status(
            session=session,
            user=user,
            consent_type=CONSENT_TYPE_AI_PROCESSING,
            version=CURRENT_CONSENT_VERSION,
        )

    assert status["hasCurrentConsent"] is False
    assert status["version"] == CURRENT_CONSENT_VERSION
    assert status["grantedAt"] is None
    assert status["locale"] is None


@pytest.mark.asyncio
async def test_get_current_consent_status_matches_version(async_engine):
    async with _session_ctx(async_engine) as session:
        user = await _make_user(session)
        await consent_service.grant_consent(
            session=session,
            user=user,
            consent_type=CONSENT_TYPE_AI_PROCESSING,
            version=CURRENT_CONSENT_VERSION,
            locale="uk",
            ip=None,
            user_agent=None,
        )
        status = await consent_service.get_current_consent_status(
            session=session,
            user=user,
            consent_type=CONSENT_TYPE_AI_PROCESSING,
            version=CURRENT_CONSENT_VERSION,
        )

    assert status["hasCurrentConsent"] is True
    assert status["version"] == CURRENT_CONSENT_VERSION
    assert status["locale"] == "uk"


@pytest.mark.asyncio
async def test_get_current_consent_status_ignores_old_version(async_engine):
    async with _session_ctx(async_engine) as session:
        user = await _make_user(session)
        await consent_service.grant_consent(
            session=session,
            user=user,
            consent_type=CONSENT_TYPE_AI_PROCESSING,
            version="2020-01-01-v0",
            locale="en",
            ip=None,
            user_agent=None,
        )
        status = await consent_service.get_current_consent_status(
            session=session,
            user=user,
            consent_type=CONSENT_TYPE_AI_PROCESSING,
            version=CURRENT_CONSENT_VERSION,
        )

    assert status["hasCurrentConsent"] is False


@pytest.mark.asyncio
async def test_revoke_chat_consent_inserts_append_only_row(async_engine):
    """``revoke_chat_consent`` appends a NEW row with ``revoked_at`` set,
    never updates the existing grant row."""
    async with _session_ctx(async_engine) as session:
        user = await _make_user(session)
        grant = await consent_service.grant_consent(
            session=session,
            user=user,
            consent_type=CONSENT_TYPE_CHAT_PROCESSING,
            version=CURRENT_CHAT_CONSENT_VERSION,
            locale="en",
            ip=None,
            user_agent=None,
        )
        revoke = await consent_service.revoke_chat_consent(
            session=session,
            user=user,
            locale="en",
            ip=None,
            user_agent=None,
        )

        result = await session.exec(
            select(UserConsent).where(
                UserConsent.user_id == user.id,
                UserConsent.consent_type == CONSENT_TYPE_CHAT_PROCESSING,
            )
        )
        rows = list(result.all())
        assert len(rows) == 2
        grant_row = next(r for r in rows if r.id == grant.id)
        assert grant_row.revoked_at is None
        assert grant_row.granted_at is not None
        revoke_row = next(r for r in rows if r.id == revoke.id)
        assert revoke_row.revoked_at is not None
        # H1: revoke rows must have granted_at=NULL so that granted_at and
        # revoked_at are mutually-exclusive event-type discriminators.
        assert revoke_row.granted_at is None
        assert revoke_row.version == CURRENT_CHAT_CONSENT_VERSION


@pytest.mark.asyncio
async def test_get_current_consent_status_resolves_grant_revoke_regrant(
    async_engine,
):
    """Most-recent row wins — grant → revoke → regrant ends in
    hasCurrentConsent=True."""
    async with _session_ctx(async_engine) as session:
        user = await _make_user(session)

        await consent_service.grant_consent(
            session=session,
            user=user,
            consent_type=CONSENT_TYPE_CHAT_PROCESSING,
            version=CURRENT_CHAT_CONSENT_VERSION,
            locale="en",
            ip=None,
            user_agent=None,
        )
        after_grant = await consent_service.get_current_consent_status(
            session=session,
            user=user,
            consent_type=CONSENT_TYPE_CHAT_PROCESSING,
            version=CURRENT_CHAT_CONSENT_VERSION,
        )
        assert after_grant["hasCurrentConsent"] is True
        assert after_grant["revokedAt"] is None

        await consent_service.revoke_chat_consent(
            session=session,
            user=user,
            locale="en",
            ip=None,
            user_agent=None,
        )
        after_revoke = await consent_service.get_current_consent_status(
            session=session,
            user=user,
            consent_type=CONSENT_TYPE_CHAT_PROCESSING,
            version=CURRENT_CHAT_CONSENT_VERSION,
        )
        assert after_revoke["hasCurrentConsent"] is False
        assert after_revoke["revokedAt"] is not None

        await consent_service.grant_consent(
            session=session,
            user=user,
            consent_type=CONSENT_TYPE_CHAT_PROCESSING,
            version=CURRENT_CHAT_CONSENT_VERSION,
            locale="en",
            ip=None,
            user_agent=None,
        )
        after_regrant = await consent_service.get_current_consent_status(
            session=session,
            user=user,
            consent_type=CONSENT_TYPE_CHAT_PROCESSING,
            version=CURRENT_CHAT_CONSENT_VERSION,
        )
        assert after_regrant["hasCurrentConsent"] is True
        assert after_regrant["revokedAt"] is None
