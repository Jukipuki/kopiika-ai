"""Story 10.5 AC #11 — ChatSessionHandler.send_turn_stream tests."""

from __future__ import annotations

import os
import tempfile
import uuid
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession as SQLModelAsyncSession

from app.agents.chat.chat_backend import (
    BackendStreamDone,
    BackendTokenDelta,
    BackendToolHop,
    ChatBackend,
    ChatGuardrailInterventionError,
    ChatTransientError,
)
from app.agents.chat.input_validator import ChatInputBlockedError
from app.agents.chat.session_handler import ChatSessionHandler
from app.agents.chat.stream_events import (
    ChatStreamCompleted,
    ChatTokenDelta,
    ChatToolHopCompleted,
    ChatToolHopStarted,
)
from app.agents.chat.tools.tool_errors import ChatToolLoopExceededError
from app.core.consent import (
    CONSENT_TYPE_CHAT_PROCESSING,
    CURRENT_CHAT_CONSENT_VERSION,
)
from app.models.chat_message import ChatMessage
from app.models.user import User
from app.services import consent_service


@pytest_asyncio.fixture
async def fk_engine():
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")

    @event.listens_for(engine.sync_engine, "connect")
    def _set_pragma(dbapi_conn, _):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys = ON")
        cur.close()

    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)
    await engine.dispose()
    os.unlink(db_path)


@pytest_asyncio.fixture
async def consented_user(fk_engine):
    async with SQLModelAsyncSession(fk_engine, expire_on_commit=False) as s:
        user = User(
            cognito_sub=f"st-{uuid.uuid4()}",
            email=f"st-{uuid.uuid4()}@e.com",
            is_verified=True,
        )
        s.add(user)
        await s.commit()
        await consent_service.grant_consent(
            session=s,
            user=user,
            consent_type=CONSENT_TYPE_CHAT_PROCESSING,
            version=CURRENT_CHAT_CONSENT_VERSION,
            locale="en",
            ip=None,
            user_agent=None,
        )
        yield user


class _StreamBackend(ChatBackend):
    """ChatBackend where ``invoke_stream`` yields a canned sequence."""

    def __init__(self, events_or_exc):
        self._events_or_exc = events_or_exc
        self.create_remote_session = AsyncMock(side_effect=lambda i: f"ac-{i}")
        self.terminate_remote_session = AsyncMock(return_value=None)
        self.invoke = AsyncMock()

    async def create_remote_session(self, db_session_id):  # type: ignore[override]
        raise NotImplementedError

    async def invoke(self, **_kwargs):  # type: ignore[override]
        raise NotImplementedError

    async def terminate_remote_session(self, _id):  # type: ignore[override]
        raise NotImplementedError

    async def invoke_stream(self, **_kwargs):  # type: ignore[override]
        if isinstance(self._events_or_exc, Exception):
            raise self._events_or_exc
        for ev in self._events_or_exc:
            if isinstance(ev, Exception):
                raise ev
            yield ev


def _make_tool_result(*, tool_name="get_transactions", ok=True):
    # Build a minimal ToolResult-like object the handler accepts for
    # persistence (_serialize_tool_call uses getattr fall-throughs).
    from types import SimpleNamespace

    return SimpleNamespace(
        tool_name=tool_name,
        ok=ok,
        payload={"rows": []},
        error_kind=None,
        elapsed_ms=12,
        tool_use_id="t-1",
    )


@pytest.fixture(autouse=True)
def _reset_canary_cache():
    from app.agents.chat.canaries import _reset_canary_cache_for_tests

    _reset_canary_cache_for_tests()
    yield
    _reset_canary_cache_for_tests()


async def _collect(agen):
    out = []
    async for e in agen:
        out.append(e)
    return out


@pytest.mark.asyncio
async def test_happy_path_zero_tool_hops(fk_engine, consented_user):
    events = [
        BackendTokenDelta(text="Hello, "),
        BackendTokenDelta(text="world."),
        BackendStreamDone(
            input_tokens=20, output_tokens=5, token_source="model", tool_calls=()
        ),
    ]
    backend = _StreamBackend(events)
    handler = ChatSessionHandler(backend)

    async with SQLModelAsyncSession(fk_engine, expire_on_commit=False) as db:
        handle = await handler.create_session(db, consented_user)
        emitted = await _collect(
            handler.send_turn_stream(db, handle, "Hi.", correlation_id="c1")
        )

    types = [type(e).__name__ for e in emitted]
    assert types[0] == "ChatStreamStarted"
    assert types[-1] == "ChatStreamCompleted"
    deltas = [e for e in emitted if isinstance(e, ChatTokenDelta)]
    assert len(deltas) == 2
    completed = emitted[-1]
    assert isinstance(completed, ChatStreamCompleted)
    assert completed.tool_call_count == 0

    async with SQLModelAsyncSession(fk_engine) as db:
        rows = (
            await db.exec(
                select(ChatMessage).where(ChatMessage.session_id == handle.db_session_id)
            )
        ).all()
    roles = sorted(r[0].role for r in rows)
    assert roles == ["assistant", "user"]
    assistant_row = next(r[0] for r in rows if r[0].role == "assistant")
    assert assistant_row.content == "Hello, world."


@pytest.mark.asyncio
async def test_tool_hop_turn_yields_tool_hop_events_and_persists_tool_rows(
    fk_engine, consented_user
):
    tool_res = _make_tool_result()
    events = [
        BackendToolHop(tool_name="get_transactions", hop_index=1, ok=True, result=tool_res),
        BackendTokenDelta(text="You spent $42."),
        BackendStreamDone(
            input_tokens=30,
            output_tokens=7,
            token_source="model",
            tool_calls=(tool_res,),
        ),
    ]
    backend = _StreamBackend(events)
    handler = ChatSessionHandler(backend)

    async with SQLModelAsyncSession(fk_engine, expire_on_commit=False) as db:
        handle = await handler.create_session(db, consented_user)
        emitted = await _collect(
            handler.send_turn_stream(db, handle, "?", correlation_id="c2")
        )

    assert any(isinstance(e, ChatToolHopStarted) for e in emitted)
    assert any(isinstance(e, ChatToolHopCompleted) for e in emitted)

    async with SQLModelAsyncSession(fk_engine) as db:
        rows = (
            await db.exec(
                select(ChatMessage)
                .where(ChatMessage.session_id == handle.db_session_id)
                .order_by(ChatMessage.created_at)
            )
        ).all()
    roles = [r[0].role for r in rows]
    # user, tool, assistant order (tool row persisted before assistant).
    assert roles == ["user", "tool", "assistant"]


@pytest.mark.asyncio
async def test_input_blocked_persists_user_with_guardrail_blocked_no_tokens(
    fk_engine, consented_user
):
    # Empty input triggers ChatInputBlockedError at Step 1.
    backend = _StreamBackend([])
    handler = ChatSessionHandler(backend)
    async with SQLModelAsyncSession(fk_engine, expire_on_commit=False) as db:
        handle = await handler.create_session(db, consented_user)
        with pytest.raises(ChatInputBlockedError):
            await _collect(
                handler.send_turn_stream(db, handle, "   ", correlation_id="c3")
            )

    async with SQLModelAsyncSession(fk_engine) as db:
        rows = (
            await db.exec(
                select(ChatMessage).where(ChatMessage.session_id == handle.db_session_id)
            )
        ).all()
    user_row = next(r[0] for r in rows if r[0].role == "user")
    assert user_row.guardrail_action == "blocked"


@pytest.mark.asyncio
async def test_tool_loop_exceeded_persists_partial_tool_rows_no_assistant(
    fk_engine, consented_user
):
    tool_res = _make_tool_result()
    err = ChatToolLoopExceededError(hops=6, last_tool_name="x")
    err.tool_calls_so_far = (tool_res, tool_res)
    events = [
        BackendToolHop(tool_name="x", hop_index=1, ok=True, result=tool_res),
        err,
    ]
    backend = _StreamBackend(events)
    handler = ChatSessionHandler(backend)

    async with SQLModelAsyncSession(fk_engine, expire_on_commit=False) as db:
        handle = await handler.create_session(db, consented_user)
        with pytest.raises(ChatToolLoopExceededError):
            await _collect(
                handler.send_turn_stream(db, handle, "hello", correlation_id="c4")
            )

    async with SQLModelAsyncSession(fk_engine) as db:
        rows = (
            await db.exec(
                select(ChatMessage).where(ChatMessage.session_id == handle.db_session_id)
            )
        ).all()
    roles = sorted(r[0].role for r in rows)
    assert "assistant" not in roles
    assert "tool" in roles


@pytest.mark.asyncio
async def test_guardrail_intervention_grounding_no_assistant_row(
    fk_engine, consented_user
):
    exc = ChatGuardrailInterventionError(intervention_kind="grounding")
    events = [BackendTokenDelta(text="partial"), exc]
    backend = _StreamBackend(events)
    handler = ChatSessionHandler(backend)

    async with SQLModelAsyncSession(fk_engine, expire_on_commit=False) as db:
        handle = await handler.create_session(db, consented_user)
        with pytest.raises(ChatGuardrailInterventionError):
            await _collect(
                handler.send_turn_stream(db, handle, "hi", correlation_id="c5")
            )

    async with SQLModelAsyncSession(fk_engine) as db:
        rows = (
            await db.exec(
                select(ChatMessage).where(ChatMessage.session_id == handle.db_session_id)
            )
        ).all()
    roles = [r[0].role for r in rows]
    assert "assistant" not in roles


@pytest.mark.asyncio
async def test_transient_error_no_assistant_row(fk_engine, consented_user):
    events = [ChatTransientError("throttled")]
    backend = _StreamBackend(events)
    handler = ChatSessionHandler(backend)
    async with SQLModelAsyncSession(fk_engine, expire_on_commit=False) as db:
        handle = await handler.create_session(db, consented_user)
        with pytest.raises(ChatTransientError):
            await _collect(
                handler.send_turn_stream(db, handle, "hi", correlation_id="c6")
            )
