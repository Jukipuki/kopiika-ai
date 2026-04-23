"""Shared LLM client initialization for pipeline agent nodes.

Story 9.5a: provider-routing factory. Resolves logical role -> provider-qualified
model ID from models.yaml based on settings.LLM_PROVIDER. Bedrock branch is
reserved but not wired — that lands in Story 9.5b.
"""

import functools
import os
from pathlib import Path

import yaml

from app.agents.circuit_breaker import check_circuit, record_failure, record_success  # noqa: F401
from app.agents.circuit_breaker import CircuitBreakerOpenError  # noqa: F401 — re-export
from app.core.config import settings

_PRIMARY_ROLE = "agent_default"
_FALLBACK_MAP = {"anthropic": "openai", "openai": "anthropic", "bedrock": "bedrock"}


def _models_config_path() -> Path:
    override = os.environ.get("LLM_MODELS_CONFIG_PATH")
    if override:
        return Path(override)
    return Path(__file__).parent / "models.yaml"


@functools.lru_cache(maxsize=1)
def _load_models_config() -> dict[str, dict[str, str]]:
    path = _models_config_path()
    if not path.is_file():
        raise FileNotFoundError(f"models.yaml not found at {path}")
    parsed = yaml.safe_load(path.read_text())
    if not isinstance(parsed, dict):
        raise ValueError(f"models.yaml at {path} must be a mapping of role -> provider-map (got {type(parsed).__name__})")
    return parsed


def reload_models_config_for_tests() -> None:
    """Clear the cached models.yaml. Tests only — production must not call this."""
    _load_models_config.cache_clear()


def _resolve_model_id(role: str, provider: str) -> str:
    config = _load_models_config()
    if role not in config:
        raise KeyError(
            f"Role '{role}' not found in models.yaml (available: {sorted(config.keys())})"
        )
    role_entry = config[role]
    if provider not in role_entry:
        raise KeyError(
            f"Role '{role}' has no '{provider}' entry in models.yaml "
            f"(available: {sorted(role_entry.keys())})"
        )
    return role_entry[provider]


def _build_client(provider: str, model_id: str):
    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(model=model_id, api_key=settings.ANTHROPIC_API_KEY)
    if provider == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(model=model_id, api_key=settings.OPENAI_API_KEY)
    if provider == "bedrock":
        raise NotImplementedError("Bedrock provider wiring lands in Story 9.5b")
    raise ValueError(f"Unknown LLM provider: {provider}")


def _validate_api_key(provider: str) -> None:
    if provider == "anthropic" and settings.ANTHROPIC_API_KEY is None:
        raise ValueError("ANTHROPIC_API_KEY not configured")
    if provider == "openai" and settings.OPENAI_API_KEY is None:
        raise ValueError("OPENAI_API_KEY not configured")


def _get_client_for(provider: str):
    if provider == "bedrock":
        # Bedrock wiring (including its circuit-breaker key) lands in Story 9.5b.
        # Fail loud before touching Redis or resolving config.
        raise NotImplementedError("Bedrock provider wiring lands in Story 9.5b")
    check_circuit(provider)
    _validate_api_key(provider)
    model_id = _resolve_model_id(_PRIMARY_ROLE, provider)
    return _build_client(provider, model_id)


def get_llm_client():
    """Return the primary LLM client.

    Provider is selected by settings.LLM_PROVIDER (default: anthropic).
    Checks the circuit breaker before returning. Callers should call
    record_success/record_failure after use via the circuit_breaker module.
    """
    return _get_client_for(settings.LLM_PROVIDER)


def get_fallback_llm_client():
    """Return the fallback LLM client (opposite of primary).

    Checks the circuit breaker before returning.
    """
    fallback = _FALLBACK_MAP[settings.LLM_PROVIDER]
    return _get_client_for(fallback)
