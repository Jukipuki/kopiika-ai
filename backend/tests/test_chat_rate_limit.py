"""Story 10.11 — chat rate-limit envelope enforcement tests.

Covers:
  * The five new ``RateLimiter`` methods (hourly ZSET, concurrent-slot
    DB count, no-op release, daily-token cap projection / recording).
  * ``create_session_endpoint`` 429 envelope on the concurrent cap.
  * ``stream_chat_turn`` pre-stream ``chat-refused`` frame on hourly +
    daily caps.
  * Disconnect-finalizer partial-spend recording.

All Redis calls go through the autouse ``fake_redis`` fixture
(``backend/tests/conftest.py``); the in-memory fakeredis client is
shared across the test process.
"""

from __future__ import annotations

import asyncio
import json
import os
import tempfile
import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import fakeredis.aioredis
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession as SQLModelAsyncSession

import app.models  # noqa: F401  (registers SQLModel tables)
from app.agents.chat.rate_limit_errors import ChatRateLimitedError
from app.agents.chat.session_handler import ChatSessionHandle
from app.models.chat_session import ChatSession
from app.models.user import User
from app.services.rate_limiter import RateLimiter, _today_utc_suffix


# ---------------------------------------------------------------------
# Async DB fixture (mirrors test_chat_history_endpoints.hist_engine).
# ---------------------------------------------------------------------


@pytest_asyncio.fixture
async def rl_engine():
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)
    await engine.dispose()
    os.unlink(db_path)


@pytest_asyncio.fixture
async def fresh_redis():
    """Module-private fakeredis so per-test keys don't bleed across tests."""
    client = fakeredis.aioredis.FakeRedis(decode_responses=True)
    yield client
    await client.flushall()
    await client.aclose()


@pytest_asyncio.fixture
async def rl(fresh_redis):
    return RateLimiter(redis=fresh_redis)


async def _seed_user(engine, cognito_sub: str) -> uuid.UUID:
    async with SQLModelAsyncSession(engine) as s:
        uid = uuid.uuid4()
        s.add(User(id=uid, email=f"{uuid.uuid4()}@e.co", cognito_sub=cognito_sub))
        await s.commit()
    return uid


async def _seed_session(engine, user_id: uuid.UUID) -> uuid.UUID:
    async with SQLModelAsyncSession(engine) as s:
        cs = ChatSession(user_id=user_id, consent_version_at_creation="v1")
        s.add(cs)
        await s.commit()
        await s.refresh(cs)
        return cs.id


# ---------------------------------------------------------------------
# AC #1 — RateLimiter unit tests.
# ---------------------------------------------------------------------


class TestRateLimiterChatHourly:
    @pytest.mark.asyncio
    async def test_under_cap_records_and_passes(self, rl, fresh_redis):
        uid = "u-1"
        for _ in range(5):
            await rl.check_chat_hourly_rate_limit(
                uid, correlation_id="cid", max_turns=10
            )
        count = await fresh_redis.zcard(f"rate_limit:chat:hourly:{uid}")
        assert count == 5

    @pytest.mark.asyncio
    async def test_at_cap_raises_with_retry_after(self, rl, fresh_redis):
        uid = "u-2"
        for _ in range(3):
            await rl.check_chat_hourly_rate_limit(
                uid, correlation_id="cid", max_turns=3
            )
        with pytest.raises(ChatRateLimitedError) as exc_info:
            await rl.check_chat_hourly_rate_limit(
                uid, correlation_id="cid-blocked", max_turns=3
            )
        assert exc_info.value.cause == "hourly"
        assert exc_info.value.correlation_id == "cid-blocked"
        assert 1 <= (exc_info.value.retry_after_seconds or 0) <= 3600
        # Cap-exceeded path MUST NOT record an additional entry.
        assert await fresh_redis.zcard(f"rate_limit:chat:hourly:{uid}") == 3


class TestRateLimiterConcurrentSlot:
    @pytest.mark.asyncio
    async def test_returns_true_when_under_cap(self, rl, rl_engine):
        uid = await _seed_user(rl_engine, f"sub-{uuid.uuid4()}")
        await _seed_session(rl_engine, uid)
        async with SQLModelAsyncSession(rl_engine) as s:
            ok = await rl.acquire_chat_concurrent_session_slot(
                s, str(uid), max_concurrent=10
            )
        assert ok is True

    @pytest.mark.asyncio
    async def test_returns_false_at_cap(self, rl, rl_engine):
        uid = await _seed_user(rl_engine, f"sub-{uuid.uuid4()}")
        for _ in range(10):
            await _seed_session(rl_engine, uid)
        async with SQLModelAsyncSession(rl_engine) as s:
            ok = await rl.acquire_chat_concurrent_session_slot(
                s, str(uid), max_concurrent=10
            )
        assert ok is False

    @pytest.mark.asyncio
    async def test_release_is_noop(self, rl):
        # No-op release: must not raise, must not touch Redis.
        sentinel = AsyncMock()
        rl._redis = sentinel
        await rl.release_chat_concurrent_session_slot("u-x")
        sentinel.assert_not_called()


class TestRateLimiterDailyTokenCap:
    @pytest.mark.asyncio
    async def test_under_cap_passes(self, rl):
        await rl.check_chat_daily_token_cap(
            "u-d1",
            correlation_id="cid",
            max_tokens_per_day=10_000,
            projected_tokens=100,
        )

    @pytest.mark.asyncio
    async def test_over_cap_raises(self, rl, fresh_redis):
        key = f"rate_limit:chat:daily_tokens:u-d2:{_today_utc_suffix()}"
        await fresh_redis.set(key, "9_900")
        with pytest.raises(ChatRateLimitedError) as exc_info:
            await rl.check_chat_daily_token_cap(
                "u-d2",
                correlation_id="cid-d",
                max_tokens_per_day=10_000,
                projected_tokens=200,
            )
        assert exc_info.value.cause == "daily_tokens"
        # Wall-clock to UTC midnight: between 1s and 24h+.
        assert (exc_info.value.retry_after_seconds or 0) >= 1
        assert (exc_info.value.retry_after_seconds or 0) <= 86_400
        # Pre-gate must NOT INCRBY.
        assert await fresh_redis.get(key) == "9_900"

    @pytest.mark.asyncio
    async def test_record_token_spend_increments_and_sets_ttl(
        self, rl, fresh_redis
    ):
        uid = "u-d3"
        key = f"rate_limit:chat:daily_tokens:{uid}:{_today_utc_suffix()}"
        await rl.record_chat_token_spend(uid, 300)
        await rl.record_chat_token_spend(uid, 200)
        assert await fresh_redis.get(key) == "500"
        ttl = await fresh_redis.ttl(key)
        # First-write set TTL = 25h; second write must NOT push it out.
        assert 0 < ttl <= 25 * 3600

    @pytest.mark.asyncio
    async def test_record_token_spend_zero_is_noop(self, rl, fresh_redis):
        await rl.record_chat_token_spend("u-d4", 0)
        key = f"rate_limit:chat:daily_tokens:u-d4:{_today_utc_suffix()}"
        assert await fresh_redis.get(key) is None

    @pytest.mark.asyncio
    async def test_daily_key_is_calendar_day_aligned(self, rl, fresh_redis):
        # Only the suffix derivation is exercised here; full day-rollover
        # behaviour is verified by the calendar key changing across the
        # UTC midnight boundary (see datetime.now(UTC).date()).
        uid = "u-d5"
        suffix = _today_utc_suffix()
        await rl.record_chat_token_spend(uid, 50)
        assert await fresh_redis.get(
            f"rate_limit:chat:daily_tokens:{uid}:{suffix}"
        ) == "50"


# ---------------------------------------------------------------------
# AC #2 — POST /chat/sessions concurrent-cap 429 envelope.
# ---------------------------------------------------------------------


class _FakeStreamHandler:
    def __init__(self):
        self._stream_events = None
        self._stream_exc = None
        self.create_exc: Exception | None = None
        self.terminate_exc: Exception | None = None

    def set_stream(self, events=None, exc=None):
        self._stream_events = events
        self._stream_exc = exc

    async def create_session(self, db, user):
        if self.create_exc is not None:
            raise self.create_exc
        cs = ChatSession(user_id=user.id, consent_version_at_creation="v1")
        db.add(cs)
        await db.commit()
        await db.refresh(cs)
        return ChatSessionHandle(
            db_session_id=cs.id,
            agentcore_session_id=str(cs.id),
            created_at=cs.created_at,
            user_id=user.id,
        )

    async def terminate_session(self, handle):
        if self.terminate_exc is not None:
            raise self.terminate_exc

    async def send_turn_stream(
        self, db, handle, user_message, *, correlation_id, **_kwargs
    ):
        if self._stream_exc is not None:
            raise self._stream_exc
        for ev in self._stream_events or []:
            if isinstance(ev, Exception):
                raise ev
            yield ev


@pytest_asyncio.fixture
async def chat_client(rl_engine, fresh_redis):
    from app.api.deps import get_db, get_rate_limiter
    from app.api.v1.chat import get_chat_session_handler
    from app.core.security import get_current_user_payload
    from app.main import app

    fake_handler = _FakeStreamHandler()
    rate_limiter = RateLimiter(redis=fresh_redis)

    _request_session: dict[int, SQLModelAsyncSession] = {}

    async def override_db():
        key = id(asyncio.current_task())
        if key not in _request_session:
            s = SQLModelAsyncSession(rl_engine, expire_on_commit=False)
            _request_session[key] = s
            try:
                yield s
            finally:
                await s.close()
                _request_session.pop(key, None)
        else:
            yield _request_session[key]

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_chat_session_handler] = lambda: fake_handler
    app.dependency_overrides[get_rate_limiter] = lambda: rate_limiter

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac, fake_handler, rl_engine, rate_limiter, fresh_redis

    app.dependency_overrides.pop(get_current_user_payload, None)
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_chat_session_handler, None)
    app.dependency_overrides.pop(get_rate_limiter, None)


def _set_auth(sub: str):
    from app.core.security import get_current_user_payload
    from app.main import app

    async def _payload():
        return {"sub": sub}

    app.dependency_overrides[get_current_user_payload] = _payload


@pytest.mark.asyncio
async def test_create_session_blocked_at_concurrent_cap(chat_client):
    client, _, engine, _, _ = chat_client
    sub = f"sub-{uuid.uuid4()}"
    uid = await _seed_user(engine, sub)
    for _ in range(10):
        await _seed_session(engine, uid)
    _set_auth(sub)

    resp = await client.post("/api/v1/chat/sessions")
    assert resp.status_code == 429
    err = resp.json()["detail"]["error"]
    assert err["code"] == "CHAT_RATE_LIMITED"
    assert err["cause"] == "concurrent"
    assert "correlationId" in err


@pytest.mark.asyncio
async def test_create_session_allows_under_cap(chat_client):
    client, _, engine, _, _ = chat_client
    sub = f"sub-{uuid.uuid4()}"
    uid = await _seed_user(engine, sub)
    for _ in range(9):
        await _seed_session(engine, uid)
    _set_auth(sub)

    resp = await client.post("/api/v1/chat/sessions")
    assert resp.status_code == 201


# ---------------------------------------------------------------------
# AC #3 / AC #4 — stream_chat_turn rate-limit refusal frames.
# ---------------------------------------------------------------------


async def _stub_verify(sub: str, monkeypatch):
    from app.api.v1 import _sse as _sse_mod

    async def _vt(t):
        return {"sub": sub}

    monkeypatch.setattr(_sse_mod, "verify_token", _vt)


def _parse_first_frame(body: str) -> tuple[str, dict]:
    block = body.split("\n\n", 1)[0]
    lines = block.splitlines()
    event_line = next(ln for ln in lines if ln.startswith("event: "))
    data_line = next(ln for ln in lines if ln.startswith("data: "))
    return (
        event_line[len("event: "):],
        json.loads(data_line[len("data: "):]),
    )


@pytest.mark.asyncio
async def test_send_turn_blocked_at_hourly_cap(
    chat_client, monkeypatch, fresh_redis
):
    client, _, engine, _, _ = chat_client
    sub = f"sub-{uuid.uuid4()}"
    uid = await _seed_user(engine, sub)
    sid = await _seed_session(engine, uid)
    await _stub_verify(sub, monkeypatch)

    # Pre-seed the hourly ZSET with 60 entries within the rolling window.
    key = f"rate_limit:chat:hourly:{uid}"
    now = datetime.now(UTC).timestamp()
    members = {str(now - i): now - i for i in range(60)}
    await fresh_redis.zadd(key, members)

    resp = await client.post(
        f"/api/v1/chat/sessions/{sid}/turns/stream?token=tok",
        json={"message": "hi"},
    )
    assert resp.status_code == 200
    body = b""
    async for chunk in resp.aiter_bytes():
        body += chunk
    event, payload = _parse_first_frame(body.decode("utf-8"))
    assert event == "chat-refused"
    assert payload["reason"] == "rate_limited"
    assert 1 <= payload["retryAfterSeconds"] <= 3600
    # Block path MUST NOT record a 61st entry.
    assert await fresh_redis.zcard(key) == 60


@pytest.mark.asyncio
async def test_send_turn_blocked_at_daily_token_cap(
    chat_client, monkeypatch, fresh_redis
):
    client, _, engine, _, _ = chat_client
    sub = f"sub-{uuid.uuid4()}"
    uid = await _seed_user(engine, sub)
    sid = await _seed_session(engine, uid)
    await _stub_verify(sub, monkeypatch)

    # Push the daily counter to 1 token below the default cap.
    from app.core.config import settings as _settings

    near_cap = _settings.CHAT_DAILY_TOKEN_CAP_PER_USER - 1
    key = (
        f"rate_limit:chat:daily_tokens:{uid}:{_today_utc_suffix()}"
    )
    await fresh_redis.set(key, str(near_cap))

    resp = await client.post(
        f"/api/v1/chat/sessions/{sid}/turns/stream?token=tok",
        json={"message": "hi"},
    )
    assert resp.status_code == 200
    body = b""
    async for chunk in resp.aiter_bytes():
        body += chunk
    event, payload = _parse_first_frame(body.decode("utf-8"))
    assert event == "chat-refused"
    assert payload["reason"] == "rate_limited"
    # Daily cap retry-after is wall-clock-aligned to UTC midnight.
    assert payload["retryAfterSeconds"] >= 1
    # Pre-gate doesn't INCRBY.
    assert await fresh_redis.get(key) == str(near_cap)


@pytest.mark.asyncio
async def test_send_turn_finalizer_records_partial_spend_on_cancel(
    chat_client, monkeypatch, fresh_redis
):
    """AC #8 (vi) — partial spend MUST be recorded when a stream is
    terminated via CancelledError / unmapped exception (not just the
    polled ``request.is_disconnected`` branch). Otherwise an actor can
    open a turn, consume tokens, and dodge the daily counter by forcing
    an exotic termination.
    """
    from app.agents.chat.stream_events import ChatStreamStarted, ChatTokenDelta

    client, handler, engine, _, _ = chat_client
    sub = f"sub-{uuid.uuid4()}"
    uid = await _seed_user(engine, sub)
    sid = await _seed_session(engine, uid)
    await _stub_verify(sub, monkeypatch)

    # Simulate a client-driven cancellation mid-stream (the bypass
    # vector: open turn → consume tokens → drop TCP → expect zero
    # daily-counter charge). The CancelledError here exits the
    # ``stream_chat_turn`` event loop via the explicit
    # ``except asyncio.CancelledError: raise`` branch, which runs
    # ``finally`` (where the partial-spend recording lives).
    handler.set_stream(
        events=[
            ChatStreamStarted(correlation_id="cid", session_id=str(sid)),
            ChatTokenDelta(text="hello "),
            ChatTokenDelta(text="world"),
            asyncio.CancelledError(),
        ]
    )

    key = f"rate_limit:chat:daily_tokens:{uid}:{_today_utc_suffix()}"
    assert await fresh_redis.get(key) is None

    # The CancelledError will propagate through the StreamingResponse;
    # httpx may raise during iteration. We only care about the side
    # effect: the daily counter MUST be incremented by the finally
    # block before the exception leaves the route.
    try:
        resp = await client.post(
            f"/api/v1/chat/sessions/{sid}/turns/stream?token=tok",
            json={"message": "hi"},
        )
        async for _chunk in resp.aiter_bytes():
            pass
    except (asyncio.CancelledError, Exception):  # noqa: BLE001
        pass

    raw = await fresh_redis.get(key)
    assert raw is not None, (
        "partial spend was not recorded — finalizer hook is missing"
    )
    # Lower bound: at least the input estimate (8000 + len("hi")//3).
    assert int(raw) >= 8000
