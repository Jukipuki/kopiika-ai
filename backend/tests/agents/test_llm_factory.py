"""Unit tests for the llm.py provider-routing factory (Story 9.5a).

Offline only — no real API calls, no Redis. Circuit-breaker state is
mocked via monkeypatching app.agents.circuit_breaker.check_circuit.
"""

from pathlib import Path

import pytest

from app.agents import llm as llm_module
from app.core.config import settings
from app.core.exceptions import CircuitBreakerOpenError


@pytest.fixture(autouse=True)
def _reset_cache_and_keys(monkeypatch):
    """Reset lru_cache + provide fake API keys between tests."""
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "fake-anthropic")
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "fake-openai")
    monkeypatch.setattr(settings, "LLM_PROVIDER", "anthropic")
    # Neutralize circuit breaker by default (tests override as needed).
    monkeypatch.setattr(llm_module, "check_circuit", lambda provider: None)
    llm_module.reload_models_config_for_tests()
    yield
    llm_module.reload_models_config_for_tests()


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


def test_bedrock_primary_raises_not_implemented(monkeypatch):
    monkeypatch.setattr(settings, "LLM_PROVIDER", "bedrock")
    with pytest.raises(NotImplementedError, match="Story 9.5b"):
        llm_module.get_llm_client()
    with pytest.raises(NotImplementedError, match="Story 9.5b"):
        llm_module.get_fallback_llm_client()


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
