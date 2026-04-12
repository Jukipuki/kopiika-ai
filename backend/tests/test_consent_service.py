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

from app.core.consent import CONSENT_TYPE_AI_PROCESSING, CURRENT_CONSENT_VERSION
from app.models.user import User
from app.services import consent_service


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
