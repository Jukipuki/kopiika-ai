"""Tests for DirectBedrockBackend (Phase A per ADR-0004).

Story 10.4c adds tool-use loop coverage in the same file. The langchain
``ainvoke`` boundary is mocked; no real Bedrock traffic in CI.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from botocore.exceptions import ClientError

from app.agents.chat import chat_backend
from app.agents.chat.chat_backend import (
    ChatConfigurationError,
    ChatProviderNotSupportedError,
    ChatTransientError,
    DirectBedrockBackend,
    MAX_TOOL_HOPS,
)
from app.agents.chat.tools.tool_errors import ChatToolLoopExceededError
from app.core.config import settings
from app.models.chat_message import ChatMessage


@pytest.fixture
def bedrock_env(monkeypatch):
    monkeypatch.setattr(settings, "LLM_PROVIDER", "bedrock")
    yield


def _user_msg(content: str) -> ChatMessage:
    return ChatMessage(session_id=uuid.uuid4(), role="user", content=content)


def _fake_client(ai_msg) -> MagicMock:
    """MagicMock client whose ``bind_tools`` returns the same client so
    ``ainvoke`` can be controlled with a single AsyncMock.
    """
    client = MagicMock()
    client.ainvoke = AsyncMock(return_value=ai_msg)
    client.bind_tools = MagicMock(return_value=client)
    return client


def _fake_client_sequence(msgs) -> MagicMock:
    """MagicMock client that cycles through ``msgs`` across successive ainvoke calls."""
    client = MagicMock()
    client.ainvoke = AsyncMock(side_effect=list(msgs))
    client.bind_tools = MagicMock(return_value=client)
    return client


def _plain_text_ai(content="ok", in_t=1, out_t=1) -> MagicMock:
    ai = MagicMock()
    ai.content = content
    ai.usage_metadata = {"input_tokens": in_t, "output_tokens": out_t}
    ai.tool_calls = []
    return ai


def _tool_use_ai(name="get_transactions", args=None, tc_id="tu_1") -> MagicMock:
    ai = MagicMock()
    ai.content = [{"type": "tool_use", "id": tc_id, "name": name, "input": args or {}}]
    ai.usage_metadata = {"input_tokens": 1, "output_tokens": 1}
    ai.tool_calls = [{"name": name, "args": args or {}, "id": tc_id}]
    return ai


def _invoke_kwargs(**overrides):
    base = {
        "db_session_id": uuid.uuid4(),
        "context_messages": [],
        "user_message": "hi",
        "system_prompt": "sys",
        "user_id": uuid.uuid4(),
        "db": MagicMock(),
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Construction guard (AC #14)
# ---------------------------------------------------------------------------


def test_non_bedrock_provider_raises_on_construction(monkeypatch):
    monkeypatch.setattr(settings, "LLM_PROVIDER", "anthropic")
    with pytest.raises(ChatProviderNotSupportedError) as excinfo:
        DirectBedrockBackend()
    msg = str(excinfo.value)
    assert "LLM_PROVIDER=bedrock" in msg
    assert "Current provider: anthropic" in msg


def test_bedrock_provider_allows_construction(bedrock_env):
    backend = DirectBedrockBackend()
    assert isinstance(backend, DirectBedrockBackend)


# ---------------------------------------------------------------------------
# Region / provider routing
# ---------------------------------------------------------------------------


def test_bedrock_client_built_for_eu_central_1(bedrock_env):
    from app.agents import llm

    with patch("app.agents.llm._build_client") as build:
        build.return_value = MagicMock()
        llm._get_client_for("bedrock", role="chat_default")
        args, _ = build.call_args
        provider_arg, model_arg = args
        assert provider_arg == "bedrock"
        assert ":eu-central-1:" in model_arg
        assert "inference-profile/" in model_arg


# ---------------------------------------------------------------------------
# invoke happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_invoke_places_system_prompt_at_position_zero(bedrock_env):
    from langchain_core.messages import SystemMessage

    fake_client = _fake_client(_plain_text_ai())
    backend = DirectBedrockBackend()
    summary_row = ChatMessage(session_id=uuid.uuid4(), role="system", content="SUMMARY")
    user_row = ChatMessage(session_id=uuid.uuid4(), role="user", content="u1")
    with patch("app.agents.llm._get_client_for", return_value=fake_client):
        with patch("app.agents.llm.record_success"):
            await backend.invoke(
                **_invoke_kwargs(
                    context_messages=[summary_row, user_row],
                    user_message="hey",
                    system_prompt="HARDENED_PROMPT_TEXT",
                )
            )
    lc_messages = fake_client.ainvoke.call_args[0][0]
    assert isinstance(lc_messages[0], SystemMessage)
    assert lc_messages[0].content == "HARDENED_PROMPT_TEXT"
    summary_positions = [
        i for i, m in enumerate(lc_messages) if getattr(m, "content", "") == "SUMMARY"
    ]
    assert summary_positions and min(summary_positions) >= 1


@pytest.mark.asyncio
async def test_invoke_returns_text_and_model_tokens(bedrock_env):
    fake_client = _fake_client(
        _plain_text_ai("Spent 2,450 UAH on groceries in March.", 42, 17)
    )
    backend = DirectBedrockBackend()
    with patch("app.agents.llm._get_client_for", return_value=fake_client):
        with patch("app.agents.llm.record_success") as rec_ok:
            result = await backend.invoke(
                **_invoke_kwargs(user_message="How much did I spend last month?")
            )
    assert result.text == "Spent 2,450 UAH on groceries in March."
    assert result.input_tokens == 42
    assert result.output_tokens == 17
    assert result.token_source == "model"
    assert result.tool_calls == ()
    rec_ok.assert_called_once_with("bedrock")


@pytest.mark.asyncio
async def test_invoke_falls_back_to_tiktoken_when_usage_missing(bedrock_env):
    ai = MagicMock()
    ai.content = "ok"
    ai.usage_metadata = {}
    ai.tool_calls = []
    fake_client = _fake_client(ai)
    backend = DirectBedrockBackend()
    with patch("app.agents.llm._get_client_for", return_value=fake_client):
        with patch("app.agents.llm.record_success"):
            result = await backend.invoke(
                **_invoke_kwargs(context_messages=[_user_msg("hi")])
            )
    assert result.token_source == "tiktoken"
    assert result.input_tokens >= 1
    assert result.output_tokens >= 1


# ---------------------------------------------------------------------------
# Exception translation
# ---------------------------------------------------------------------------


def _client_error(code: str) -> ClientError:
    return ClientError(
        error_response={"Error": {"Code": code, "Message": "forced"}},
        operation_name="InvokeModel",
    )


@pytest.mark.asyncio
async def test_access_denied_maps_to_configuration_error(bedrock_env):
    fake_client = MagicMock()
    fake_client.ainvoke = AsyncMock(side_effect=_client_error("AccessDeniedException"))
    fake_client.bind_tools = MagicMock(return_value=fake_client)
    backend = DirectBedrockBackend()
    with patch("app.agents.llm._get_client_for", return_value=fake_client):
        with patch("app.agents.llm.record_failure") as rec_fail:
            with pytest.raises(ChatConfigurationError):
                await backend.invoke(**_invoke_kwargs())
    rec_fail.assert_called_once_with("bedrock")


@pytest.mark.asyncio
@pytest.mark.parametrize("code", ["ThrottlingException", "ServiceUnavailableException"])
async def test_throttling_and_unavailable_map_to_transient_error(bedrock_env, code):
    fake_client = MagicMock()
    fake_client.ainvoke = AsyncMock(side_effect=_client_error(code))
    fake_client.bind_tools = MagicMock(return_value=fake_client)
    backend = DirectBedrockBackend()
    with patch("app.agents.llm._get_client_for", return_value=fake_client):
        with patch("app.agents.llm.record_failure"):
            with pytest.raises(ChatTransientError):
                await backend.invoke(**_invoke_kwargs())


@pytest.mark.asyncio
async def test_unknown_client_error_propagates_raw(bedrock_env):
    fake_client = MagicMock()
    fake_client.ainvoke = AsyncMock(side_effect=_client_error("SomeWeirdException"))
    fake_client.bind_tools = MagicMock(return_value=fake_client)
    backend = DirectBedrockBackend()
    with patch("app.agents.llm._get_client_for", return_value=fake_client):
        with patch("app.agents.llm.record_failure"):
            with pytest.raises(ClientError):
                await backend.invoke(**_invoke_kwargs())


# ---------------------------------------------------------------------------
# create / terminate are no-ops in Phase A
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_remote_session_returns_db_id_string(bedrock_env):
    backend = DirectBedrockBackend()
    db_id = uuid.uuid4()
    result = await backend.create_remote_session(db_id)
    assert result == str(db_id)


@pytest.mark.asyncio
async def test_terminate_remote_session_is_noop(bedrock_env):
    backend = DirectBedrockBackend()
    assert await backend.terminate_remote_session("any-id") is None


# ---------------------------------------------------------------------------
# build_backend() factory
# ---------------------------------------------------------------------------


def test_build_backend_direct(bedrock_env, monkeypatch):
    monkeypatch.setattr(settings, "CHAT_RUNTIME", "direct")
    assert isinstance(chat_backend.build_backend(), DirectBedrockBackend)


def test_build_backend_agentcore_raises_phase_b(bedrock_env, monkeypatch):
    monkeypatch.setattr(settings, "CHAT_RUNTIME", "agentcore")
    with pytest.raises(ChatConfigurationError) as excinfo:
        chat_backend.build_backend()
    assert "Phase B" in str(excinfo.value)


# ---------------------------------------------------------------------------
# Tool-use loop (Story 10.4c AC #7)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_toolless_turn_exits_with_zero_hops(bedrock_env):
    """Model returns plain text first call → loop exits with hops=0, tool_calls=()."""
    fake_client = _fake_client(_plain_text_ai("plain", 5, 5))
    backend = DirectBedrockBackend()
    with patch("app.agents.llm._get_client_for", return_value=fake_client):
        with patch("app.agents.llm.record_success"):
            result = await backend.invoke(**_invoke_kwargs())
    assert result.tool_calls == ()
    assert result.text == "plain"
    assert fake_client.ainvoke.await_count == 1


@pytest.mark.asyncio
async def test_single_tool_turn_dispatches_and_returns(bedrock_env):
    tool_use = _tool_use_ai(args={"limit": 5}, tc_id="tu_A")
    final = _plain_text_ai("final answer", 3, 7)
    fake_client = _fake_client_sequence([tool_use, final])

    dispatched = MagicMock()

    async def _fake_dispatch(invocation, *, user_id, db, db_session_id=None):
        dispatched(invocation, user_id=user_id)
        from app.agents.chat.tools.dispatcher import ToolResult

        return ToolResult(
            tool_use_id=invocation.tool_use_id,
            tool_name=invocation.tool_name,
            ok=True,
            payload={"rows": [], "row_count": 0, "truncated": False},
            error_kind=None,
            elapsed_ms=1,
        )

    backend = DirectBedrockBackend()
    with patch("app.agents.llm._get_client_for", return_value=fake_client):
        with patch("app.agents.llm.record_success"):
            with patch(
                "app.agents.chat.tools.dispatcher.dispatch_tool",
                new=_fake_dispatch,
            ):
                result = await backend.invoke(**_invoke_kwargs())
    assert result.text == "final answer"
    assert len(result.tool_calls) == 1
    assert result.tool_calls[0].tool_name == "get_transactions"
    assert fake_client.ainvoke.await_count == 2
    assert result.input_tokens == 1 + 3
    assert result.output_tokens == 1 + 7


@pytest.mark.asyncio
async def test_two_parallel_tool_uses_execute_in_series(bedrock_env):
    ai_parallel = MagicMock()
    ai_parallel.content = [
        {"type": "tool_use", "id": "tu_1", "name": "get_transactions", "input": {}},
        {"type": "tool_use", "id": "tu_2", "name": "get_profile", "input": {}},
    ]
    ai_parallel.usage_metadata = {"input_tokens": 1, "output_tokens": 1}
    ai_parallel.tool_calls = [
        {"name": "get_transactions", "args": {}, "id": "tu_1"},
        {"name": "get_profile", "args": {}, "id": "tu_2"},
    ]
    final = _plain_text_ai("combined", 2, 4)
    fake_client = _fake_client_sequence([ai_parallel, final])

    async def _fake_dispatch(invocation, *, user_id, db, db_session_id=None):
        from app.agents.chat.tools.dispatcher import ToolResult

        return ToolResult(
            tool_use_id=invocation.tool_use_id,
            tool_name=invocation.tool_name,
            ok=True,
            payload={"ok": True},
            error_kind=None,
            elapsed_ms=1,
        )

    backend = DirectBedrockBackend()
    with patch("app.agents.llm._get_client_for", return_value=fake_client):
        with patch("app.agents.llm.record_success"):
            with patch(
                "app.agents.chat.tools.dispatcher.dispatch_tool",
                new=_fake_dispatch,
            ):
                result = await backend.invoke(**_invoke_kwargs())
    assert len(result.tool_calls) == 2
    assert [c.tool_name for c in result.tool_calls] == [
        "get_transactions",
        "get_profile",
    ]
    # Two tools collapsed into a single hop — only 2 ainvoke calls total.
    assert fake_client.ainvoke.await_count == 2


@pytest.mark.asyncio
async def test_loop_exceeded_raises(bedrock_env):
    tool_use = _tool_use_ai(args={}, tc_id="tu_stuck")
    # Always return tool_use → the loop never terminates within cap.
    fake_client = MagicMock()
    fake_client.ainvoke = AsyncMock(return_value=tool_use)
    fake_client.bind_tools = MagicMock(return_value=fake_client)

    async def _fake_dispatch(invocation, *, user_id, db, db_session_id=None):
        from app.agents.chat.tools.dispatcher import ToolResult

        return ToolResult(
            tool_use_id=invocation.tool_use_id,
            tool_name=invocation.tool_name,
            ok=True,
            payload={"ok": True},
            error_kind=None,
            elapsed_ms=1,
        )

    backend = DirectBedrockBackend()
    with patch("app.agents.llm._get_client_for", return_value=fake_client):
        with patch("app.agents.llm.record_success"):
            with patch(
                "app.agents.chat.tools.dispatcher.dispatch_tool",
                new=_fake_dispatch,
            ):
                with pytest.raises(ChatToolLoopExceededError) as exc_info:
                    await backend.invoke(**_invoke_kwargs())
    assert exc_info.value.hops == MAX_TOOL_HOPS + 1
    # tool_calls_so_far carries the partial forensic trail.
    assert len(exc_info.value.tool_calls_so_far) == MAX_TOOL_HOPS


@pytest.mark.asyncio
async def test_not_allowed_tool_round_trips_as_toolresult(bedrock_env):
    """The dispatcher returns an ``ok=False, error_kind='not_allowed'`` ToolResult
    (soft path) and the loop feeds that back to the model; the second iteration's
    text response is final.
    """
    bad_tool_use = MagicMock()
    bad_tool_use.content = [
        {"type": "tool_use", "id": "tu_bad", "name": "delete_all_data", "input": {}}
    ]
    bad_tool_use.usage_metadata = {"input_tokens": 1, "output_tokens": 1}
    bad_tool_use.tool_calls = [{"name": "delete_all_data", "args": {}, "id": "tu_bad"}]
    final = _plain_text_ai("sorry, I can't do that", 1, 1)
    fake_client = _fake_client_sequence([bad_tool_use, final])

    backend = DirectBedrockBackend()
    with patch("app.agents.llm._get_client_for", return_value=fake_client):
        with patch("app.agents.llm.record_success"):
            result = await backend.invoke(**_invoke_kwargs())
    assert len(result.tool_calls) == 1
    assert result.tool_calls[0].error_kind == "not_allowed"
    assert result.tool_calls[0].ok is False
    assert result.text == "sorry, I can't do that"
