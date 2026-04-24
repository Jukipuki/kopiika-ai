"""Tests for DirectBedrockBackend (Phase A per ADR-0004).

Phase B's AgentCore backend has a sibling test file
``test_chat_backend_agentcore.py`` that skips until 10.4a-runtime ships.
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
)
from app.core.config import settings
from app.models.chat_message import ChatMessage


@pytest.fixture
def bedrock_env(monkeypatch):
    monkeypatch.setattr(settings, "LLM_PROVIDER", "bedrock")
    yield


def _user_msg(content: str) -> ChatMessage:
    return ChatMessage(session_id=uuid.uuid4(), role="user", content=content)


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
    # Does not raise; instance is created successfully.
    backend = DirectBedrockBackend()
    assert isinstance(backend, DirectBedrockBackend)


# ---------------------------------------------------------------------------
# Region / provider routing (AC #13 "selects eu-central-1 from settings")
# ---------------------------------------------------------------------------


def test_bedrock_client_built_for_eu_central_1(bedrock_env):
    """``_get_client_for('bedrock', role='chat_default')`` resolves the ARN
    from models.yaml, which pins chat_default to an eu-central-1 inference
    profile per Story 9.4. This wires the region without a settings lookup.
    """
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
# invoke happy path (AC #10)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_invoke_returns_text_and_model_tokens(bedrock_env):
    ai_msg = MagicMock()
    ai_msg.content = "Spent 2,450 UAH on groceries in March."
    ai_msg.usage_metadata = {"input_tokens": 42, "output_tokens": 17}

    fake_client = MagicMock()
    fake_client.ainvoke = AsyncMock(return_value=ai_msg)

    backend = DirectBedrockBackend()
    with patch.object(
        chat_backend, "_get_client_for", return_value=fake_client, create=True
    ) as _gci:
        # _get_client_for is imported inside invoke() → patch it on the llm module too
        with patch("app.agents.llm._get_client_for", return_value=fake_client):
            with patch("app.agents.llm.record_success") as rec_ok:
                result = await backend.invoke(
                    db_session_id=uuid.uuid4(),
                    context_messages=[],
                    user_message="How much did I spend last month?",
                )
    assert result.text == "Spent 2,450 UAH on groceries in March."
    assert result.input_tokens == 42
    assert result.output_tokens == 17
    assert result.token_source == "model"
    rec_ok.assert_called_once_with("bedrock")


@pytest.mark.asyncio
async def test_invoke_falls_back_to_tiktoken_when_usage_missing(bedrock_env):
    ai_msg = MagicMock()
    ai_msg.content = "ok"
    # No usage_metadata → fallback
    ai_msg.usage_metadata = {}

    fake_client = MagicMock()
    fake_client.ainvoke = AsyncMock(return_value=ai_msg)

    backend = DirectBedrockBackend()
    with patch("app.agents.llm._get_client_for", return_value=fake_client):
        with patch("app.agents.llm.record_success"):
            result = await backend.invoke(
                db_session_id=uuid.uuid4(),
                context_messages=[_user_msg("hi")],
                user_message="hey",
            )
    assert result.token_source == "tiktoken"
    assert result.input_tokens >= 1
    assert result.output_tokens >= 1


@pytest.mark.asyncio
async def test_invoke_no_tools_payload_shape(bedrock_env):
    """The langchain ainvoke call receives a flat list of BaseMessage — no
    ``tools`` / ``toolConfig`` kwarg. Story 10.4c's job is to add tools.
    """
    ai_msg = MagicMock()
    ai_msg.content = "ok"
    ai_msg.usage_metadata = {"input_tokens": 1, "output_tokens": 1}

    fake_client = MagicMock()
    fake_client.ainvoke = AsyncMock(return_value=ai_msg)

    backend = DirectBedrockBackend()
    with patch("app.agents.llm._get_client_for", return_value=fake_client):
        with patch("app.agents.llm.record_success"):
            await backend.invoke(
                db_session_id=uuid.uuid4(),
                context_messages=[],
                user_message="hello",
            )
    call_args, call_kwargs = fake_client.ainvoke.call_args
    # The positional arg is a list of LC messages.
    assert isinstance(call_args[0], list)
    assert "tools" not in call_kwargs
    assert "toolConfig" not in call_kwargs


# ---------------------------------------------------------------------------
# Exception translation (AC #10)
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
    backend = DirectBedrockBackend()
    with patch("app.agents.llm._get_client_for", return_value=fake_client):
        with patch("app.agents.llm.record_failure") as rec_fail:
            with pytest.raises(ChatConfigurationError):
                await backend.invoke(
                    db_session_id=uuid.uuid4(),
                    context_messages=[],
                    user_message="q",
                )
    rec_fail.assert_called_once_with("bedrock")


@pytest.mark.asyncio
@pytest.mark.parametrize("code", ["ThrottlingException", "ServiceUnavailableException"])
async def test_throttling_and_unavailable_map_to_transient_error(bedrock_env, code):
    fake_client = MagicMock()
    fake_client.ainvoke = AsyncMock(side_effect=_client_error(code))
    backend = DirectBedrockBackend()
    with patch("app.agents.llm._get_client_for", return_value=fake_client):
        with patch("app.agents.llm.record_failure"):
            with pytest.raises(ChatTransientError):
                await backend.invoke(
                    db_session_id=uuid.uuid4(),
                    context_messages=[],
                    user_message="q",
                )


@pytest.mark.asyncio
async def test_unknown_client_error_propagates_raw(bedrock_env):
    fake_client = MagicMock()
    fake_client.ainvoke = AsyncMock(side_effect=_client_error("SomeWeirdException"))
    backend = DirectBedrockBackend()
    with patch("app.agents.llm._get_client_for", return_value=fake_client):
        with patch("app.agents.llm.record_failure"):
            with pytest.raises(ClientError):
                await backend.invoke(
                    db_session_id=uuid.uuid4(),
                    context_messages=[],
                    user_message="q",
                )


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
