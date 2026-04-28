"""Story 10.5 AC #11 — FastAPI chat route tests."""

from __future__ import annotations

import asyncio
import json
import os
import tempfile
import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession as SQLModelAsyncSession

import app.models  # noqa: F401
from app.agents.chat.chat_backend import ChatGuardrailInterventionError, ChatTransientError
from app.agents.chat.input_validator import ChatInputBlockedError
from app.agents.chat.rate_limit_errors import ChatRateLimitedError
from app.agents.chat.session_handler import ChatSessionHandle
from app.agents.chat.stream_events import (
    ChatStreamCompleted,
    ChatStreamStarted,
    ChatTokenDelta,
)
from app.agents.chat.tools.tool_errors import ChatToolLoopExceededError
from app.models.chat_session import ChatSession
from app.models.user import User
from app.services.chat_session_service import ChatConsentRequiredError


@pytest_asyncio.fixture
async def ch_engine():
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


async def _seed_user(engine, cognito_sub: str) -> uuid.UUID:
    async with SQLModelAsyncSession(engine) as s:
        uid = uuid.uuid4()
        s.add(User(id=uid, email=f"{uuid.uuid4()}@e.co", cognito_sub=cognito_sub))
        await s.commit()
    return uid


async def _seed_chat_session(engine, user_id: uuid.UUID) -> uuid.UUID:
    async with SQLModelAsyncSession(engine) as s:
        cs = ChatSession(user_id=user_id, consent_version_at_creation="v1")
        s.add(cs)
        await s.commit()
        await s.refresh(cs)
        return cs.id


class _FakeStreamHandler:
    """Stand-in for ChatSessionHandler — route tests wire this via DI."""

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
            if isinstance(ev, float):
                await asyncio.sleep(ev)
                continue
            yield ev


@pytest_asyncio.fixture
async def client_and_handler(ch_engine):
    from app.api.deps import get_db
    from app.api.v1.chat import get_chat_session_handler
    from app.core.security import get_current_user_payload
    from app.main import app

    fake_handler = _FakeStreamHandler()

    # Share one session per request so the User loaded by get_current_user
    # doesn't get expired before the route handler accesses its attributes.
    _request_session: dict[int, SQLModelAsyncSession] = {}

    async def override_db():
        key = id(asyncio.current_task())
        if key not in _request_session:
            s = SQLModelAsyncSession(ch_engine, expire_on_commit=False)
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

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac, fake_handler, ch_engine

    app.dependency_overrides.pop(get_current_user_payload, None)
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_chat_session_handler, None)


def _set_auth(sub: str):
    from app.core.security import get_current_user_payload
    from app.main import app

    async def _payload():
        return {"sub": sub}

    app.dependency_overrides[get_current_user_payload] = _payload


async def _read_sse_body(response) -> str:
    buf = b""
    async for chunk in response.aiter_bytes():
        buf += chunk
    return buf.decode("utf-8")


def _parse_frames(body: str) -> list[tuple[str, dict | None]]:
    frames: list[tuple[str, dict | None]] = []
    for block in body.split("\n\n"):
        if not block.strip():
            continue
        if block.startswith(":"):
            frames.append(("heartbeat", None))
            continue
        lines = block.splitlines()
        event_line = next((ln for ln in lines if ln.startswith("event: ")), None)
        data_line = next((ln for ln in lines if ln.startswith("data: ")), None)
        if event_line and data_line:
            frames.append(
                (event_line[len("event: ") :], json.loads(data_line[len("data: ") :]))
            )
    return frames


# ---------------------------------------------------------------------
# POST /chat/sessions
# ---------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_session_happy_path(client_and_handler):
    client, fake, engine = client_and_handler
    sub = f"sub-{uuid.uuid4()}"
    await _seed_user(engine, sub)
    _set_auth(sub)
    resp = await client.post("/api/v1/chat/sessions")
    assert resp.status_code == 201
    body = resp.json()
    assert "sessionId" in body
    assert "createdAt" in body
    assert "consentVersionAtCreation" in body


@pytest.mark.asyncio
async def test_create_session_no_consent_returns_403(client_and_handler):
    client, fake, engine = client_and_handler
    sub = f"sub-{uuid.uuid4()}"
    await _seed_user(engine, sub)
    _set_auth(sub)
    fake.create_exc = ChatConsentRequiredError("no consent")
    resp = await client.post("/api/v1/chat/sessions")
    assert resp.status_code == 403
    assert resp.json()["detail"]["error"]["code"] == "CHAT_CONSENT_REQUIRED"


# ---------------------------------------------------------------------
# POST /chat/sessions/{id}/turns/stream
# ---------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stream_bad_token_returns_401(client_and_handler, monkeypatch):
    client, fake, engine = client_and_handler
    from app.api.v1 import _sse as _sse_mod

    async def _bad_token(t):
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "INVALID_TOKEN", "message": "bad"}},
        )

    monkeypatch.setattr(_sse_mod, "verify_token", _bad_token)
    session_id = uuid.uuid4()
    resp = await client.post(
        f"/api/v1/chat/sessions/{session_id}/turns/stream?token=bad",
        json={"message": "hi"},
    )
    assert resp.status_code == 401


async def _stub_verify(sub: str, monkeypatch):
    from app.api.v1 import _sse as _sse_mod

    async def _vt(t):
        return {"sub": sub}

    monkeypatch.setattr(_sse_mod, "verify_token", _vt)


@pytest.mark.asyncio
async def test_stream_accepts_authorization_header(
    client_and_handler, monkeypatch
):
    """Header path: FE moved off EventSource and now sends the JWT in
    ``Authorization: Bearer ...``. The endpoint MUST authenticate from
    the header (no ``?token=`` query). Locks the regression where the
    endpoint silently demanded a query-string token and returned 422."""
    client, fake, engine = client_and_handler
    sub = f"sub-{uuid.uuid4()}"
    uid = await _seed_user(engine, sub)
    sid = await _seed_chat_session(engine, uid)
    await _stub_verify(sub, monkeypatch)

    fake.set_stream(
        events=[
            ChatStreamStarted(correlation_id="c", session_id=sid),
            ChatTokenDelta(text="hi"),
            ChatStreamCompleted(
                input_tokens=1,
                output_tokens=1,
                session_turn_count=1,
                summarization_applied=False,
                token_source="model",
                tool_call_count=0,
            ),
        ]
    )

    async with client.stream(
        "POST",
        f"/api/v1/chat/sessions/{sid}/turns/stream",
        json={"message": "hi"},
        headers={"Authorization": "Bearer tok"},
    ) as resp:
        assert resp.status_code == 200


@pytest.mark.asyncio
async def test_stream_missing_token_returns_401(client_and_handler):
    """Neither Authorization header nor ?token= query → 401 MISSING_TOKEN.
    Ensures the new dual-source resolver doesn't accidentally allow
    anonymous access."""
    client, _fake, _engine = client_and_handler
    session_id = uuid.uuid4()
    resp = await client.post(
        f"/api/v1/chat/sessions/{session_id}/turns/stream",
        json={"message": "hi"},
    )
    assert resp.status_code == 401
    body = resp.json()
    assert body["detail"]["error"]["code"] == "MISSING_TOKEN"


@pytest.mark.asyncio
async def test_stream_cross_user_session_returns_404(client_and_handler, monkeypatch):
    client, fake, engine = client_and_handler
    sub = f"sub-{uuid.uuid4()}"
    await _seed_user(engine, sub)
    other_uid = await _seed_user(engine, f"other-{uuid.uuid4()}")
    other_sid = await _seed_chat_session(engine, other_uid)
    await _stub_verify(sub, monkeypatch)

    resp = await client.post(
        f"/api/v1/chat/sessions/{other_sid}/turns/stream?token=tok",
        json={"message": "hi"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_stream_happy_path_frames(client_and_handler, monkeypatch):
    client, fake, engine = client_and_handler
    sub = f"sub-{uuid.uuid4()}"
    uid = await _seed_user(engine, sub)
    sid = await _seed_chat_session(engine, uid)
    await _stub_verify(sub, monkeypatch)

    fake.set_stream(
        events=[
            ChatStreamStarted(correlation_id="c", session_id=sid),
            ChatTokenDelta(text="Hello "),
            ChatTokenDelta(text="there."),
            ChatStreamCompleted(
                input_tokens=10,
                output_tokens=3,
                session_turn_count=1,
                summarization_applied=False,
                token_source="model",
                tool_call_count=0,
            ),
        ]
    )

    async with client.stream(
        "POST",
        f"/api/v1/chat/sessions/{sid}/turns/stream?token=tok",
        json={"message": "hi"},
    ) as resp:
        assert resp.status_code == 200
        body = await _read_sse_body(resp)

    frames = _parse_frames(body)
    names = [f[0] for f in frames if f[0] != "heartbeat"]
    assert names[0] == "chat-open"
    assert names[-1] == "chat-complete"
    assert names.count("chat-token") == 2
    # chat-open payload must use camelCase (AC #1 to_camel convention) and
    # carry the two required identifiers.
    open_payload = [f[1] for f in frames if f[0] == "chat-open"][0]
    assert "correlationId" in open_payload
    assert "sessionId" in open_payload
    assert "session_id" not in open_payload  # no snake_case drift
    complete = [f[1] for f in frames if f[0] == "chat-complete"][0]
    # camelCase keys.
    assert "inputTokens" in complete
    assert "toolCallCount" in complete


@pytest.mark.parametrize(
    "exc, expected_reason",
    [
        (ChatInputBlockedError(reason="empty", detail="e"), "guardrail_blocked"),
        (ChatToolLoopExceededError(hops=6), "tool_blocked"),
        (
            ChatGuardrailInterventionError(intervention_kind="grounding"),
            "ungrounded",
        ),
        (ChatTransientError("throttle"), "transient_error"),
    ],
)
@pytest.mark.asyncio
async def test_stream_refusal_maps_reason(
    client_and_handler, monkeypatch, exc, expected_reason
):
    client, fake, engine = client_and_handler
    sub = f"sub-{uuid.uuid4()}"
    uid = await _seed_user(engine, sub)
    sid = await _seed_chat_session(engine, uid)
    await _stub_verify(sub, monkeypatch)

    fake.set_stream(exc=exc)
    async with client.stream(
        "POST",
        f"/api/v1/chat/sessions/{sid}/turns/stream?token=tok",
        json={"message": "hi"},
    ) as resp:
        assert resp.status_code == 200
        body = await _read_sse_body(resp)
    frames = _parse_frames(body)
    refused = [f[1] for f in frames if f[0] == "chat-refused"]
    assert refused
    assert refused[0]["reason"] == expected_reason
    assert refused[0]["correlationId"]


@pytest.mark.asyncio
async def test_stream_rate_limited_surfaces_retry_after(
    client_and_handler, monkeypatch
):
    client, fake, engine = client_and_handler
    sub = f"sub-{uuid.uuid4()}"
    uid = await _seed_user(engine, sub)
    sid = await _seed_chat_session(engine, uid)
    await _stub_verify(sub, monkeypatch)

    fake.set_stream(
        exc=ChatRateLimitedError(correlation_id="x", retry_after_seconds=30)
    )
    async with client.stream(
        "POST",
        f"/api/v1/chat/sessions/{sid}/turns/stream?token=tok",
        json={"message": "hi"},
    ) as resp:
        body = await _read_sse_body(resp)
    refused = [f[1] for f in _parse_frames(body) if f[0] == "chat-refused"][0]
    assert refused["reason"] == "rate_limited"
    assert refused["retryAfterSeconds"] == 30


@pytest.mark.asyncio
async def test_stream_unmapped_exception_emits_terminal_refused_frame(
    client_and_handler, monkeypatch
):
    """AC #5 / AC #14 invariant 2: every stream ends with chat-complete OR
    chat-refused — never a dropped connection. An unmapped runtime error
    (e.g. a DB failure mid-stream) must still produce a terminal
    ``chat-refused`` frame with ``reason=transient_error`` so the UI state
    machine can exit ``streaming``.
    """
    client, fake, engine = client_and_handler
    sub = f"sub-{uuid.uuid4()}"
    uid = await _seed_user(engine, sub)
    sid = await _seed_chat_session(engine, uid)
    await _stub_verify(sub, monkeypatch)

    fake.set_stream(exc=RuntimeError("unexpected: db went away"))
    async with client.stream(
        "POST",
        f"/api/v1/chat/sessions/{sid}/turns/stream?token=tok",
        json={"message": "hi"},
    ) as resp:
        assert resp.status_code == 200
        body = await _read_sse_body(resp)
    frames = _parse_frames(body)
    names = [f[0] for f in frames if f[0] != "heartbeat"]
    assert names[0] == "chat-open"
    assert names[-1] == "chat-refused"
    refused = [f[1] for f in frames if f[0] == "chat-refused"][0]
    assert refused["reason"] == "transient_error"
    assert refused["correlationId"]


# ---------------------------------------------------------------------
# Story 10.6a — Grounding enforcement regression pin (AC #2)
# ---------------------------------------------------------------------


@pytest.mark.asyncio
async def test_chat_route_grounding_returns_chat_refused_ungrounded(
    client_and_handler, monkeypatch
):
    """End-to-end pair for the AC #2 unit-level pin in
    ``test_send_turn_stream::test_grounding_intervention_returns_ungrounded_no_regenerate``.

    Drives a full request through the SSE route with the handler raising
    ``ChatGuardrailInterventionError(intervention_kind="grounding")`` after
    a stream has opened, and asserts the wire envelope matches the
    architecture L1808-L1813 contract:
    ``{"error": "CHAT_REFUSED", "reason": "ungrounded",
       "correlationId": "<uuid>", "retryAfterSeconds": null}``.
    """
    client, fake, engine = client_and_handler
    sub = f"sub-{uuid.uuid4()}"
    uid = await _seed_user(engine, sub)
    sid = await _seed_chat_session(engine, uid)
    await _stub_verify(sub, monkeypatch)

    fake.set_stream(
        exc=ChatGuardrailInterventionError(
            intervention_kind="grounding",
            trace_summary=(
                "contextualGroundingPolicy: groundingScore=0.42 "
                "below threshold 0.85"
            ),
        )
    )
    async with client.stream(
        "POST",
        f"/api/v1/chat/sessions/{sid}/turns/stream?token=tok",
        json={"message": "How much did I spend on cigars?"},
    ) as resp:
        assert resp.status_code == 200
        body = await _read_sse_body(resp)

    frames = _parse_frames(body)
    names = [f[0] for f in frames if f[0] != "heartbeat"]
    assert names[0] == "chat-open"
    assert names[-1] == "chat-refused"

    refused = [f[1] for f in frames if f[0] == "chat-refused"][0]
    # Architecture L1808-L1813 envelope contract.
    assert refused["error"] == "CHAT_REFUSED"
    assert refused["reason"] == "ungrounded"
    # correlationId is a UUID string; envelope omits/keeps null retryAfterSeconds.
    assert refused["correlationId"]
    uuid.UUID(refused["correlationId"])  # must parse
    assert refused.get("retryAfterSeconds") is None


@pytest.mark.asyncio
async def test_stream_over_cap_message_returns_422(client_and_handler, monkeypatch):
    client, fake, engine = client_and_handler
    sub = f"sub-{uuid.uuid4()}"
    uid = await _seed_user(engine, sub)
    sid = await _seed_chat_session(engine, uid)
    await _stub_verify(sub, monkeypatch)

    big = "a" * 5000
    resp = await client.post(
        f"/api/v1/chat/sessions/{sid}/turns/stream?token=tok",
        json={"message": big},
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------
# DELETE /chat/sessions/{id}
# ---------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_session_returns_204(client_and_handler):
    client, fake, engine = client_and_handler
    sub = f"sub-{uuid.uuid4()}"
    uid = await _seed_user(engine, sub)
    sid = await _seed_chat_session(engine, uid)
    _set_auth(sub)
    resp = await client.delete(f"/api/v1/chat/sessions/{sid}")
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_delete_session_cross_user_returns_404(client_and_handler):
    client, fake, engine = client_and_handler
    sub = f"sub-{uuid.uuid4()}"
    await _seed_user(engine, sub)
    other_uid = await _seed_user(engine, f"other-{uuid.uuid4()}")
    other_sid = await _seed_chat_session(engine, other_uid)
    _set_auth(sub)
    resp = await client.delete(f"/api/v1/chat/sessions/{other_sid}")
    assert resp.status_code == 404


# ---------------------------------------------------------------------
# Story 10.6b — chat-citations SSE frame
# ---------------------------------------------------------------------


def _citation_set():
    from datetime import date

    from app.agents.chat.citations import (
        CategoryCitation,
        ProfileFieldCitation,
        RagDocCitation,
        TransactionCitation,
    )

    return (
        TransactionCitation(
            id=uuid.uuid4(),
            booked_at=date(2026, 3, 14),
            description="Coffee Shop",
            amount_kopiykas=-8500,
            currency="UAH",
            category_code="groceries",
            label="Coffee Shop · 2026-03-14",
        ),
        CategoryCitation(code="groceries", label="Groceries"),
        ProfileFieldCitation(
            field="monthly_expenses_kopiykas",
            value=4_530_000,
            currency="UAH",
            as_of=date(2026, 4, 1),
            label="Monthly expenses (Apr 2026)",
        ),
        RagDocCitation(
            source_id="en/emergency-fund",
            title="en/emergency-fund",
            snippet="An emergency fund covers …",
            similarity=0.83,
            label="en/emergency-fund",
        ),
    )


@pytest.mark.asyncio
async def test_chat_route_emits_chat_citations_frame(
    client_and_handler, monkeypatch
):
    from app.agents.chat.stream_events import ChatCitationsAttached

    client, fake, engine = client_and_handler
    sub = f"sub-{uuid.uuid4()}"
    uid = await _seed_user(engine, sub)
    sid = await _seed_chat_session(engine, uid)
    await _stub_verify(sub, monkeypatch)

    citations = _citation_set()
    fake.set_stream(
        events=[
            ChatStreamStarted(correlation_id="c", session_id=sid),
            ChatTokenDelta(text="Hello"),
            ChatCitationsAttached(citations=citations),
            ChatStreamCompleted(
                input_tokens=1,
                output_tokens=1,
                session_turn_count=1,
                summarization_applied=False,
                token_source="model",
                tool_call_count=1,
            ),
        ]
    )
    async with client.stream(
        "POST",
        f"/api/v1/chat/sessions/{sid}/turns/stream?token=tok",
        json={"message": "hi"},
    ) as resp:
        body = await _read_sse_body(resp)
    frames = _parse_frames(body)
    names = [f[0] for f in frames if f[0] != "heartbeat"]
    assert names.count("chat-citations") == 1
    last_token_idx = max(i for i, f in enumerate(frames) if f[0] == "chat-token")
    cit_idx = next(i for i, f in enumerate(frames) if f[0] == "chat-citations")
    complete_idx = next(i for i, f in enumerate(frames) if f[0] == "chat-complete")
    assert last_token_idx < cit_idx < complete_idx


@pytest.mark.asyncio
async def test_chat_route_no_chat_citations_frame_when_empty(
    client_and_handler, monkeypatch
):
    client, fake, engine = client_and_handler
    sub = f"sub-{uuid.uuid4()}"
    uid = await _seed_user(engine, sub)
    sid = await _seed_chat_session(engine, uid)
    await _stub_verify(sub, monkeypatch)

    fake.set_stream(
        events=[
            ChatStreamStarted(correlation_id="c", session_id=sid),
            ChatTokenDelta(text="Hello"),
            ChatStreamCompleted(
                input_tokens=1,
                output_tokens=1,
                session_turn_count=1,
                summarization_applied=False,
                token_source="model",
                tool_call_count=0,
            ),
        ]
    )
    async with client.stream(
        "POST",
        f"/api/v1/chat/sessions/{sid}/turns/stream?token=tok",
        json={"message": "hi"},
    ) as resp:
        body = await _read_sse_body(resp)
    frames = _parse_frames(body)
    assert not any(f[0] == "chat-citations" for f in frames)


@pytest.mark.asyncio
async def test_chat_route_chat_citations_payload_is_camel_case(
    client_and_handler, monkeypatch
):
    from app.agents.chat.stream_events import ChatCitationsAttached

    client, fake, engine = client_and_handler
    sub = f"sub-{uuid.uuid4()}"
    uid = await _seed_user(engine, sub)
    sid = await _seed_chat_session(engine, uid)
    await _stub_verify(sub, monkeypatch)

    citations = _citation_set()
    fake.set_stream(
        events=[
            ChatStreamStarted(correlation_id="c", session_id=sid),
            ChatTokenDelta(text="x"),
            ChatCitationsAttached(citations=citations),
            ChatStreamCompleted(
                input_tokens=1,
                output_tokens=1,
                session_turn_count=1,
                summarization_applied=False,
                token_source="model",
                tool_call_count=1,
            ),
        ]
    )
    async with client.stream(
        "POST",
        f"/api/v1/chat/sessions/{sid}/turns/stream?token=tok",
        json={"message": "hi"},
    ) as resp:
        body = await _read_sse_body(resp)
    frames = _parse_frames(body)
    cit_payload = next(f[1] for f in frames if f[0] == "chat-citations")
    serialized = json.dumps(cit_payload)
    # camelCase keys present.
    for key in ("bookedAt", "amountKopiykas", "categoryCode", "sourceId", "asOf"):
        assert key in serialized, f"missing camelCase key: {key}"
    # snake_case variants must not appear.
    for snake in ("booked_at", "amount_kopiykas", "category_code", "source_id", "as_of"):
        assert snake not in serialized, f"snake_case key leaked: {snake}"
