"""Chat rate-limit exception skeleton — Story 10.5 AC #9.

# SCOPE: A single, empty-skeleton exception class authored here so Story
# 10.5's CHAT_REFUSED envelope translator has a stable typed target.
# Raiser / middleware / Redis counter ship in Story 10.11.
#
# Non-goals (Story 10.11 owns):
#   - 60/hr + 10 concurrent + per-user daily token enforcement
#   - Redis rate-limit counters
#   - retry_after_seconds derivation from the sliding window state
#   - any FastAPI middleware wiring
"""

from __future__ import annotations


class ChatRateLimitedError(Exception):
    """Raised by Story 10.11's rate-limit middleware when a user exceeds one
    of the configured chat rate-limit dimensions (hourly turn count,
    concurrent streams, daily token budget).

    Authored in 10.5 so the CHAT_REFUSED envelope translator in
    ``app/api/v1/chat.py`` has a stable import target; the class is read by
    the translator (``reason=rate_limited`` + optional
    ``retry_after_seconds``). Story 10.11 plugs in by raising instances of
    this class from its middleware — no translator edit needed.
    """

    def __init__(
        self,
        *,
        correlation_id: str,
        retry_after_seconds: int | None = None,
        cause: str = "unknown",  # "hourly" | "concurrent" | "daily_tokens" | "unknown"
    ) -> None:
        self.correlation_id = correlation_id
        self.retry_after_seconds = retry_after_seconds
        self.cause = cause
        super().__init__(f"Chat rate-limited (cause={cause})")


__all__ = ["ChatRateLimitedError"]
