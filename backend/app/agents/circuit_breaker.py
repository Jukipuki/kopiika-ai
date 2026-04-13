"""Redis-backed circuit breaker for LLM API calls.

Simple counter + TTL pattern: tracks consecutive failures per LLM provider,
trips after FAILURE_THRESHOLD failures, cooldown for COOLDOWN_SECONDS.
"""

import logging

import redis as sync_redis

from app.core.config import settings
from app.core.exceptions import CircuitBreakerOpenError  # noqa: F401 — re-export

logger = logging.getLogger(__name__)

FAILURE_THRESHOLD = 3
COOLDOWN_SECONDS = 60

# Redis key patterns
_FAILURE_KEY = "circuit_breaker:failures:{provider}"
_OPEN_KEY = "circuit_breaker:open:{provider}"

# Module-level singleton — avoids creating a new connection pool on every call.
_redis_client: sync_redis.Redis | None = None


def _get_redis() -> sync_redis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = sync_redis.from_url(settings.REDIS_URL, decode_responses=True)
    return _redis_client


def check_circuit(provider: str) -> None:
    """Check if the circuit breaker is open for the given provider.

    Raises CircuitBreakerOpenError if the circuit is open.
    """
    client = _get_redis()
    if client.exists(_OPEN_KEY.format(provider=provider)):
        raise CircuitBreakerOpenError(provider)


def record_success(provider: str) -> None:
    """Record a successful LLM call — reset the failure counter."""
    _get_redis().delete(_FAILURE_KEY.format(provider=provider))


def record_failure(provider: str) -> None:
    """Record a failed LLM call. If threshold reached, open the circuit."""
    client = _get_redis()
    key = _FAILURE_KEY.format(provider=provider)
    failures = client.incr(key)
    # Set expiry so stale counters don't persist forever
    client.expire(key, COOLDOWN_SECONDS * 2)

    if failures >= FAILURE_THRESHOLD:
        open_key = _OPEN_KEY.format(provider=provider)
        client.set(open_key, "1", ex=COOLDOWN_SECONDS)
        client.delete(key)
        logger.warning(
            "Circuit breaker OPEN for provider %s (cooldown=%ds)",
            provider,
            COOLDOWN_SECONDS,
        )
