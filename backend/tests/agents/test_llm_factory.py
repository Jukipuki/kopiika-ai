"""Unit tests for the llm.py provider-routing factory (Stories 9.5a + 9.5b).

Offline only — no real API calls, no Redis, no real AWS. Circuit-breaker state
is mocked via monkeypatching app.agents.circuit_breaker.check_circuit.
Bedrock client construction is mocked via monkeypatching
langchain_aws.ChatBedrockConverse to a sentinel class.
"""

from pathlib import Path

import pytest

from app.agents import llm as llm_module
from app.core.config import settings
from app.core.exceptions import CircuitBreakerOpenError


HAIKU_BEDROCK_ARN = (
    "arn:aws:bedrock:eu-central-1:573562677570:inference-profile/"
    "eu.anthropic.claude-haiku-4-5-20251001-v1:0"
)
NOVA_MICRO_BEDROCK_ARN = (
    "arn:aws:bedrock:eu-central-1:573562677570:inference-profile/"
    "eu.amazon.nova-micro-v1:0"
)


class _BedrockSentinel:
    """Stand-in for ChatBedrockConverse — captures constructor kwargs for assertions."""

    call_count = 0

    def __init__(self, **kwargs):
        type(self).call_count += 1
        self.kwargs = kwargs
        self.model_id = kwargs.get("model") or kwargs.get("model_id")
        self.region_name = kwargs.get("region_name")
        self.provider = kwargs.get("provider")


@pytest.fixture(autouse=True)
def _reset_cache_and_keys(monkeypatch):
    """Reset lru_cache + provide fake API keys between tests."""
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "fake-anthropic")
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "fake-openai")
    monkeypatch.setattr(settings, "LLM_PROVIDER", "anthropic")
    # Neutralize circuit breaker by default (tests override as needed).
    monkeypatch.setattr(llm_module, "check_circuit", lambda provider: None)
    llm_module.reload_models_config_for_tests()
    # Reset sentinel call counter per test.
    _BedrockSentinel.call_count = 0
    yield
    llm_module.reload_models_config_for_tests()


@pytest.fixture
def _bedrock_sentinel(monkeypatch):
    """Patch langchain_aws.ChatBedrockConverse to the sentinel class.

    Must target the langchain_aws module attribute (not llm_module), because
    _build_client does a lazy `from langchain_aws import ChatBedrockConverse`
    that re-reads the attribute on each call.
    """
    monkeypatch.setenv("AWS_PROFILE", "test-fake")
    import langchain_aws
    monkeypatch.setattr(langchain_aws, "ChatBedrockConverse", _BedrockSentinel)
    return _BedrockSentinel


def test_default_provider_returns_anthropic_haiku():
    client = llm_module.get_llm_client()
    assert type(client).__name__ == "ChatAnthropic"
    assert client.model == "claude-haiku-4-5-20251001"


def test_primary_switch_to_openai(monkeypatch):
    monkeypatch.setattr(settings, "LLM_PROVIDER", "openai")
    client = llm_module.get_llm_client()
    assert type(client).__name__ == "ChatOpenAI"
    assert client.model_name == "gpt-4o-mini"

    fallback = llm_module.get_fallback_llm_client()
    assert type(fallback).__name__ == "ChatAnthropic"
    assert fallback.model == "claude-haiku-4-5-20251001"


def test_bedrock_primary_returns_chat_bedrock_client(monkeypatch, _bedrock_sentinel):
    monkeypatch.setattr(settings, "LLM_PROVIDER", "bedrock")
    client = llm_module.get_llm_client()
    assert isinstance(client, _bedrock_sentinel)
    assert client.model_id == HAIKU_BEDROCK_ARN
    assert client.region_name == "eu-central-1"
    assert client.provider == "anthropic"


def test_bedrock_fallback_resolves_agent_fallback_role(monkeypatch, _bedrock_sentinel, tmp_path: Path):
    default_arn = (
        "arn:aws:bedrock:eu-central-1:000000000000:inference-profile/"
        "eu.anthropic.claude-haiku-4-5-20251001-v1:0"
    )
    fallback_arn = (
        "arn:aws:bedrock:eu-central-1:000000000000:inference-profile/"
        "eu.amazon.nova-micro-v1:0"
    )
    fixture = tmp_path / "models.yaml"
    fixture.write_text(
        "agent_default:\n"
        "  anthropic: \"claude-haiku-4-5-20251001\"\n"
        "  openai: \"gpt-4o-mini\"\n"
        f"  bedrock: \"{default_arn}\"\n"
        "agent_fallback:\n"
        "  anthropic: \"claude-haiku-4-5-20251001\"\n"
        "  openai: \"gpt-4o-mini\"\n"
        f"  bedrock: \"{fallback_arn}\"\n"
    )
    monkeypatch.setenv("LLM_MODELS_CONFIG_PATH", str(fixture))
    monkeypatch.setattr(settings, "LLM_PROVIDER", "bedrock")
    llm_module.reload_models_config_for_tests()

    fallback = llm_module.get_fallback_llm_client()
    assert isinstance(fallback, _bedrock_sentinel)
    assert fallback.model_id == fallback_arn
    # Provider family is derived from the ARN prefix — Nova ARN → "amazon", not
    # the primary's "anthropic". Locks the _parse_bedrock_arn contract.
    assert fallback.provider == "amazon"
    assert fallback.region_name == "eu-central-1"


def test_bedrock_circuit_open_blocks_construction(monkeypatch, _bedrock_sentinel):
    monkeypatch.setattr(settings, "LLM_PROVIDER", "bedrock")

    def _raise_open(provider: str) -> None:
        if provider == "bedrock":
            raise CircuitBreakerOpenError(provider)

    monkeypatch.setattr(llm_module, "check_circuit", _raise_open)

    with pytest.raises(CircuitBreakerOpenError):
        llm_module.get_llm_client()
    assert _bedrock_sentinel.call_count == 0


def test_non_bedrock_primary_fallback_topology_unchanged(monkeypatch):
    # Anthropic primary → OpenAI fallback (opposite-of-primary at agent_default).
    monkeypatch.setattr(settings, "LLM_PROVIDER", "anthropic")
    fallback = llm_module.get_fallback_llm_client()
    assert type(fallback).__name__ == "ChatOpenAI"
    assert fallback.model_name == "gpt-4o-mini"

    # OpenAI primary → Anthropic fallback.
    monkeypatch.setattr(settings, "LLM_PROVIDER", "openai")
    fallback = llm_module.get_fallback_llm_client()
    assert type(fallback).__name__ == "ChatAnthropic"
    assert fallback.model == "claude-haiku-4-5-20251001"


def test_missing_anthropic_api_key_raises_value_error(monkeypatch):
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", None)
    with pytest.raises(ValueError, match="^ANTHROPIC_API_KEY not configured$"):
        llm_module.get_llm_client()


def test_missing_openai_api_key_raises_value_error(monkeypatch):
    monkeypatch.setattr(settings, "LLM_PROVIDER", "openai")
    monkeypatch.setattr(settings, "OPENAI_API_KEY", None)
    with pytest.raises(ValueError, match="^OPENAI_API_KEY not configured$"):
        llm_module.get_llm_client()


def test_missing_role_raises_key_error(monkeypatch, tmp_path: Path):
    fixture = tmp_path / "models.yaml"
    fixture.write_text(
        "other_role:\n"
        "  anthropic: \"claude-haiku-4-5-20251001\"\n"
        "  openai: \"gpt-4o-mini\"\n"
        "  bedrock: \"arn:whatever\"\n"
    )
    monkeypatch.setenv("LLM_MODELS_CONFIG_PATH", str(fixture))
    llm_module.reload_models_config_for_tests()
    with pytest.raises(KeyError, match="Role 'agent_default' not found"):
        llm_module.get_llm_client()


def test_missing_provider_subkey_raises_key_error(monkeypatch, tmp_path: Path):
    fixture = tmp_path / "models.yaml"
    fixture.write_text(
        "agent_default:\n"
        "  openai: \"gpt-4o-mini\"\n"
        "  bedrock: \"arn:whatever\"\n"
    )
    monkeypatch.setenv("LLM_MODELS_CONFIG_PATH", str(fixture))
    llm_module.reload_models_config_for_tests()
    with pytest.raises(KeyError, match="has no 'anthropic' entry"):
        llm_module.get_llm_client()


def test_circuit_breaker_open_blocks_client_construction(monkeypatch):
    def _raise_open(provider: str) -> None:
        raise CircuitBreakerOpenError(provider)

    monkeypatch.setattr(llm_module, "check_circuit", _raise_open)

    def _fail_anthropic(*args, **kwargs):
        pytest.fail("ChatAnthropic should not be constructed when circuit is open")

    def _fail_openai(*args, **kwargs):
        pytest.fail("ChatOpenAI should not be constructed when circuit is open")

    import langchain_anthropic
    import langchain_openai

    monkeypatch.setattr(langchain_anthropic, "ChatAnthropic", _fail_anthropic)
    monkeypatch.setattr(langchain_openai, "ChatOpenAI", _fail_openai)

    with pytest.raises(CircuitBreakerOpenError):
        llm_module.get_llm_client()
