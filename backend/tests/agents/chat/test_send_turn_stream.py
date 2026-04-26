"""Story 10.5 AC #11 — ChatSessionHandler.send_turn_stream tests.

Story 10.5a appends finalizer-path coverage (i)–(ix) at the bottom of this
file. The Story-10.5 tests above remain the regression pins for the four
terminal branches; (iii) refactors the original
``test_guardrail_intervention_grounding_no_assistant_row`` test to match
AC #3's behavior change (intervention with non-empty accumulated_text now
delegates persistence to the finalizer).
"""

from __future__ import annotations

import asyncio
import logging
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

from app.agents.chat.canaries import _DEV_FALLBACK_CANARIES
from app.agents.chat.canary_detector import ChatPromptLeakDetectedError
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


@pytest.fixture(autouse=True)
def _app_logger_propagates_for_caplog():
    """The 'app' logger has propagate=False under production logging setup;
    caplog attaches to the root logger so records never reach it. Temporarily
    flip propagation during tests so caplog assertions are meaningful.
    """
    lg = logging.getLogger("app")
    prev = lg.propagate
    lg.propagate = True
    try:
        yield
    finally:
        lg.propagate = prev


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
async def test_transient_error_no_assistant_row(fk_engine, consented_user):
    # ChatTransientError raised on the FIRST iteration (before any deltas):
    # accumulated_text is empty, so the finalizer writes nothing for the
    # assistant role. tool_results is also empty. The finalizer DOES run
    # (no terminal branch handles ChatTransientError), bumping
    # last_active_at — this is the "best-effort persist anything we have"
    # contract from Story 10.5a AC #2.
    events = [ChatTransientError("throttled")]
    backend = _StreamBackend(events)
    handler = ChatSessionHandler(backend)
    async with SQLModelAsyncSession(fk_engine, expire_on_commit=False) as db:
        handle = await handler.create_session(db, consented_user)
        with pytest.raises(ChatTransientError):
            await _collect(
                handler.send_turn_stream(db, handle, "hi", correlation_id="c6")
            )

    async with SQLModelAsyncSession(fk_engine) as db:
        rows = (
            await db.exec(
                select(ChatMessage).where(ChatMessage.session_id == handle.db_session_id)
            )
        ).all()
    roles = [r[0].role for r in rows]
    assert "assistant" not in roles


# ----------------------------------------------------------------------
# Story 10.5a — finalizer-path coverage (AC #5)
# ----------------------------------------------------------------------
#
# These tests exercise the outer try/finally + _finalized gate. They run
# against the same _StreamBackend / _HangingStreamBackend fixtures the
# Story-10.5 tests above use. Each test is keyed to a sub-bullet of AC #5
# (i)–(ix). The existing tests above act as regression pins for the four
# terminal branches (happy-path, canary-leak, tool-abort, intervention)
# — they MUST continue to pass after 10.5a (TD-108 + TD-109 short-term).


class _HangingStreamBackend(ChatBackend):
    """``invoke_stream`` yields the canned events then awaits forever.

    Used by AC #5 (i), (ii), (vii) to simulate the disconnect path: the
    test drives the agen through the deltas, then calls ``agen.aclose()``
    which fires ``GeneratorExit`` into the handler's outer ``try/finally``.
    Without the hang, ``BackendStreamDone`` would fall through to the
    happy-path Step 5/6 sequence — the finalizer body would never run.
    """

    def __init__(self, deltas):
        self._deltas = deltas
        self.create_remote_session = AsyncMock(side_effect=lambda i: f"ac-{i}")
        self.terminate_remote_session = AsyncMock(return_value=None)
        self.invoke = AsyncMock()
        self.hang_event = asyncio.Event()  # never set; await blocks forever

    async def create_remote_session(self, db_session_id):  # type: ignore[override]
        raise NotImplementedError

    async def invoke(self, **_kwargs):  # type: ignore[override]
        raise NotImplementedError

    async def terminate_remote_session(self, _id):  # type: ignore[override]
        raise NotImplementedError

    async def invoke_stream(self, **_kwargs):  # type: ignore[override]
        for d in self._deltas:
            yield d
        # Hang until the test calls aclose() on the outer agen, which
        # cancels this coroutine via GeneratorExit propagation.
        await self.hang_event.wait()


async def _drain_until_n_token_deltas(agen, n: int):
    """Pull events from ``agen`` until ``n`` ``ChatTokenDelta``s have arrived.

    Helper for the disconnect tests — we want all canned deltas accumulated
    before triggering aclose() so the finalizer sees the full
    ``accumulated_text``.
    """
    seen = 0
    events = []
    while seen < n:
        e = await agen.__anext__()
        events.append(e)
        if isinstance(e, ChatTokenDelta):
            seen += 1
    return events


@pytest.mark.asyncio
async def test_disconnect_mid_stream_persists_assistant_row(fk_engine, consented_user, caplog):
    # AC #5 (i): disconnect mid-token-stream → assistant row persisted
    # with no guardrail flag, no canary log, last_active_at bumped.
    deltas = [BackendTokenDelta(text="hello "), BackendTokenDelta(text="world "), BackendTokenDelta(text="!")]
    backend = _HangingStreamBackend(deltas)
    handler = ChatSessionHandler(backend)

    async with SQLModelAsyncSession(fk_engine, expire_on_commit=False) as db:
        handle = await handler.create_session(db, consented_user)
        # Capture pre-stream last_active_at for the bump assertion.
        from app.models.chat_session import ChatSession as _CS

        pre_last_active = (
            await db.exec(select(_CS).where(_CS.id == handle.db_session_id))
        ).one()[0].last_active_at

        agen = handler.send_turn_stream(db, handle, "Hi.", correlation_id="ci")
        with caplog.at_level(logging.INFO):
            await _drain_until_n_token_deltas(agen, 3)
            await agen.aclose()

    async with SQLModelAsyncSession(fk_engine) as db:
        rows = (
            await db.exec(
                select(ChatMessage).where(ChatMessage.session_id == handle.db_session_id)
            )
        ).all()
        from app.models.chat_session import ChatSession as _CS2

        cs_post = (
            await db.exec(select(_CS2).where(_CS2.id == handle.db_session_id))
        ).one()[0]

    assistants = [r[0] for r in rows if r[0].role == "assistant"]
    assert len(assistants) == 1
    assert assistants[0].content == "hello world !"
    assert assistants[0].guardrail_action != "blocked"
    # Column default is an empty JSON object, not NULL — the absence of a
    # filter_source key is the signal of a clean partial write.
    assert "filter_source" not in (assistants[0].redaction_flags or {})
    assert cs_post.last_active_at != pre_last_active
    # No ChatStreamCompleted (peer is gone) + no canary leak.
    assert not any(r.message == "chat.canary.leaked" for r in caplog.records)
    assert not any(r.message == "chat.stream.finalizer_failed" for r in caplog.records)


@pytest.mark.asyncio
async def test_disconnect_with_canary_in_accumulated_text_emits_blocked_row(
    fk_engine, consented_user, caplog
):
    # AC #5 (ii): canary in accumulated_text on disconnect path →
    # blocked row + chat.canary.leaked ERROR with finalizer_path=True.
    canary = _DEV_FALLBACK_CANARIES[0]
    deltas = [
        BackendTokenDelta(text="here is the secret: "),
        BackendTokenDelta(text=canary),
        BackendTokenDelta(text=" ok?"),
    ]
    backend = _HangingStreamBackend(deltas)
    handler = ChatSessionHandler(backend)

    async with SQLModelAsyncSession(fk_engine, expire_on_commit=False) as db:
        handle = await handler.create_session(db, consented_user)
        agen = handler.send_turn_stream(db, handle, "Hi.", correlation_id="cii")
        with caplog.at_level(logging.ERROR):
            await _drain_until_n_token_deltas(agen, 3)
            await agen.aclose()

    async with SQLModelAsyncSession(fk_engine) as db:
        rows = (
            await db.exec(
                select(ChatMessage).where(ChatMessage.session_id == handle.db_session_id)
            )
        ).all()
    assistants = [r[0] for r in rows if r[0].role == "assistant"]
    assert len(assistants) == 1
    assert assistants[0].guardrail_action == "blocked"
    assert assistants[0].redaction_flags["filter_source"] == "canary_detector"
    assert "canary_slot" in assistants[0].redaction_flags
    assert "canary_prefix" in assistants[0].redaction_flags
    leak_logs = [r for r in caplog.records if r.message == "chat.canary.leaked"]
    assert len(leak_logs) == 1
    assert getattr(leak_logs[0], "finalizer_path", False) is True


@pytest.mark.asyncio
async def test_intervention_with_prior_accumulated_text_finalizer_persists(
    fk_engine, consented_user, caplog
):
    # AC #5 (iii) + AC #3 behavior change: intervention on a trailing
    # chunk after deltas already streamed → finalizer persists assistant
    # row, intervention propagates, intervened-INFO log still fires once.
    exc = ChatGuardrailInterventionError(intervention_kind="content_filter")
    events = [
        BackendTokenDelta(text="some text"),
        BackendTokenDelta(text="some text"),
        exc,
    ]
    backend = _StreamBackend(events)
    handler = ChatSessionHandler(backend)

    async with SQLModelAsyncSession(fk_engine, expire_on_commit=False) as db:
        handle = await handler.create_session(db, consented_user)
        with caplog.at_level(logging.INFO):
            with pytest.raises(ChatGuardrailInterventionError):
                await _collect(
                    handler.send_turn_stream(db, handle, "hi", correlation_id="ciii")
                )

    async with SQLModelAsyncSession(fk_engine) as db:
        rows = (
            await db.exec(
                select(ChatMessage).where(ChatMessage.session_id == handle.db_session_id)
            )
        ).all()
    assistants = [r[0] for r in rows if r[0].role == "assistant"]
    assert len(assistants) == 1
    assert assistants[0].content == "some textsome text"
    assert assistants[0].guardrail_action != "blocked"
    intervened = [r for r in caplog.records if r.message == "chat.stream.guardrail_intervened"]
    assert len(intervened) == 1
    assert not any(r.message == "chat.canary.leaked" for r in caplog.records)


@pytest.mark.asyncio
async def test_intervention_with_prior_accumulated_text_canary_embedded(
    fk_engine, consented_user, caplog
):
    # AC #5 (iii) canary-embedded sub-case: intervention on trailing chunk
    # AFTER the model has emitted a canary mid-stream → finalizer F.1 fires
    # chat.canary.leaked with finalizer_path=True AND persists a blocked row;
    # original ChatGuardrailInterventionError still propagates.
    canary = _DEV_FALLBACK_CANARIES[0]
    exc = ChatGuardrailInterventionError(intervention_kind="content_filter")
    events = [
        BackendTokenDelta(text="leaking: "),
        BackendTokenDelta(text=canary),
        exc,
    ]
    backend = _StreamBackend(events)
    handler = ChatSessionHandler(backend)

    async with SQLModelAsyncSession(fk_engine, expire_on_commit=False) as db:
        handle = await handler.create_session(db, consented_user)
        with caplog.at_level(logging.ERROR):
            with pytest.raises(ChatGuardrailInterventionError):
                await _collect(
                    handler.send_turn_stream(
                        db, handle, "hi", correlation_id="ciii-canary"
                    )
                )

    async with SQLModelAsyncSession(fk_engine) as db:
        rows = (
            await db.exec(
                select(ChatMessage).where(ChatMessage.session_id == handle.db_session_id)
            )
        ).all()
    assistants = [r[0] for r in rows if r[0].role == "assistant"]
    assert len(assistants) == 1
    assert assistants[0].guardrail_action == "blocked"
    assert assistants[0].redaction_flags["filter_source"] == "canary_detector"
    leak_logs = [r for r in caplog.records if r.message == "chat.canary.leaked"]
    assert len(leak_logs) == 1
    assert getattr(leak_logs[0], "finalizer_path", False) is True


@pytest.mark.asyncio
async def test_finalizer_persists_tool_rows_before_assistant_row(
    fk_engine, consented_user
):
    # Pins H2 from the 10-5a code review: finalizer-path persistence must
    # match happy-path ordering — tool rows precede the assistant row by
    # created_at. Exercises ChatGuardrailInterventionError on a trailing
    # chunk after BOTH a tool hop AND token deltas have streamed.
    tool_res = _make_tool_result()
    exc = ChatGuardrailInterventionError(intervention_kind="content_filter")
    events = [
        BackendToolHop(tool_name="get_transactions", hop_index=1, ok=True, result=tool_res),
        BackendTokenDelta(text="answer-fragment"),
        exc,
    ]
    backend = _StreamBackend(events)
    handler = ChatSessionHandler(backend)

    async with SQLModelAsyncSession(fk_engine, expire_on_commit=False) as db:
        handle = await handler.create_session(db, consented_user)
        with pytest.raises(ChatGuardrailInterventionError):
            await _collect(
                handler.send_turn_stream(db, handle, "hi", correlation_id="cordering")
            )

    async with SQLModelAsyncSession(fk_engine) as db:
        rows = (
            await db.exec(
                select(ChatMessage)
                .where(ChatMessage.session_id == handle.db_session_id)
                .order_by(ChatMessage.created_at)
            )
        ).all()
    roles = [r[0].role for r in rows]
    assert roles == ["user", "tool", "assistant"]


@pytest.mark.asyncio
async def test_intervention_with_empty_accumulated_text_existing_branch_wins(
    fk_engine, consented_user, caplog
):
    # AC #5 (iv) — regression pin for the existing intervention branch.
    # No deltas streamed → behavior unchanged from pre-10.5a: no
    # assistant row, last_active_at bumped exactly once, exception re-raised.
    exc = ChatGuardrailInterventionError(intervention_kind="denied_topic")
    events = [exc]
    backend = _StreamBackend(events)
    handler = ChatSessionHandler(backend)

    async with SQLModelAsyncSession(fk_engine, expire_on_commit=False) as db:
        handle = await handler.create_session(db, consented_user)
        with caplog.at_level(logging.ERROR):
            with pytest.raises(ChatGuardrailInterventionError):
                await _collect(
                    handler.send_turn_stream(db, handle, "hi", correlation_id="civ")
                )

    async with SQLModelAsyncSession(fk_engine) as db:
        rows = (
            await db.exec(
                select(ChatMessage).where(ChatMessage.session_id == handle.db_session_id)
            )
        ).all()
    roles = [r[0].role for r in rows]
    assert "assistant" not in roles
    assert not any(r.message == "chat.stream.finalizer_failed" for r in caplog.records)


@pytest.mark.asyncio
async def test_transient_error_after_partial_deltas_finalizer_persists(
    fk_engine, consented_user
):
    # AC #5 (v): ChatTransientError mid-stream after deltas → finalizer
    # persists assistant row with the accumulated content, no canary log.
    events = [
        BackendTokenDelta(text="partial-1"),
        BackendTokenDelta(text=" partial-2"),
        ChatTransientError("Bedrock throttle"),
    ]
    backend = _StreamBackend(events)
    handler = ChatSessionHandler(backend)

    async with SQLModelAsyncSession(fk_engine, expire_on_commit=False) as db:
        handle = await handler.create_session(db, consented_user)
        with pytest.raises(ChatTransientError):
            await _collect(
                handler.send_turn_stream(db, handle, "hi", correlation_id="cv")
            )

    async with SQLModelAsyncSession(fk_engine) as db:
        rows = (
            await db.exec(
                select(ChatMessage).where(ChatMessage.session_id == handle.db_session_id)
            )
        ).all()
    assistants = [r[0] for r in rows if r[0].role == "assistant"]
    assert len(assistants) == 1
    assert assistants[0].content == "partial-1 partial-2"
    assert assistants[0].guardrail_action != "blocked"


@pytest.mark.asyncio
async def test_happy_path_finalizer_no_op(fk_engine, consented_user, caplog):
    # AC #5 (vi): happy-path turn → finalizer no-ops; no
    # chat.stream.finalizer_failed regression.
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
        with caplog.at_level(logging.ERROR):
            await _collect(
                handler.send_turn_stream(db, handle, "Hi.", correlation_id="cvi")
            )

    assert not any(r.message == "chat.stream.finalizer_failed" for r in caplog.records)
    async with SQLModelAsyncSession(fk_engine) as db:
        rows = (
            await db.exec(
                select(ChatMessage).where(ChatMessage.session_id == handle.db_session_id)
            )
        ).all()
    # Exactly one assistant row — finalizer must NOT have written a duplicate.
    assistants = [r[0] for r in rows if r[0].role == "assistant"]
    assert len(assistants) == 1


@pytest.mark.asyncio
async def test_finalizer_db_failure_logs_finalizer_failed(
    fk_engine, consented_user, caplog
):
    # AC #5 (vii): patch db.commit to fail on the finalizer's call.
    # The original GeneratorExit-driven path triggers the finalizer's
    # commit; that commit raises RuntimeError → chat.stream.finalizer_failed
    # ERROR logged, original exception (GeneratorExit) propagates out as
    # the agen closing — NOT the RuntimeError.
    deltas = [BackendTokenDelta(text="hello")]
    backend = _HangingStreamBackend(deltas)
    handler = ChatSessionHandler(backend)

    async with SQLModelAsyncSession(fk_engine, expire_on_commit=False) as db:
        handle = await handler.create_session(db, consented_user)
        # Wrap commit so it succeeds for Step 0 user-row, then fails on
        # the finalizer's commit (call #2 in this fixture's lifecycle).
        original_commit = db.commit
        commit_calls = {"n": 0}

        async def _flaky_commit():
            commit_calls["n"] += 1
            if commit_calls["n"] >= 2:
                raise RuntimeError("db pool exhausted")
            await original_commit()

        db.commit = _flaky_commit  # type: ignore[method-assign]

        agen = handler.send_turn_stream(db, handle, "Hi.", correlation_id="cvii")
        with caplog.at_level(logging.ERROR):
            await _drain_until_n_token_deltas(agen, 1)
            # aclose drives GeneratorExit → finalizer → flaky_commit raises
            # → handler logs chat.stream.finalizer_failed and swallows so
            # the original GeneratorExit propagates from aclose() cleanly.
            # Explicit assertion: aclose() must NOT surface RuntimeError —
            # if the bare-Exception envelope ever regressed to
            # ``except BaseException`` (or were removed), the RuntimeError
            # would propagate here instead.
            close_result = await agen.aclose()
            assert close_result is None

    finalizer_fail = [
        r for r in caplog.records if r.message == "chat.stream.finalizer_failed"
    ]
    assert len(finalizer_fail) == 1
    assert getattr(finalizer_fail[0], "error_class", None) == "RuntimeError"
    assert getattr(finalizer_fail[0], "accumulated_char_len", 0) > 0


# ----------------------------------------------------------------------
# Story 10.6a — Grounding enforcement regression pin (AC #2)
# ----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_grounding_intervention_returns_ungrounded_no_regenerate(
    fk_engine, consented_user, caplog, monkeypatch
):
    # Story 10.6a AC #2 — the architecture L1711 no-regenerate contract.
    # Mocks ``invoke_stream`` to yield two text deltas and then raise
    # ``ChatGuardrailInterventionError(intervention_kind="grounding")``.
    # Asserts:
    #  (a) the exception propagates out of ``send_turn_stream`` — the API
    #      layer at chat.py:193-199 translates it to CHAT_REFUSED with
    #      reason=ungrounded;
    #  (b) ``ChatBackend.invoke_stream`` was called *exactly once* — no
    #      retry / regenerate / second backend call followed the
    #      intervention (the negative regression pin);
    #  (c) the persisted assistant row matches Story 10.5a's deferred-
    #      finalizer clean-row contract — single ``role='assistant'`` row
    #      with the accumulated pre-intervention text, NO
    #      ``guardrail_action='blocked'`` flag, NO ``filter_source`` in
    #      ``redaction_flags`` (the block signal lives on the SSE wire
    #      envelope translated by chat.py:193-199, not in DB columns);
    #  (d) ``chat.stream.guardrail_intervened`` INFO log fires exactly once
    #      with ``intervention_kind='grounding'`` in extra.
    exc = ChatGuardrailInterventionError(
        intervention_kind="grounding",
        trace_summary=(
            "contextualGroundingPolicy: groundingScore=0.42 below threshold 0.85"
        ),
    )
    events = [
        BackendTokenDelta(text="The user spent "),
        BackendTokenDelta(text="The user spent "),
        BackendTokenDelta(text="$10,000 on cigars"),
        exc,
    ]
    backend = _StreamBackend(events)
    handler = ChatSessionHandler(backend)

    invoke_call_count = {"n": 0}
    original_invoke = backend.invoke_stream

    async def _counting_invoke_stream(**kwargs):
        invoke_call_count["n"] += 1
        async for ev in original_invoke(**kwargs):
            yield ev

    monkeypatch.setattr(backend, "invoke_stream", _counting_invoke_stream)

    async with SQLModelAsyncSession(fk_engine, expire_on_commit=False) as db:
        handle = await handler.create_session(db, consented_user)
        with caplog.at_level(logging.INFO):
            with pytest.raises(ChatGuardrailInterventionError) as ei:
                await _collect(
                    handler.send_turn_stream(
                        db, handle, "How much did I spend on cigars?",
                        correlation_id="cg-pin",
                    )
                )

    assert ei.value.intervention_kind == "grounding"

    # (b) Negative regression pin — no retry / regenerate.
    assert invoke_call_count["n"] == 1, (
        "ChatBackend.invoke_stream must be called exactly once on grounding "
        "intervention — no silent retry / regenerate is permitted "
        "(architecture.md L1711)."
    )

    # (c) Persistence shape — Story 10.5a deferred-finalizer contract:
    # exactly one role='assistant' row with the accumulated pre-intervention
    # text, NO guardrail_action='blocked' flag, NO filter_source. The block
    # signal lives on the SSE wire envelope (translated by the API layer at
    # chat.py:193-199 to reason="ungrounded"), not in DB columns. Mirrors
    # the symmetric content_filter pin at line 516 of this file.
    async with SQLModelAsyncSession(fk_engine) as db:
        rows = (
            await db.exec(
                select(ChatMessage).where(
                    ChatMessage.session_id == handle.db_session_id
                )
            )
        ).all()
    assistants = [r[0] for r in rows if r[0].role == "assistant"]
    assert len(assistants) == 1
    assert assistants[0].guardrail_action != "blocked"
    assert "filter_source" not in (assistants[0].redaction_flags or {})
    assert "$10,000 on cigars" in assistants[0].content

    # (d) Intervention log fires exactly once with intervention_kind="grounding".
    intervened = [
        r for r in caplog.records if r.message == "chat.stream.guardrail_intervened"
    ]
    assert len(intervened) == 1
    assert getattr(intervened[0], "intervention_kind", None) == "grounding"

    # (e) No canary-leak log — the deferred-finalizer canary re-scan ran clean.
    assert not any(r.message == "chat.canary.leaked" for r in caplog.records)


@pytest.mark.asyncio
async def test_canary_leak_happy_path_emits_leaked_log_once(
    fk_engine, consented_user, caplog
):
    # AC #5 (viii) regression pin: ChatPromptLeakDetectedError happy-path
    # — the existing Step-5 branch fires chat.canary.leaked exactly once,
    # the finalizer short-circuits because that branch flipped _finalized.
    canary = _DEV_FALLBACK_CANARIES[0]
    events = [
        BackendTokenDelta(text="leaking: "),
        BackendTokenDelta(text=canary),
        BackendStreamDone(
            input_tokens=10, output_tokens=4, token_source="model", tool_calls=()
        ),
    ]
    backend = _StreamBackend(events)
    handler = ChatSessionHandler(backend)

    async with SQLModelAsyncSession(fk_engine, expire_on_commit=False) as db:
        handle = await handler.create_session(db, consented_user)
        with caplog.at_level(logging.ERROR):
            with pytest.raises(ChatPromptLeakDetectedError):
                await _collect(
                    handler.send_turn_stream(
                        db, handle, "hi", correlation_id="cviii"
                    )
                )

    leak_logs = [r for r in caplog.records if r.message == "chat.canary.leaked"]
    assert len(leak_logs) == 1
    # The Step-5 emission does NOT include finalizer_path=True.
    assert getattr(leak_logs[0], "finalizer_path", False) is False
    async with SQLModelAsyncSession(fk_engine) as db:
        rows = (
            await db.exec(
                select(ChatMessage).where(ChatMessage.session_id == handle.db_session_id)
            )
        ).all()
    assistants = [r[0] for r in rows if r[0].role == "assistant"]
    assert len(assistants) == 1
    assert assistants[0].guardrail_action == "blocked"
