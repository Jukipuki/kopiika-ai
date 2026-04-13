"""Tests for circuit breaker (Story 6.2, AC #4)."""

from unittest.mock import patch

import fakeredis
import pytest

from app.agents.circuit_breaker import (
    COOLDOWN_SECONDS,
    FAILURE_THRESHOLD,
    CircuitBreakerOpenError,
    check_circuit,
    record_failure,
    record_success,
)


@pytest.fixture(autouse=True)
def fake_cb_redis():
    """Patch circuit breaker Redis with fakeredis."""
    client = fakeredis.FakeRedis(decode_responses=True)
    with patch("app.agents.circuit_breaker._get_redis", return_value=client):
        yield client


def test_circuit_closed_by_default():
    """Circuit breaker allows calls when no failures recorded."""
    check_circuit("anthropic")  # Should not raise


def test_circuit_opens_after_threshold_failures(fake_cb_redis):
    """Circuit breaker trips after FAILURE_THRESHOLD consecutive failures."""
    for _ in range(FAILURE_THRESHOLD):
        record_failure("anthropic")

    with pytest.raises(CircuitBreakerOpenError) as exc_info:
        check_circuit("anthropic")
    assert exc_info.value.provider == "anthropic"


def test_circuit_resets_on_success(fake_cb_redis):
    """A successful call resets the failure counter."""
    record_failure("anthropic")
    record_failure("anthropic")
    record_success("anthropic")

    # Counter reset — 3 more failures needed to trip
    record_failure("anthropic")
    record_failure("anthropic")
    check_circuit("anthropic")  # Should not raise (only 2 failures)


def test_circuit_cooldown_via_ttl(fake_cb_redis):
    """Open key has TTL set to COOLDOWN_SECONDS."""
    for _ in range(FAILURE_THRESHOLD):
        record_failure("anthropic")

    ttl = fake_cb_redis.ttl("circuit_breaker:open:anthropic")
    assert 0 < ttl <= COOLDOWN_SECONDS


def test_separate_providers_independent(fake_cb_redis):
    """Failures for one provider don't affect another."""
    for _ in range(FAILURE_THRESHOLD):
        record_failure("anthropic")

    # Anthropic is open
    with pytest.raises(CircuitBreakerOpenError):
        check_circuit("anthropic")

    # OpenAI is still closed
    check_circuit("openai")  # Should not raise
