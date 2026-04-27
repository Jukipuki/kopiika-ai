"""Story 10.10 — Chat history GET + bulk-delete endpoint tests."""

from __future__ import annotations

import asyncio
import os
import tempfile
import uuid
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession as SQLModelAsyncSession

import app.models  # noqa: F401  (registers SQLModel tables)
from app.agents.chat.chat_backend import ChatSessionTerminationFailed
from app.models.chat_message import ChatMessage
from app.models.chat_session import ChatSession
from app.models.user import User
from app.services import consent_service


@pytest_asyncio.fixture
async def hist_engine():
    """SQLite + foreign-keys ON so the FK cascade fires on chat_messages."""
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
    async with engine.begin() as conn:
        from sqlalchemy import text as sa_text

        await conn.exec_driver_sql("PRAGMA foreign_keys = ON")
        await conn.run_sync(SQLModel.metadata.create_all)
        # Re-affirm pragma after metadata create_all in case a fresh conn was used.
        await conn.execute(sa_text("PRAGMA foreign_keys = ON"))
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)
    await engine.dispose()
    os.unlink(db_path)


async def _seed_user(engine, cognito_sub: str) -> uuid.UUID:
    async with SQLModelAsyncSession(engine) as s:
        uid = uuid.uuid4()
        s.add(User(id=uid, email=f"{uuid.uuid4()}@e.co", cognito_sub=cognito_sub))
        await s.commit()
    return uid


async def _seed_session(
    engine, user_id: uuid.UUID, *, last_active_at: datetime | None = None
) -> uuid.UUID:
    async with SQLModelAsyncSession(engine) as s:
        cs = ChatSession(
            user_id=user_id,
            consent_version_at_creation="v1",
        )
        if last_active_at is not None:
            cs.last_active_at = last_active_at
        s.add(cs)
        await s.commit()
        await s.refresh(cs)
        return cs.id


async def _seed_message(
    engine,
    session_id: uuid.UUID,
    *,
    role: str,
    content: str,
    created_at: datetime | None = None,
) -> uuid.UUID:
    async with SQLModelAsyncSession(engine) as s:
        m = ChatMessage(session_id=session_id, role=role, content=content)
        if created_at is not None:
            m.created_at = created_at
        s.add(m)
        await s.commit()
        await s.refresh(m)
        return m.id


class _FakeHandler:
    def __init__(self):
        self.terminated: list[uuid.UUID] = []
        self.terminate_exc: Exception | None = None

    async def terminate_session(self, handle):
        self.terminated.append(handle.db_session_id)
        if self.terminate_exc is not None:
            raise self.terminate_exc


@pytest_asyncio.fixture
async def hist_client(hist_engine):
    from app.api.deps import get_db
    from app.api.v1.chat import get_chat_session_handler
    from app.core.security import get_current_user_payload
    from app.main import app

    fake = _FakeHandler()

    _request_session: dict[int, SQLModelAsyncSession] = {}

    async def override_db():
        key = id(asyncio.current_task())
        if key not in _request_session:
            s = SQLModelAsyncSession(hist_engine, expire_on_commit=False)
            _request_session[key] = s
            try:
                yield s
            finally:
                await s.close()
                _request_session.pop(key, None)
        else:
            yield _request_session[key]

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_chat_session_handler] = lambda: fake

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac, fake, hist_engine

    app.dependency_overrides.pop(get_current_user_payload, None)
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_chat_session_handler, None)


def _set_auth(sub: str):
    from app.core.security import get_current_user_payload
    from app.main import app

    async def _payload():
        return {"sub": sub}

    app.dependency_overrides[get_current_user_payload] = _payload


# ---------------------------------------------------------------------
# GET /chat/sessions
# ---------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_sessions_returns_in_last_active_desc(hist_client):
    client, _, engine = hist_client
    sub = f"sub-{uuid.uuid4()}"
    uid = await _seed_user(engine, sub)
    base = datetime.now(UTC).replace(tzinfo=None)
    sid_old = await _seed_session(engine, uid, last_active_at=base - timedelta(hours=2))
    sid_mid = await _seed_session(engine, uid, last_active_at=base - timedelta(hours=1))
    sid_new = await _seed_session(engine, uid, last_active_at=base)
    await _seed_message(engine, sid_new, role="user", content="hi")
    await _seed_message(engine, sid_new, role="assistant", content="hello")
    await _seed_message(engine, sid_old, role="user", content="x")
    _set_auth(sub)

    resp = await client.get("/api/v1/chat/sessions")
    assert resp.status_code == 200
    body = resp.json()
    sessions = body["sessions"]
    ids = [s["sessionId"] for s in sessions]
    assert ids == [str(sid_new), str(sid_mid), str(sid_old)]
    counts = {s["sessionId"]: s["messageCount"] for s in sessions}
    assert counts[str(sid_new)] == 2
    assert counts[str(sid_mid)] == 0
    assert counts[str(sid_old)] == 1
    assert body["nextCursor"] is None


@pytest.mark.asyncio
async def test_list_sessions_is_per_tenant(hist_client):
    client, _, engine = hist_client
    sub_a = f"a-{uuid.uuid4()}"
    sub_b = f"b-{uuid.uuid4()}"
    uid_a = await _seed_user(engine, sub_a)
    uid_b = await _seed_user(engine, sub_b)
    sid_a = await _seed_session(engine, uid_a)
    await _seed_session(engine, uid_b)
    _set_auth(sub_a)
    resp = await client.get("/api/v1/chat/sessions")
    assert resp.status_code == 200
    ids = [s["sessionId"] for s in resp.json()["sessions"]]
    assert ids == [str(sid_a)]


@pytest.mark.asyncio
async def test_list_sessions_cursor_paginates(hist_client):
    client, _, engine = hist_client
    sub = f"sub-{uuid.uuid4()}"
    uid = await _seed_user(engine, sub)
    base = datetime.now(UTC).replace(tzinfo=None)
    seeded: list[uuid.UUID] = []
    for i in range(5):
        seeded.append(
            await _seed_session(
                engine, uid, last_active_at=base - timedelta(minutes=i)
            )
        )
    _set_auth(sub)

    page1 = await client.get("/api/v1/chat/sessions?limit=2")
    assert page1.status_code == 200
    body1 = page1.json()
    assert len(body1["sessions"]) == 2
    assert body1["nextCursor"]

    page2 = await client.get(f"/api/v1/chat/sessions?limit=2&cursor={body1['nextCursor']}")
    body2 = page2.json()
    assert len(body2["sessions"]) == 2
    assert body2["nextCursor"]

    page3 = await client.get(f"/api/v1/chat/sessions?limit=2&cursor={body2['nextCursor']}")
    body3 = page3.json()
    assert len(body3["sessions"]) == 1
    assert body3["nextCursor"] is None

    seen = (
        [s["sessionId"] for s in body1["sessions"]]
        + [s["sessionId"] for s in body2["sessions"]]
        + [s["sessionId"] for s in body3["sessions"]]
    )
    assert sorted(seen) == sorted(str(s) for s in seeded)


@pytest.mark.asyncio
async def test_list_sessions_bad_cursor_returns_400(hist_client):
    client, _, engine = hist_client
    sub = f"sub-{uuid.uuid4()}"
    await _seed_user(engine, sub)
    _set_auth(sub)
    resp = await client.get("/api/v1/chat/sessions?cursor=not-a-cursor")
    assert resp.status_code == 400
    assert resp.json()["detail"]["error"]["code"] == "CHAT_HISTORY_BAD_CURSOR"


@pytest.mark.asyncio
async def test_list_sessions_invalid_limit_returns_422(hist_client):
    client, _, engine = hist_client
    sub = f"sub-{uuid.uuid4()}"
    await _seed_user(engine, sub)
    _set_auth(sub)
    resp = await client.get("/api/v1/chat/sessions?limit=0")
    assert resp.status_code == 422


# ---------------------------------------------------------------------
# GET /chat/sessions/{id}/messages
# ---------------------------------------------------------------------


@pytest.mark.asyncio
async def test_transcript_excludes_tool_role(hist_client):
    client, _, engine = hist_client
    sub = f"sub-{uuid.uuid4()}"
    uid = await _seed_user(engine, sub)
    sid = await _seed_session(engine, uid)
    base = datetime.now(UTC).replace(tzinfo=None)
    await _seed_message(engine, sid, role="user", content="hi", created_at=base)
    await _seed_message(
        engine,
        sid,
        role="tool",
        content="raw tool payload",
        created_at=base + timedelta(seconds=1),
    )
    await _seed_message(
        engine,
        sid,
        role="assistant",
        content="hi back",
        created_at=base + timedelta(seconds=2),
    )
    _set_auth(sub)

    resp = await client.get(f"/api/v1/chat/sessions/{sid}/messages")
    assert resp.status_code == 200
    msgs = resp.json()["messages"]
    roles = [m["role"] for m in msgs]
    assert roles == ["user", "assistant"]
    assert all(m["role"] != "tool" for m in msgs)


@pytest.mark.asyncio
async def test_transcript_cross_user_returns_404(hist_client):
    client, _, engine = hist_client
    sub_a = f"a-{uuid.uuid4()}"
    sub_b = f"b-{uuid.uuid4()}"
    await _seed_user(engine, sub_a)
    uid_b = await _seed_user(engine, sub_b)
    sid_b = await _seed_session(engine, uid_b)
    _set_auth(sub_a)
    resp = await client.get(f"/api/v1/chat/sessions/{sid_b}/messages")
    assert resp.status_code == 404
    assert resp.json()["detail"]["error"]["code"] == "CHAT_SESSION_NOT_FOUND"


# ---------------------------------------------------------------------
# DELETE /chat/sessions  (bulk)
# ---------------------------------------------------------------------


@pytest.mark.asyncio
async def test_bulk_delete_and_account_delete_cascades(hist_client):
    client, fake, engine = hist_client
    sub_a = f"a-{uuid.uuid4()}"
    sub_b = f"b-{uuid.uuid4()}"
    uid_a = await _seed_user(engine, sub_a)
    uid_b = await _seed_user(engine, sub_b)
    a_sids: list[uuid.UUID] = []
    for _ in range(3):
        sid = await _seed_session(engine, uid_a)
        for _ in range(5):
            await _seed_message(engine, sid, role="user", content="m")
        a_sids.append(sid)
    sid_b = await _seed_session(engine, uid_b)
    await _seed_message(engine, sid_b, role="user", content="b1")
    await _seed_message(engine, sid_b, role="assistant", content="b2")

    # (a) bulk-DELETE as user_a
    _set_auth(sub_a)
    resp = await client.delete("/api/v1/chat/sessions")
    assert resp.status_code == 204

    async with SQLModelAsyncSession(engine) as s:
        from sqlalchemy import func as sa_func
        from sqlalchemy import select as sa_select

        ca = await s.exec(
            sa_select(sa_func.count())
            .select_from(ChatSession)
            .where(ChatSession.user_id == uid_a)
        )
        assert ca.scalar_one() == 0
        cma = await s.exec(
            sa_select(sa_func.count())
            .select_from(ChatMessage)
            .join(ChatSession, ChatMessage.session_id == ChatSession.id)
            .where(ChatSession.user_id == uid_a)
        )
        assert cma.scalar_one() == 0
        cb = await s.exec(
            sa_select(sa_func.count())
            .select_from(ChatSession)
            .where(ChatSession.user_id == uid_b)
        )
        assert cb.scalar_one() == 1
        cmb = await s.exec(
            sa_select(sa_func.count())
            .select_from(ChatMessage)
            .join(ChatSession, ChatMessage.session_id == ChatSession.id)
            .where(ChatSession.user_id == uid_b)
        )
        assert cmb.scalar_one() == 2

    # terminate_session called once per seeded user_a session BEFORE the delete.
    assert sorted(fake.terminated) == sorted(a_sids)

    # (b) bulk-DELETE on a user with zero sessions returns 204
    fake.terminated.clear()
    resp = await client.delete("/api/v1/chat/sessions")
    assert resp.status_code == 204
    assert fake.terminated == []

    # (c) account-deletion path cascades user_b sessions + messages.
    # FK cascade is wired in 10.1b's migration (chat_sessions.user_id ON
    # DELETE CASCADE); deleting the user row exercises the same chain that
    # account_deletion_service.delete_all_user_data triggers in production.
    async with SQLModelAsyncSession(engine, expire_on_commit=False) as s:
        user_b = await s.get(User, uid_b)
        await s.delete(user_b)
        await s.commit()
    async with SQLModelAsyncSession(engine) as s:
        from sqlalchemy import func as sa_func
        from sqlalchemy import select as sa_select

        cb = await s.exec(
            sa_select(sa_func.count())
            .select_from(ChatSession)
            .where(ChatSession.user_id == uid_b)
        )
        assert cb.scalar_one() == 0


@pytest.mark.asyncio
async def test_bulk_delete_terminates_runtime_first(hist_client):
    """terminate_session is called for every session BEFORE the DB delete; a
    ChatSessionTerminationFailed aborts the transaction with 503 + zero rows
    deleted.
    """
    client, fake, engine = hist_client
    sub = f"sub-{uuid.uuid4()}"
    uid = await _seed_user(engine, sub)
    seeded = [await _seed_session(engine, uid) for _ in range(2)]
    fake.terminate_exc = ChatSessionTerminationFailed("boom")
    _set_auth(sub)

    resp = await client.delete("/api/v1/chat/sessions")
    assert resp.status_code == 503
    assert resp.json()["detail"]["error"]["code"] == "CHAT_BACKEND_UNAVAILABLE"
    # terminate_session was called at least once before abort.
    assert len(fake.terminated) >= 1

    # Rows preserved.
    async with SQLModelAsyncSession(engine) as s:
        from sqlalchemy import func as sa_func
        from sqlalchemy import select as sa_select

        c = await s.exec(
            sa_select(sa_func.count())
            .select_from(ChatSession)
            .where(ChatSession.user_id == uid)
        )
        assert c.scalar_one() == len(seeded)


@pytest.mark.asyncio
async def test_after_revoke_consent_listing_is_empty(hist_client):
    """AC #4(d): post-revoke, the new GET observes the cascade's empty state."""
    client, fake, engine = hist_client
    sub = f"sub-{uuid.uuid4()}"
    uid = await _seed_user(engine, sub)
    await _seed_session(engine, uid)
    await _seed_session(engine, uid)
    _set_auth(sub)

    # Sanity: listing shows the seeded sessions.
    pre = await client.get("/api/v1/chat/sessions")
    assert len(pre.json()["sessions"]) == 2

    async with SQLModelAsyncSession(engine, expire_on_commit=False) as s:
        user = await s.get(User, uid)
        # Seed a chat_processing consent so revoke has something to mark.
        from app.core.consent import (
            CONSENT_TYPE_CHAT_PROCESSING,
            CURRENT_CHAT_CONSENT_VERSION,
        )
        from app.models.consent import UserConsent

        s.add(
            UserConsent(
                user_id=uid,
                consent_type=CONSENT_TYPE_CHAT_PROCESSING,
                version=CURRENT_CHAT_CONSENT_VERSION,
                granted_at=datetime.now(UTC).replace(tzinfo=None),
                locale="en",
            )
        )
        await s.commit()
        await consent_service.revoke_chat_consent(
            s, user, locale="en", ip=None, user_agent=None
        )

    post = await client.get("/api/v1/chat/sessions")
    assert post.status_code == 200
    assert post.json()["sessions"] == []
