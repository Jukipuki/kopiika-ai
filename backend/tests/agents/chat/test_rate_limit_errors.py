"""Story 10.5 AC #9 — ChatRateLimitedError skeleton."""

from __future__ import annotations

from app.agents.chat.rate_limit_errors import ChatRateLimitedError


def test_rate_limit_error_importable_constructible_and_translatable():
    exc = ChatRateLimitedError(
        correlation_id="abc",
        retry_after_seconds=30,
        cause="hourly",
    )
    assert exc.correlation_id == "abc"
    assert exc.retry_after_seconds == 30
    assert exc.cause == "hourly"

    # Translator maps to reason=rate_limited + retryAfterSeconds.
    from app.api.v1.chat import _translate_exception

    reason, payload, _cls, _lvl = _translate_exception(exc, correlation_id="abc")
    assert reason == "rate_limited"
    assert payload["reason"] == "rate_limited"
    assert payload["retryAfterSeconds"] == 30
    assert payload["correlationId"] == "abc"

    # retry_after_seconds is optional — translator returns None when unset.
    exc2 = ChatRateLimitedError(correlation_id="zzz")
    _reason, payload2, _cls2, _lvl2 = _translate_exception(exc2, correlation_id="zzz")
    assert payload2["retryAfterSeconds"] is None
