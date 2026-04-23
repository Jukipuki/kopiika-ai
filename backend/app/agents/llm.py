"""Shared LLM client initialization for pipeline agent nodes.

Story 9.5a: provider-routing factory. Story 9.5b: Bedrock branch wired via
langchain-aws ChatBedrockConverse; adds agent_fallback role so bedrock-primary
deploys fall back to a different Bedrock model (not the same Haiku ARN).
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
_FALLBACK_ROLE_MAP = {"anthropic": "agent_default", "openai": "agent_default", "bedrock": "agent_fallback"}


def _fallback_role_for(primary: str) -> str:
    return _FALLBACK_ROLE_MAP[primary]


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


def _parse_bedrock_arn(model_id: str) -> tuple[str, str]:
    """Return (region, provider_family) parsed from a Bedrock inference-profile ARN.

    Expected shape: ``arn:aws:bedrock:<region>:<account>:inference-profile/<scope>.<family>.<rest>``
    e.g. ``eu.anthropic.claude-haiku-4-5-...`` → ("eu-central-1", "anthropic");
         ``eu.amazon.nova-micro-v1:0``        → ("eu-central-1", "amazon").
    """
    parts = model_id.split(":")
    if len(parts) < 6 or parts[0] != "arn" or parts[2] != "bedrock":
        raise ValueError(f"Bedrock model_id must be a full Bedrock ARN (got: {model_id!r})")
    region = parts[3]
    profile_id = parts[5].split("/", 1)[-1]
    segments = profile_id.split(".")
    if len(segments) < 2:
        raise ValueError(f"Unexpected Bedrock inference-profile id shape: {profile_id!r}")
    return region, segments[1]


def _build_client(provider: str, model_id: str):
    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(model=model_id, api_key=settings.ANTHROPIC_API_KEY)
    if provider == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(model=model_id, api_key=settings.OPENAI_API_KEY)
    if provider == "bedrock":
        from langchain_aws import ChatBedrockConverse
        region, family = _parse_bedrock_arn(model_id)
        return ChatBedrockConverse(
            model=model_id,
            region_name=region,
            provider=family,
        )
    raise ValueError(f"Unknown LLM provider: {provider}")


def _validate_api_key(provider: str) -> None:
    if provider == "bedrock":
        # Bedrock credentials come from the boto3 default chain, not a settings field.
        return
    if provider == "anthropic" and settings.ANTHROPIC_API_KEY is None:
        raise ValueError("ANTHROPIC_API_KEY not configured")
    if provider == "openai" and settings.OPENAI_API_KEY is None:
        raise ValueError("OPENAI_API_KEY not configured")


def _get_client_for(provider: str, role: str = _PRIMARY_ROLE):
    check_circuit(provider)
    _validate_api_key(provider)
    model_id = _resolve_model_id(role, provider)
    return _build_client(provider, model_id)


def get_llm_client():
    """Return the primary LLM client.

    Provider is selected by settings.LLM_PROVIDER (default: anthropic).
    Checks the circuit breaker before returning. Callers should call
    record_success/record_failure after use via the circuit_breaker module.
    """
    return _get_client_for(settings.LLM_PROVIDER)


def get_fallback_llm_client():
    """Return the fallback LLM client.

    For anthropic/openai primaries: opposite-of-primary at agent_default role.
    For bedrock primary: bedrock at agent_fallback role (a different Bedrock
    model, to avoid a same-ARN round-trip on circuit-breaker trip).
    Checks the circuit breaker before returning.
    """
    primary = settings.LLM_PROVIDER
    fallback_provider = _FALLBACK_MAP[primary]
    fallback_role = _fallback_role_for(primary)
    return _get_client_for(fallback_provider, fallback_role)
