"""Shared LLM client initialization for pipeline agent nodes."""

from app.agents.circuit_breaker import check_circuit, record_failure, record_success
from app.agents.circuit_breaker import CircuitBreakerOpenError  # noqa: F401 — re-export
from app.core.config import settings


def get_llm_client():
    """Return the primary LLM client (Claude Haiku).

    Checks the circuit breaker before returning. Callers should call
    record_success/record_failure after use via the circuit_breaker module.
    """
    check_circuit("anthropic")
    if settings.ANTHROPIC_API_KEY is None:
        raise ValueError("ANTHROPIC_API_KEY not configured")
    from langchain_anthropic import ChatAnthropic
    return ChatAnthropic(
        model="claude-haiku-4-5-20251001",
        api_key=settings.ANTHROPIC_API_KEY,
    )


def get_fallback_llm_client():
    """Return the fallback LLM client (GPT-4o-mini).

    Checks the circuit breaker before returning.
    """
    check_circuit("openai")
    if settings.OPENAI_API_KEY is None:
        raise ValueError("OPENAI_API_KEY not configured")
    from langchain_openai import ChatOpenAI
    return ChatOpenAI(
        model="gpt-4o-mini",
        api_key=settings.OPENAI_API_KEY,
    )
