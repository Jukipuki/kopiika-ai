"""Tests for the chat canary loader — Story 10.4b AC #2 / AC #12."""

from __future__ import annotations

import json
import re
from unittest.mock import MagicMock, patch

import pytest

from app.agents.chat import canaries as canaries_mod
from app.agents.chat.canaries import (
    CanaryLoadError,
    CanarySet,
    _reset_canary_cache_for_tests,
    get_canary_set,
    load_canaries,
)
from app.core.config import settings


@pytest.fixture(autouse=True)
def _clear_cache():
    _reset_canary_cache_for_tests()
    yield
    _reset_canary_cache_for_tests()


# ---------------------------------------------------------------------------
# Dev-fallback path (LLM_PROVIDER != bedrock)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dev_fallback_conforms_to_charset_length_and_distinctness(monkeypatch):
    monkeypatch.setattr(settings, "LLM_PROVIDER", "anthropic")
    cset = await load_canaries()
    assert isinstance(cset, CanarySet)
    assert cset.version_id == "dev-fallback"
    tokens = cset.as_tuple()
    assert len(set(tokens)) == 3
    for t in tokens:
        assert len(t) >= 24
        assert re.match(r"^[A-Za-z0-9_-]+$", t)


# ---------------------------------------------------------------------------
# Secrets Manager happy path + shape/validation errors
# ---------------------------------------------------------------------------


def _make_boto_client(secret_string: str, version_id: str = "v-AWSCURRENT"):
    client = MagicMock()
    client.get_secret_value.return_value = {
        "SecretString": secret_string,
        "VersionId": version_id,
    }
    return client


@pytest.fixture
def bedrock_env(monkeypatch):
    monkeypatch.setattr(settings, "LLM_PROVIDER", "bedrock")
    monkeypatch.setattr(settings, "AWS_SECRETS_PREFIX", "kopiika/test")
    monkeypatch.setattr(settings, "CHAT_CANARIES_SECRET_ID", None)


@pytest.mark.asyncio
async def test_secrets_manager_happy_path(bedrock_env):
    payload = json.dumps(
        {
            "canary_a": "A" * 24,
            "canary_b": "B" * 24,
            "canary_c": "C" * 24,
        }
    )
    client = _make_boto_client(payload)
    with patch("boto3.client", return_value=client):
        cset = await load_canaries()
    assert cset.canary_a == "A" * 24
    assert cset.canary_b == "B" * 24
    assert cset.canary_c == "C" * 24
    assert cset.version_id == "v-AWSCURRENT"
    client.get_secret_value.assert_called_once_with(
        SecretId="kopiika/test/chat-canaries"
    )


@pytest.mark.asyncio
async def test_secrets_manager_explicit_secret_id_override(monkeypatch):
    monkeypatch.setattr(settings, "LLM_PROVIDER", "bedrock")
    monkeypatch.setattr(settings, "CHAT_CANARIES_SECRET_ID", "custom/name")
    monkeypatch.setattr(settings, "AWS_SECRETS_PREFIX", None)
    payload = json.dumps(
        {"canary_a": "X" * 24, "canary_b": "Y" * 24, "canary_c": "Z" * 24}
    )
    client = _make_boto_client(payload)
    with patch("boto3.client", return_value=client):
        await load_canaries()
    client.get_secret_value.assert_called_once_with(SecretId="custom/name")


@pytest.mark.asyncio
async def test_malformed_json_raises(bedrock_env):
    client = _make_boto_client("not json at all {{")
    with patch("boto3.client", return_value=client):
        with pytest.raises(CanaryLoadError):
            await load_canaries()


@pytest.mark.asyncio
async def test_missing_key_raises(bedrock_env):
    payload = json.dumps({"canary_a": "A" * 24, "canary_b": "B" * 24})
    client = _make_boto_client(payload)
    with patch("boto3.client", return_value=client):
        with pytest.raises(CanaryLoadError):
            await load_canaries()


@pytest.mark.asyncio
async def test_short_token_raises(bedrock_env):
    payload = json.dumps(
        {"canary_a": "A" * 10, "canary_b": "B" * 24, "canary_c": "C" * 24}
    )
    client = _make_boto_client(payload)
    with patch("boto3.client", return_value=client):
        with pytest.raises(CanaryLoadError):
            await load_canaries()


@pytest.mark.asyncio
async def test_off_alphabet_token_raises(bedrock_env):
    payload = json.dumps(
        {
            "canary_a": "A" * 23 + "!",  # length 24 but includes '!'
            "canary_b": "B" * 24,
            "canary_c": "C" * 24,
        }
    )
    client = _make_boto_client(payload)
    with patch("boto3.client", return_value=client):
        with pytest.raises(CanaryLoadError):
            await load_canaries()


@pytest.mark.asyncio
async def test_non_distinct_tokens_raise(bedrock_env):
    token = "A" * 24
    payload = json.dumps({"canary_a": token, "canary_b": token, "canary_c": "C" * 24})
    client = _make_boto_client(payload)
    with patch("boto3.client", return_value=client):
        with pytest.raises(CanaryLoadError):
            await load_canaries()


@pytest.mark.asyncio
async def test_boto_client_error_raises_canary_load_error(bedrock_env):
    from botocore.exceptions import ClientError

    client = MagicMock()
    client.get_secret_value.side_effect = ClientError(
        error_response={
            "Error": {"Code": "ResourceNotFoundException", "Message": "nope"}
        },
        operation_name="GetSecretValue",
    )
    with patch("boto3.client", return_value=client):
        with pytest.raises(CanaryLoadError):
            await load_canaries()


# ---------------------------------------------------------------------------
# Cache TTL behavior
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cache_serves_second_call_without_aws_hit(bedrock_env):
    payload = json.dumps(
        {"canary_a": "A" * 24, "canary_b": "B" * 24, "canary_c": "C" * 24}
    )
    client = _make_boto_client(payload)
    with patch("boto3.client", return_value=client):
        await get_canary_set()
        await get_canary_set()
    assert client.get_secret_value.call_count == 1


@pytest.mark.asyncio
async def test_cache_expires_and_refetches(bedrock_env, monkeypatch):
    payload = json.dumps(
        {"canary_a": "A" * 24, "canary_b": "B" * 24, "canary_c": "C" * 24}
    )
    client = _make_boto_client(payload)

    fake_time = [1000.0]

    def _mono():
        return fake_time[0]

    monkeypatch.setattr(canaries_mod.time, "monotonic", _mono)
    monkeypatch.setattr(settings, "CHAT_CANARY_CACHE_TTL_SECONDS", 60)

    with patch("boto3.client", return_value=client):
        await get_canary_set()
        fake_time[0] += 30  # still within TTL
        await get_canary_set()
        fake_time[0] += 100  # past TTL
        await get_canary_set()

    assert client.get_secret_value.call_count == 2


# ---------------------------------------------------------------------------
# Secret-name resolution
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_missing_prefix_and_secret_id_raises(monkeypatch):
    monkeypatch.setattr(settings, "LLM_PROVIDER", "bedrock")
    monkeypatch.setattr(settings, "CHAT_CANARIES_SECRET_ID", None)
    monkeypatch.setattr(settings, "AWS_SECRETS_PREFIX", None)
    with pytest.raises(CanaryLoadError):
        await load_canaries()
