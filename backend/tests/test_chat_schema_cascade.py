"""Cascade behavior tests for chat_sessions / chat_messages (Story 10.1b AC #7).

Extended by Story 10.4a AC #11: revoke_chat_consent now calls the chat
session terminator before the DB cascade. Three additional tests verify
(a) the terminator is called once per revoke, (b) revocation still commits
when the terminator raises, and (c) zero-sessions revokes still invoke the
terminator once (idempotency lives in the handler, not in consent_service).
"""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession as SQLModelAsyncSession

from app.core.consent import (
    CONSENT_TYPE_CHAT_PROCESSING,
    CURRENT_CHAT_CONSENT_VERSION,
)
from app.models.chat_message import ChatMessage
from app.models.chat_session import ChatSession
from app.models.consent import UserConsent
from app.models.user import User
from app.services import account_deletion_service, consent_service
from app.services.chat_session_service import (
    ChatConsentRequiredError,
    create_chat_session,
)


@pytest_asyncio.fixture
async def fk_engine():
    # Standalone engine for cascade tests — PRAGMA foreign_keys = ON is set
    # on every new connection so ON DELETE CASCADE actually fires in SQLite.
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


async def _make_user(session: SQLModelAsyncSession) -> User:
    user = User(
        cognito_sub=f"cascade-{uuid.uuid4()}",
        email=f"cascade-{uuid.uuid4()}@example.com",
        is_verified=True,
    )
    session.add(user)
    await session.commit()
    return user


async def _seed_session_with_messages(
    session: SQLModelAsyncSession, user_id: uuid.UUID
) -> tuple[uuid.UUID, list[uuid.UUID]]:
    chat_id = uuid.uuid4()
    msg_ids = [uuid.uuid4(), uuid.uuid4()]
    session.add(
        ChatSession(
            id=chat_id,
            user_id=user_id,
            consent_version_at_creation=CURRENT_CHAT_CONSENT_VERSION,
        )
    )
    await session.flush()
    for mid in msg_ids:
        session.add(
            ChatMessage(id=mid, session_id=chat_id, role="user", content="hello")
        )
    await session.commit()
    return chat_id, msg_ids


# ==================== AC #7(a): user delete cascades sessions + messages ====================


@pytest.mark.asyncio
async def test_delete_user_cascades_to_sessions_and_messages(fk_engine):
    async with SQLModelAsyncSession(fk_engine, expire_on_commit=False) as session:
        user = await _make_user(session)
        _, msg_ids = await _seed_session_with_messages(session, user.id)

        await session.exec(text("DELETE FROM users WHERE id = :uid").bindparams(uid=str(user.id)))
        await session.commit()

        session_count = (await session.exec(
            text("SELECT COUNT(*) FROM chat_sessions WHERE user_id = :uid")
            .bindparams(uid=str(user.id))
        )).one()
        assert session_count[0] == 0

        msg_count = (await session.exec(
            text(
                "SELECT COUNT(*) FROM chat_messages WHERE id IN "
                "(" + ",".join(f"'{m}'" for m in msg_ids) + ")"
            )
        )).one()
        assert msg_count[0] == 0


# ==================== AC #7(b): session delete cascades messages ====================


@pytest.mark.asyncio
async def test_delete_session_cascades_to_messages(fk_engine):
    async with SQLModelAsyncSession(fk_engine, expire_on_commit=False) as session:
        await session.exec(text("PRAGMA foreign_keys = ON"))
        user = await _make_user(session)
        chat_id, msg_ids = await _seed_session_with_messages(session, user.id)

        await session.exec(
            text("DELETE FROM chat_sessions WHERE id = :sid").bindparams(sid=str(chat_id))
        )
        await session.commit()

        msg_count = (await session.exec(
            text(
                "SELECT COUNT(*) FROM chat_messages WHERE id IN "
                "(" + ",".join(f"'{m}'" for m in msg_ids) + ")"
            )
        )).one()
        assert msg_count[0] == 0


# ==================== AC #7(c): revoke_chat_consent cascade ====================


@pytest.mark.asyncio
async def test_revoke_chat_consent_cascades_sessions_messages(fk_engine):
    async with SQLModelAsyncSession(fk_engine, expire_on_commit=False) as session:
        await session.exec(text("PRAGMA foreign_keys = ON"))
        user_a = await _make_user(session)
        user_b = await _make_user(session)

        # Give both users a chat_processing grant + seeded session/messages.
        seeded_msgs: dict[uuid.UUID, list[uuid.UUID]] = {}
        for u in (user_a, user_b):
            await consent_service.grant_consent(
                session=session,
                user=u,
                consent_type=CONSENT_TYPE_CHAT_PROCESSING,
                version=CURRENT_CHAT_CONSENT_VERSION,
                locale="en",
                ip=None,
                user_agent=None,
            )
            _, msg_ids = await _seed_session_with_messages(session, u.id)
            seeded_msgs[u.id] = msg_ids

        await consent_service.revoke_chat_consent(
            session=session, user=user_a, locale="en", ip=None, user_agent=None
        )

        # user_a: sessions gone
        a_sessions = (await session.exec(
            select(ChatSession).where(ChatSession.user_id == user_a.id)
        )).all()
        assert list(a_sessions) == []
        # user_a: messages cascade-deleted — query by id directly so the
        # assertion tests the messages table independently of the session join.
        a_messages = (await session.exec(
            select(ChatMessage).where(ChatMessage.id.in_(seeded_msgs[user_a.id]))
        )).all()
        assert list(a_messages) == []

        # user_a: revoke row was written atomically.
        a_rows = (await session.exec(
            select(UserConsent).where(
                UserConsent.user_id == user_a.id,
                UserConsent.consent_type == CONSENT_TYPE_CHAT_PROCESSING,
            )
        )).all()
        assert sum(1 for r in a_rows if r.revoked_at is not None) == 1

        # user_b: sessions AND messages untouched (tenant isolation).
        b_sessions = (await session.exec(
            select(ChatSession).where(ChatSession.user_id == user_b.id)
        )).all()
        assert len(list(b_sessions)) == 1
        b_messages = (await session.exec(
            select(ChatMessage).where(ChatMessage.id.in_(seeded_msgs[user_b.id]))
        )).all()
        assert len(list(b_messages)) == len(seeded_msgs[user_b.id])


# ==================== AC #7(d): revoke is idempotent with zero sessions ====================


@pytest.mark.asyncio
async def test_revoke_chat_consent_idempotent_no_sessions(fk_engine):
    async with SQLModelAsyncSession(fk_engine, expire_on_commit=False) as session:
        await session.exec(text("PRAGMA foreign_keys = ON"))
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
        # No sessions seeded — cascade should be a clean no-op.
        await consent_service.revoke_chat_consent(
            session=session, user=user, locale="en", ip=None, user_agent=None
        )

        rows = (await session.exec(
            select(UserConsent).where(
                UserConsent.user_id == user.id,
                UserConsent.consent_type == CONSENT_TYPE_CHAT_PROCESSING,
            )
        )).all()
        assert sum(1 for r in rows if r.revoked_at is not None) == 1


# ==================== AC #7(e): delete_all_user_data removes chat rows ====================


@pytest.mark.asyncio
async def test_delete_all_user_data_removes_chat_rows(fk_engine):
    async with SQLModelAsyncSession(fk_engine, expire_on_commit=False) as session:
        await session.exec(text("PRAGMA foreign_keys = ON"))
        target = await _make_user(session)
        other = await _make_user(session)
        _, target_msg_ids = await _seed_session_with_messages(session, target.id)
        _, other_msg_ids = await _seed_session_with_messages(session, other.id)

        fake_cognito = MagicMock()
        fake_cognito.delete_user.return_value = None
        # No S3 keys in this fixture.
        await account_deletion_service.delete_all_user_data(
            session=session,
            user_id=target.id,
            cognito_sub=target.cognito_sub,
            s3_keys=[],
            cognito_service=fake_cognito,
        )

        target_sessions = (await session.exec(
            select(ChatSession).where(ChatSession.user_id == target.id)
        )).all()
        assert list(target_sessions) == []
        target_messages = (await session.exec(
            select(ChatMessage).where(ChatMessage.id.in_(target_msg_ids))
        )).all()
        assert list(target_messages) == []

        # Other user untouched.
        other_messages = (await session.exec(
            select(ChatMessage).where(ChatMessage.id.in_(other_msg_ids))
        )).all()
        assert len(list(other_messages)) == len(other_msg_ids)


# ==================== AC #7(f): re-grant creates a fresh session ====================


@pytest.mark.asyncio
async def test_regrant_after_revoke_allows_new_session(fk_engine):
    async with SQLModelAsyncSession(fk_engine, expire_on_commit=False) as session:
        await session.exec(text("PRAGMA foreign_keys = ON"))
        user = await _make_user(session)

        # grant → create session A
        await consent_service.grant_consent(
            session=session,
            user=user,
            consent_type=CONSENT_TYPE_CHAT_PROCESSING,
            version=CURRENT_CHAT_CONSENT_VERSION,
            locale="en",
            ip=None,
            user_agent=None,
        )
        session_a = await create_chat_session(session, user)

        # revoke (cascade kills A)
        await consent_service.revoke_chat_consent(
            session=session, user=user, locale="en", ip=None, user_agent=None
        )
        gone = (await session.exec(
            select(ChatSession).where(ChatSession.id == session_a.id)
        )).first()
        assert gone is None

        # Attempting to create a session without re-grant must raise.
        with pytest.raises(ChatConsentRequiredError):
            await create_chat_session(session, user)

        # re-grant → create session B
        await consent_service.grant_consent(
            session=session,
            user=user,
            consent_type=CONSENT_TYPE_CHAT_PROCESSING,
            version=CURRENT_CHAT_CONSENT_VERSION,
            locale="en",
            ip=None,
            user_agent=None,
        )
        session_b = await create_chat_session(session, user)

        remaining = list((await session.exec(
            select(ChatSession).where(ChatSession.user_id == user.id)
        )).all())
        assert len(remaining) == 1
        assert remaining[0].id == session_b.id

        # user_consents: one grant, one revoke, one grant (3 rows for chat).
        rows = list((await session.exec(
            select(UserConsent).where(
                UserConsent.user_id == user.id,
                UserConsent.consent_type == CONSENT_TYPE_CHAT_PROCESSING,
            )
        )).all())
        grants = [r for r in rows if r.granted_at is not None and r.revoked_at is None]
        revokes = [r for r in rows if r.revoked_at is not None]
        assert len(grants) == 2
        assert len(revokes) == 1


# ==================== Story 10.4a AC #11: chat session terminator hook ====================
#
# revoke_chat_consent calls the chat session terminator before the DB cascade.
# The call is fail-open: termination errors are logged but must not propagate,
# because consent revocation is legally required to succeed. The terminator is
# always invoked — idempotency lives in the handler, not in consent_service.


@pytest.mark.asyncio
async def test_revoke_calls_terminator_once_before_cascade(fk_engine):
    async with SQLModelAsyncSession(fk_engine, expire_on_commit=False) as session:
        await session.exec(text("PRAGMA foreign_keys = ON"))
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
        _, _ = await _seed_session_with_messages(session, user.id)

        mock_terminator = AsyncMock(return_value=None)
        with patch(
            "app.agents.chat.session_handler.terminate_all_user_sessions_fail_open",
            new=mock_terminator,
        ):
            await consent_service.revoke_chat_consent(
                session=session, user=user, locale="en", ip=None, user_agent=None
            )

        assert mock_terminator.await_count == 1
        # Called with (session, user) — not kwargs; match the import signature.
        args, _kwargs = mock_terminator.call_args
        assert args[1].id == user.id

        # DB cascade still fired — sessions gone.
        remaining = list((await session.exec(
            select(ChatSession).where(ChatSession.user_id == user.id)
        )).all())
        assert remaining == []


@pytest.mark.asyncio
async def test_revoke_commits_when_terminator_raises(fk_engine):
    async with SQLModelAsyncSession(fk_engine, expire_on_commit=False) as session:
        await session.exec(text("PRAGMA foreign_keys = ON"))
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
        _, _ = await _seed_session_with_messages(session, user.id)

        from app.agents.chat.chat_backend import ChatSessionTerminationFailed

        mock_terminator = AsyncMock(side_effect=ChatSessionTerminationFailed("boom"))
        with patch(
            "app.agents.chat.session_handler.terminate_all_user_sessions_fail_open",
            new=mock_terminator,
        ):
            # Does NOT raise — fail-open is the contract.
            await consent_service.revoke_chat_consent(
                session=session, user=user, locale="en", ip=None, user_agent=None
            )

        # Revocation row landed despite the terminator error.
        revokes = list((await session.exec(
            select(UserConsent)
            .where(UserConsent.user_id == user.id)
            .where(UserConsent.consent_type == CONSENT_TYPE_CHAT_PROCESSING)
            .where(UserConsent.revoked_at.is_not(None))  # type: ignore[union-attr]
        )).all())
        assert len(revokes) == 1
        # DB cascade still fired.
        remaining = list((await session.exec(
            select(ChatSession).where(ChatSession.user_id == user.id)
        )).all())
        assert remaining == []


@pytest.mark.asyncio
async def test_revoke_zero_sessions_still_invokes_terminator(fk_engine):
    """The handler's ``terminate_all_user_sessions`` is the one that no-ops
    on zero sessions. consent_service does NOT branch — it always calls the
    terminator, so Phase-B-ready behavior is exercised uniformly.
    """
    async with SQLModelAsyncSession(fk_engine, expire_on_commit=False) as session:
        await session.exec(text("PRAGMA foreign_keys = ON"))
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
        # No chat_sessions seeded.

        mock_terminator = AsyncMock(return_value=None)
        with patch(
            "app.agents.chat.session_handler.terminate_all_user_sessions_fail_open",
            new=mock_terminator,
        ):
            await consent_service.revoke_chat_consent(
                session=session, user=user, locale="en", ip=None, user_agent=None
            )
        assert mock_terminator.await_count == 1
