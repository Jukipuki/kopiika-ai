"""Tests for ChatSessionHandler (Story 10.4a Phase A per ADR-0004)."""

from __future__ import annotations

import os
import tempfile
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession as SQLModelAsyncSession

from app.agents.chat import session_handler as sh
from app.agents.chat.chat_backend import (
    ChatBackend,
    ChatInvocationResult,
    ChatProviderNotSupportedError,
    ChatSessionCreationError,
    ChatSessionTerminationFailed,
)
from app.agents.chat.session_handler import (
    ChatSessionHandle,
    ChatSessionHandler,
)
from app.core.config import settings
from app.core.consent import (
    CONSENT_TYPE_CHAT_PROCESSING,
    CURRENT_CHAT_CONSENT_VERSION,
)
from app.models.chat_message import ChatMessage
from app.models.chat_session import ChatSession
from app.models.user import User
from app.services import consent_service


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


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
    """A user who has granted current chat_processing consent."""
    async with SQLModelAsyncSession(fk_engine, expire_on_commit=False) as session:
        user = User(
            cognito_sub=f"chat-{uuid.uuid4()}",
            email=f"chat-{uuid.uuid4()}@example.com",
            is_verified=True,
        )
        session.add(user)
        await session.commit()
        await consent_service.grant_consent(
            session=session,
            user=user,
            consent_type=CONSENT_TYPE_CHAT_PROCESSING,
            version=CURRENT_CHAT_CONSENT_VERSION,
            locale="en",
            ip=None,
            user_agent=None,
        )
        yield user


class FakeBackend(ChatBackend):
    """Deterministic ChatBackend — tests wire up AsyncMocks on its methods.

    Concrete overrides just forward to instance-attached AsyncMocks so tests
    can inspect call args.
    """

    def __init__(self):
        self.create_remote_session = AsyncMock(side_effect=lambda db_id: f"ac-{db_id}")
        self.invoke = AsyncMock()
        self.terminate_remote_session = AsyncMock(return_value=None)

    # ABC compliance — instance-attribute mocks above shadow these.
    async def create_remote_session(self, db_session_id):  # type: ignore[override]
        raise NotImplementedError

    async def invoke(self, *, db_session_id, context_messages, user_message):  # type: ignore[override]
        raise NotImplementedError

    async def terminate_remote_session(self, agentcore_session_id):  # type: ignore[override]
        raise NotImplementedError


@pytest.fixture
def fake_backend():
    return FakeBackend()


@pytest.fixture
def handler(fake_backend):
    return ChatSessionHandler(fake_backend)


# ---------------------------------------------------------------------------
# create_session
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_session_happy_path(
    fk_engine, consented_user, handler, fake_backend
):
    async with SQLModelAsyncSession(fk_engine, expire_on_commit=False) as db:
        handle = await handler.create_session(db, consented_user)
    assert isinstance(handle, ChatSessionHandle)
    assert handle.user_id == consented_user.id
    assert handle.agentcore_session_id.startswith("ac-")
    fake_backend.create_remote_session.assert_awaited_once()

    # Row exists in DB
    async with SQLModelAsyncSession(fk_engine) as db:
        result = await db.exec(
            select(ChatSession).where(ChatSession.id == handle.db_session_id)  # type: ignore[arg-type]
        )
        rows = result.all()
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_create_session_compensating_delete_on_backend_failure(
    fk_engine, consented_user, handler, fake_backend
):
    fake_backend.create_remote_session.side_effect = RuntimeError("boom")

    async with SQLModelAsyncSession(fk_engine, expire_on_commit=False) as db:
        with pytest.raises(ChatSessionCreationError):
            await handler.create_session(db, consented_user)

    # No orphan DB row
    async with SQLModelAsyncSession(fk_engine) as db:
        result = await db.exec(
            select(ChatSession).where(ChatSession.user_id == consented_user.id)  # type: ignore[arg-type]
        )
        assert result.all() == []


# ---------------------------------------------------------------------------
# send_turn — happy path + summarization
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_send_turn_happy_path(fk_engine, consented_user, handler, fake_backend):
    fake_backend.invoke.return_value = ChatInvocationResult(
        text="Hello from Sonnet.",
        input_tokens=50,
        output_tokens=8,
        token_source="model",
    )

    async with SQLModelAsyncSession(fk_engine, expire_on_commit=False) as db:
        handle = await handler.create_session(db, consented_user)
        response = await handler.send_turn(db, handle, "Hi, chat.")

    assert response.assistant_message == "Hello from Sonnet."
    assert response.input_tokens == 50
    assert response.output_tokens == 8
    assert response.summarization_applied is False
    assert response.token_source == "model"
    # Both messages persisted
    async with SQLModelAsyncSession(fk_engine) as db:
        result = await db.exec(
            select(ChatMessage).where(ChatMessage.session_id == handle.db_session_id)  # type: ignore[arg-type]
        )
        roles = sorted(row[0].role for row in result.all())
    assert roles == ["assistant", "user"]


@pytest.mark.asyncio
async def test_send_turn_triggers_summarization_at_turn_boundary(
    fk_engine, consented_user, handler, fake_backend, monkeypatch
):
    """At the 20-turn ceiling, summarization fires before the next invoke."""
    monkeypatch.setattr(settings, "CHAT_SESSION_MAX_TURNS", 3)
    monkeypatch.setattr(settings, "CHAT_SESSION_MAX_TOKENS", 10_000)
    monkeypatch.setattr(settings, "CHAT_SUMMARIZATION_KEEP_RECENT_TURNS", 1)

    fake_backend.invoke.return_value = ChatInvocationResult(
        text="ok", input_tokens=1, output_tokens=1, token_source="model"
    )

    async with SQLModelAsyncSession(fk_engine, expire_on_commit=False) as db:
        handle = await handler.create_session(db, consented_user)
        # Seed 3 prior turns directly (user + assistant each) — so the
        # current send_turn arrives at 3 user-turns stored + 1 new user =
        # 4 turns total → well over the configured max_turns=3.
        for i in range(3):
            db.add(
                ChatMessage(
                    session_id=handle.db_session_id, role="user", content=f"u{i}"
                )
            )
            db.add(
                ChatMessage(
                    session_id=handle.db_session_id, role="assistant", content=f"a{i}"
                )
            )
        await db.commit()

        with patch.object(
            handler, "_call_summarizer", new=AsyncMock(return_value="SUMMARY")
        ):
            response = await handler.send_turn(db, handle, "u3")
    assert response.summarization_applied is True

    # A role='system' summary row was persisted.
    async with SQLModelAsyncSession(fk_engine) as db:
        result = await db.exec(
            select(ChatMessage)
            .where(ChatMessage.session_id == handle.db_session_id)  # type: ignore[arg-type]
            .where(ChatMessage.role == "system")
        )
        summaries = result.all()
    assert len(summaries) == 1
    assert summaries[0][0].content == "SUMMARY"


@pytest.mark.asyncio
async def test_send_turn_triggers_summarization_at_token_boundary(
    fk_engine, consented_user, handler, fake_backend, monkeypatch
):
    monkeypatch.setattr(settings, "CHAT_SESSION_MAX_TURNS", 1000)
    monkeypatch.setattr(settings, "CHAT_SESSION_MAX_TOKENS", 5)  # impossible-low
    monkeypatch.setattr(settings, "CHAT_SUMMARIZATION_KEEP_RECENT_TURNS", 1)

    fake_backend.invoke.return_value = ChatInvocationResult(
        text="ok", input_tokens=1, output_tokens=1, token_source="model"
    )

    async with SQLModelAsyncSession(fk_engine, expire_on_commit=False) as db:
        handle = await handler.create_session(db, consented_user)
        # Seed enough content to exceed 5 tokens easily
        db.add(
            ChatMessage(
                session_id=handle.db_session_id,
                role="user",
                content="a long enough message to exceed five tokens",
            )
        )
        db.add(
            ChatMessage(
                session_id=handle.db_session_id,
                role="assistant",
                content="a matching reply with plenty of words",
            )
        )
        await db.commit()

        with patch.object(handler, "_call_summarizer", new=AsyncMock(return_value="S")):
            response = await handler.send_turn(db, handle, "another long message here")
    assert response.summarization_applied is True


@pytest.mark.asyncio
async def test_send_turn_token_bound_without_enough_turns_reports_no_summarization(
    fk_engine, consented_user, handler, fake_backend, monkeypatch
):
    """Token bound tripped but history has fewer than keep_recent turns → no
    summarization possible. ``summarization_applied`` must be False — Story
    10.9 metrics would otherwise count phantom summarizations.
    """
    monkeypatch.setattr(settings, "CHAT_SESSION_MAX_TURNS", 1000)
    monkeypatch.setattr(settings, "CHAT_SESSION_MAX_TOKENS", 1)  # trips on any input
    monkeypatch.setattr(settings, "CHAT_SUMMARIZATION_KEEP_RECENT_TURNS", 10)

    fake_backend.invoke.return_value = ChatInvocationResult(
        text="ok", input_tokens=1, output_tokens=1, token_source="model"
    )

    async with SQLModelAsyncSession(fk_engine, expire_on_commit=False) as db:
        handle = await handler.create_session(db, consented_user)
        response = await handler.send_turn(db, handle, "hello world")
    assert response.summarization_applied is False


@pytest.mark.asyncio
async def test_send_turn_summarization_failure_falls_back_to_drop(
    fk_engine, consented_user, handler, fake_backend, monkeypatch
):
    """Summarization LLM error → drop older turns, emit chat.summarization.failed,
    continue the chat turn. AC #9 fallback-drop semantics.
    """
    monkeypatch.setattr(settings, "CHAT_SESSION_MAX_TURNS", 2)
    monkeypatch.setattr(settings, "CHAT_SESSION_MAX_TOKENS", 10_000)
    monkeypatch.setattr(settings, "CHAT_SUMMARIZATION_KEEP_RECENT_TURNS", 1)

    fake_backend.invoke.return_value = ChatInvocationResult(
        text="ok", input_tokens=1, output_tokens=1, token_source="model"
    )

    async with SQLModelAsyncSession(fk_engine, expire_on_commit=False) as db:
        handle = await handler.create_session(db, consented_user)
        for i in range(3):
            db.add(
                ChatMessage(
                    session_id=handle.db_session_id, role="user", content=f"u{i}"
                )
            )
            db.add(
                ChatMessage(
                    session_id=handle.db_session_id, role="assistant", content=f"a{i}"
                )
            )
        await db.commit()

        with patch.object(
            handler,
            "_call_summarizer",
            new=AsyncMock(side_effect=RuntimeError("llm-fail")),
        ):
            response = await handler.send_turn(db, handle, "u3")

    # Turn still completed — drop-fallback path doesn't raise.
    assert response.assistant_message == "ok"
    assert response.summarization_applied is True

    # No role='system' summary persisted — the fallback is silent-but-logged drop.
    async with SQLModelAsyncSession(fk_engine) as db:
        result = await db.exec(
            select(ChatMessage)
            .where(ChatMessage.session_id == handle.db_session_id)  # type: ignore[arg-type]
            .where(ChatMessage.role == "system")
        )
        assert result.all() == []


# ---------------------------------------------------------------------------
# terminate_session + terminate_all_user_sessions
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_terminate_session_calls_backend(fake_backend, handler):
    handle = ChatSessionHandle(
        db_session_id=uuid.uuid4(),
        agentcore_session_id="ac-x",
        created_at=MagicMock(),
        user_id=uuid.uuid4(),
    )
    await handler.terminate_session(handle)
    fake_backend.terminate_remote_session.assert_awaited_once_with("ac-x")


@pytest.mark.asyncio
async def test_terminate_session_wraps_backend_error(fake_backend, handler):
    fake_backend.terminate_remote_session.side_effect = RuntimeError("boom")
    handle = ChatSessionHandle(
        db_session_id=uuid.uuid4(),
        agentcore_session_id="ac-x",
        created_at=MagicMock(),
        user_id=uuid.uuid4(),
    )
    with pytest.raises(ChatSessionTerminationFailed):
        await handler.terminate_session(handle)


@pytest.mark.asyncio
async def test_terminate_all_user_sessions_iterates_in_series(
    fk_engine, consented_user, handler, fake_backend
):
    # Seed 3 sessions for the user
    async with SQLModelAsyncSession(fk_engine, expire_on_commit=False) as db:
        for _ in range(3):
            db.add(
                ChatSession(
                    user_id=consented_user.id,
                    consent_version_at_creation=CURRENT_CHAT_CONSENT_VERSION,
                )
            )
        await db.commit()

        await handler.terminate_all_user_sessions(db, consented_user)

    assert fake_backend.terminate_remote_session.await_count == 3


@pytest.mark.asyncio
async def test_terminate_all_user_sessions_fail_open_on_backend_error(
    fk_engine, consented_user, handler, fake_backend
):
    fake_backend.terminate_remote_session.side_effect = RuntimeError("boom")
    async with SQLModelAsyncSession(fk_engine, expire_on_commit=False) as db:
        db.add(
            ChatSession(
                user_id=consented_user.id,
                consent_version_at_creation=CURRENT_CHAT_CONSENT_VERSION,
            )
        )
        await db.commit()

        # Does NOT raise — revocation must not be blocked by termination failure.
        await handler.terminate_all_user_sessions(db, consented_user)


# ---------------------------------------------------------------------------
# Non-bedrock provider guards (AC #14)
# ---------------------------------------------------------------------------


def test_get_chat_session_handler_raises_on_non_bedrock(monkeypatch):
    monkeypatch.setattr(settings, "LLM_PROVIDER", "anthropic")
    monkeypatch.setattr(settings, "CHAT_RUNTIME", "direct")
    sh._reset_singleton_for_tests()
    with pytest.raises(ChatProviderNotSupportedError):
        sh.get_chat_session_handler()


def test_get_chat_session_handler_succeeds_on_bedrock(monkeypatch):
    monkeypatch.setattr(settings, "LLM_PROVIDER", "bedrock")
    monkeypatch.setattr(settings, "CHAT_RUNTIME", "direct")
    sh._reset_singleton_for_tests()
    try:
        handler = sh.get_chat_session_handler()
        assert handler is not None
    finally:
        sh._reset_singleton_for_tests()


@pytest.mark.asyncio
async def test_terminate_all_user_sessions_fail_open_wrapper_skips_non_bedrock(
    fk_engine, consented_user, monkeypatch
):
    """consent_service calls this wrapper; non-bedrock deploys must not crash
    revoke_chat_consent. The wrapper catches ChatProviderNotSupportedError
    and logs chat.session.termination_skipped_nonbedrock.
    """
    monkeypatch.setattr(settings, "LLM_PROVIDER", "anthropic")
    monkeypatch.setattr(settings, "CHAT_RUNTIME", "direct")
    sh._reset_singleton_for_tests()
    try:
        async with SQLModelAsyncSession(fk_engine, expire_on_commit=False) as db:
            # Does NOT raise
            await sh.terminate_all_user_sessions_fail_open(db, consented_user)
    finally:
        sh._reset_singleton_for_tests()
