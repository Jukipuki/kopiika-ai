"""Schema/model tests for chat_sessions + chat_messages (Story 10.1b AC #8)."""
from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession as SQLModelAsyncSession

from app.core.consent import CURRENT_CHAT_CONSENT_VERSION
from app.models.chat_message import ChatMessage
from app.models.chat_session import ChatSession
from app.models.user import User


@pytest_asyncio.fixture
async def fk_engine():
    import os
    import tempfile

    from sqlalchemy import event
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlmodel import SQLModel

    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")

    @event.listens_for(engine.sync_engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, _):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys = ON")
        cursor.close()

    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)
    await engine.dispose()
    os.unlink(db_path)


@pytest_asyncio.fixture
async def seeded_user(fk_engine) -> User:
    user = User(
        cognito_sub=f"schema-{uuid.uuid4()}",
        email=f"schema-{uuid.uuid4()}@example.com",
        is_verified=True,
    )
    async with SQLModelAsyncSession(fk_engine, expire_on_commit=False) as session:
        session.add(user)
        await session.commit()
    return user


# ==================== AC #8(a): consent_version_at_creation required ====================


@pytest.mark.asyncio
async def test_chat_session_requires_consent_version(fk_engine, seeded_user):
    # Supply created_at / last_active_at explicitly so the NOT-NULL violation
    # we are asserting is unambiguously on consent_version_at_creation and
    # not on a timestamp column (the test-only SQLite DDL doesn't replicate
    # the migration's server_default=now()).
    async with SQLModelAsyncSession(fk_engine) as session:
        await session.exec(text("PRAGMA foreign_keys = ON"))
        now_iso = "2026-04-24 00:00:00"
        with pytest.raises(IntegrityError) as exc_info:
            await session.exec(
                text(
                    "INSERT INTO chat_sessions "
                    "(id, user_id, created_at, last_active_at, consent_version_at_creation) "
                    "VALUES (:id, :user_id, :now, :now, NULL)"
                ).bindparams(
                    id=str(uuid.uuid4()),
                    user_id=str(seeded_user.id),
                    now=now_iso,
                )
            )
            await session.commit()
        assert "consent_version_at_creation" in str(exc_info.value)


# ==================== AC #8(b): role CHECK constraint ====================


@pytest.mark.asyncio
async def test_role_check_constraint_rejects_invalid(fk_engine, seeded_user):
    # Seed a real session first so the FK in chat_messages resolves.
    chat_session_id = uuid.uuid4()
    async with SQLModelAsyncSession(fk_engine, expire_on_commit=False) as session:
        await session.exec(text("PRAGMA foreign_keys = ON"))
        cs = ChatSession(
            id=chat_session_id,
            user_id=seeded_user.id,
            consent_version_at_creation=CURRENT_CHAT_CONSENT_VERSION,
        )
        session.add(cs)
        await session.commit()

    async with SQLModelAsyncSession(fk_engine) as session:
        await session.exec(text("PRAGMA foreign_keys = ON"))
        with pytest.raises(IntegrityError):
            await session.exec(
                text(
                    "INSERT INTO chat_messages "
                    "(id, session_id, role, content, redaction_flags, guardrail_action) "
                    "VALUES (:id, :sid, 'admin', 'x', '{}', 'none')"
                ).bindparams(id=str(uuid.uuid4()), sid=str(chat_session_id))
            )
            await session.commit()


# ==================== AC #8(c): guardrail_action CHECK + default ====================


@pytest.mark.asyncio
async def test_guardrail_action_check_constraint_and_default(
    fk_engine, seeded_user
):
    chat_session_id = uuid.uuid4()
    async with SQLModelAsyncSession(fk_engine, expire_on_commit=False) as session:
        await session.exec(text("PRAGMA foreign_keys = ON"))
        session.add(
            ChatSession(
                id=chat_session_id,
                user_id=seeded_user.id,
                consent_version_at_creation=CURRENT_CHAT_CONSENT_VERSION,
            )
        )
        await session.commit()

    # Invalid guardrail_action → IntegrityError
    async with SQLModelAsyncSession(fk_engine) as session:
        await session.exec(text("PRAGMA foreign_keys = ON"))
        with pytest.raises(IntegrityError):
            await session.exec(
                text(
                    "INSERT INTO chat_messages "
                    "(id, session_id, role, content, redaction_flags, guardrail_action) "
                    "VALUES (:id, :sid, 'user', 'x', '{}', 'WHATEVER')"
                ).bindparams(id=str(uuid.uuid4()), sid=str(chat_session_id))
            )
            await session.commit()

    # Default 'none' applies on ORM insert without explicit value
    msg_id = uuid.uuid4()
    async with SQLModelAsyncSession(fk_engine, expire_on_commit=False) as session:
        await session.exec(text("PRAGMA foreign_keys = ON"))
        msg = ChatMessage(id=msg_id, session_id=chat_session_id, role="user", content="hi")
        session.add(msg)
        await session.commit()

    async with SQLModelAsyncSession(fk_engine) as session:
        result = await session.exec(select(ChatMessage).where(ChatMessage.id == msg_id))
        row = result.one()
        assert row.guardrail_action == "none"


# ==================== AC #8(d): redaction_flags dict round-trip ====================


@pytest.mark.asyncio
async def test_redaction_flags_round_trip(fk_engine, seeded_user):
    chat_session_id = uuid.uuid4()
    msg_id = uuid.uuid4()
    payload = {"pii_types": ["email"], "filter_source": "input"}

    async with SQLModelAsyncSession(fk_engine, expire_on_commit=False) as session:
        await session.exec(text("PRAGMA foreign_keys = ON"))
        session.add(
            ChatSession(
                id=chat_session_id,
                user_id=seeded_user.id,
                consent_version_at_creation=CURRENT_CHAT_CONSENT_VERSION,
            )
        )
        await session.flush()
        session.add(
            ChatMessage(
                id=msg_id,
                session_id=chat_session_id,
                role="assistant",
                content="redacted",
                redaction_flags=payload,
            )
        )
        await session.commit()

    # Fresh session to bypass the identity map.
    async with SQLModelAsyncSession(fk_engine) as session:
        result = await session.exec(select(ChatMessage).where(ChatMessage.id == msg_id))
        row = result.one()
        assert row.redaction_flags == payload
        assert row.redaction_flags["pii_types"] == ["email"]
