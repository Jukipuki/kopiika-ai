import logging
import time
import uuid
from datetime import UTC, datetime, time as dtime, timedelta

import redis.asyncio as aioredis
from sqlalchemy import func
from sqlalchemy import select as sa_select
from sqlmodel.ext.asyncio.session import AsyncSession as SQLModelAsyncSession

from app.agents.chat.rate_limit_errors import ChatRateLimitedError
from app.core.config import settings
from app.core.exceptions import AuthenticationError
from app.models.chat_session import ChatSession

logger = logging.getLogger(__name__)


def _seconds_until_utc_midnight() -> int:
    """Whole seconds until the next UTC midnight (always >= 1)."""
    now = datetime.now(UTC)
    tomorrow = (now + timedelta(days=1)).date()
    midnight = datetime.combine(tomorrow, dtime.min, tzinfo=UTC)
    return max(int((midnight - now).total_seconds()), 1)


def _today_utc_suffix() -> str:
    return datetime.now(UTC).date().isoformat()


class RateLimiter:
    def __init__(
        self,
        redis: aioredis.Redis,
        max_attempts: int = 10,
        window_seconds: int = 900,
    ) -> None:
        self._redis = redis
        self._max_attempts = max_attempts
        self._window_seconds = window_seconds

    async def check_rate_limit(self, ip: str) -> None:
        key = f"rate_limit:login:{ip}"
        now = time.time()
        window_start = now - self._window_seconds

        pipe = self._redis.pipeline()
        pipe.zremrangebyscore(key, 0, window_start)
        pipe.zcard(key)
        pipe.zrange(key, 0, 0, withscores=True)
        results = await pipe.execute()

        attempt_count = results[1]

        if attempt_count >= self._max_attempts:
            oldest_entries = results[2]
            if oldest_entries:
                oldest_time = oldest_entries[0][1]
                retry_after = int(oldest_time + self._window_seconds - now) + 1
            else:
                retry_after = self._window_seconds

            raise AuthenticationError(
                code="RATE_LIMITED",
                message="Too many login attempts. Please try again later.",
                status_code=429,
                details={"retryAfter": retry_after},
            )

    async def record_failed_attempt(self, ip: str) -> None:
        key = f"rate_limit:login:{ip}"
        now = time.time()

        pipe = self._redis.pipeline()
        pipe.zadd(key, {str(now): now})
        pipe.expire(key, self._window_seconds)
        await pipe.execute()

    async def clear_attempts(self, ip: str) -> None:
        key = f"rate_limit:login:{ip}"
        await self._redis.delete(key)

    async def check_upload_rate_limit(
        self, user_id: str, max_uploads: int = 20, window_seconds: int = 3600
    ) -> None:
        key = f"rate_limit:upload:{user_id}"
        now = time.time()
        window_start = now - window_seconds

        pipe = self._redis.pipeline()
        pipe.zremrangebyscore(key, 0, window_start)
        pipe.zcard(key)
        results = await pipe.execute()

        attempt_count = results[1]

        if attempt_count >= max_uploads:
            from app.core.exceptions import ValidationError

            raise ValidationError(
                code="RATE_LIMITED",
                message="You've uploaded a lot of files recently. Please try again in a few minutes.",
                status_code=429,
            )

        # Record this upload
        pipe = self._redis.pipeline()
        pipe.zadd(key, {str(now): now})
        pipe.expire(key, window_seconds)
        await pipe.execute()

    async def check_consent_rate_limit(
        self, user_id: str, max_grants: int = 10, window_seconds: int = 3600
    ) -> None:
        key = f"rate_limit:consent:{user_id}"
        now = time.time()
        window_start = now - window_seconds

        pipe = self._redis.pipeline()
        pipe.zremrangebyscore(key, 0, window_start)
        pipe.zcard(key)
        results = await pipe.execute()

        attempt_count = results[1]

        if attempt_count >= max_grants:
            from app.core.exceptions import ValidationError

            raise ValidationError(
                code="RATE_LIMITED",
                message="Too many consent requests. Please try again later.",
                status_code=429,
            )

        pipe = self._redis.pipeline()
        pipe.zadd(key, {str(now): now})
        pipe.expire(key, window_seconds)
        await pipe.execute()

    async def check_feedback_rate_limit(
        self, user_id: str, max_batches: int = 60, window_seconds: int = 60
    ) -> None:
        key = f"rate_limit:feedback:{user_id}"
        now = time.time()
        window_start = now - window_seconds

        pipe = self._redis.pipeline()
        pipe.zremrangebyscore(key, 0, window_start)
        pipe.zcard(key)
        results = await pipe.execute()

        attempt_count = results[1]

        if attempt_count >= max_batches:
            from app.core.exceptions import ValidationError

            raise ValidationError(
                code="RATE_LIMITED",
                message="Too many interaction reports. Please try again shortly.",
                status_code=429,
            )

        pipe = self._redis.pipeline()
        pipe.zadd(key, {str(now): now})
        pipe.expire(key, window_seconds)
        await pipe.execute()

    # ------------------------------------------------------------------
    # Story 10.11 — chat rate-limit envelope (4 dimensions).
    # See architecture.md §Rate Limits L1730-L1738. The hourly + daily
    # caps live here; the concurrent cap is authoritative on the
    # ``chat_sessions`` table (no Redis counter — it would drift under
    # restart / consent-revoke cascades / TTL expiry). The per-IP cap
    # lives in WAF (see infra/terraform/.../waf.tf) — no app-layer code.
    # ------------------------------------------------------------------

    async def check_chat_hourly_rate_limit(
        self,
        user_id: str,
        *,
        correlation_id: str,
        max_turns: int = 60,
        window_seconds: int = 3600,
    ) -> None:
        """Sliding-window hourly turn-count cap.

        Records the turn into the ZSET on the success path so the next
        call sees it; on cap-exceeded raises ``ChatRateLimitedError`` with
        ``cause="hourly"`` and a ``retry_after_seconds`` derived from the
        oldest entry's expiry.
        """
        key = f"rate_limit:chat:hourly:{user_id}"
        now = time.time()
        window_start = now - window_seconds

        pipe = self._redis.pipeline()
        pipe.zremrangebyscore(key, 0, window_start)
        pipe.zcard(key)
        pipe.zrange(key, 0, 0, withscores=True)
        results = await pipe.execute()

        attempt_count = results[1]

        if attempt_count >= max_turns:
            oldest_entries = results[2]
            if oldest_entries:
                oldest_time = oldest_entries[0][1]
                retry_after = int(oldest_time + window_seconds - now) + 1
            else:
                retry_after = window_seconds
            retry_after = max(retry_after, 1)
            raise ChatRateLimitedError(
                correlation_id=correlation_id,
                retry_after_seconds=retry_after,
                cause="hourly",
            )

        # Success path: record this turn so the next call sees it. The
        # ZSET member must be unique-per-call so two requests landing in
        # the same ``time.time()`` tick don't silently overwrite (which
        # would undercount toward the cap).
        member = f"{now}:{uuid.uuid4().hex[:8]}"
        pipe = self._redis.pipeline()
        pipe.zadd(key, {member: now})
        pipe.expire(key, window_seconds)
        await pipe.execute()

    async def acquire_chat_concurrent_session_slot(
        self,
        db: SQLModelAsyncSession,
        user_id: str,
        *,
        max_concurrent: int = 10,
    ) -> bool:
        """Pre-create gate for the per-user concurrent-session cap.

        Counts open ``chat_sessions`` rows for this user (the row IS the
        slot — no Redis counter). Returns ``True`` if the user has
        ``< max_concurrent`` sessions; ``False`` at the cap (caller raises
        the 429 envelope).
        """
        user_uuid = (
            user_id if isinstance(user_id, uuid.UUID) else uuid.UUID(user_id)
        )
        stmt = (
            sa_select(func.count(ChatSession.id))
            .select_from(ChatSession)
            .where(ChatSession.user_id == user_uuid)
        )
        result = await db.exec(stmt)
        count = result.scalar_one() or 0
        return int(count) < max_concurrent

    async def release_chat_concurrent_session_slot(
        self, user_id: str  # noqa: ARG002
    ) -> None:
        """No-op release hook for the concurrent-session cap.

        The slot is "owned" by the ``chat_sessions`` row — releases happen
        implicitly when per-session DELETE (Story 10.5) or bulk-DELETE
        (Story 10.10) decrements the rowcount. This method is here as a
        documented anchor + future hook (e.g. cache invalidation if a
        cached count is ever added). Do NOT remove even if a strict-lint
        rule flags it as unused — it's load-bearing for the inventory.
        """
        return None

    async def check_chat_daily_token_cap(
        self,
        user_id: str,
        *,
        correlation_id: str,
        max_tokens_per_day: int | None = None,
        projected_tokens: int = 0,
    ) -> None:
        """Calendar-day-aligned per-user token cap.

        Key suffix ``:{utc_yyyy_mm_dd}`` — NOT a sliding window (the FE
        wall-clock UX requires a midnight reset, per architecture and
        ``10-3b-chat-ux-states-spec.md``). Does NOT INCRBY — recording is
        ``record_chat_token_spend``'s job after a successful turn.
        """
        cap = (
            max_tokens_per_day
            if max_tokens_per_day is not None
            else settings.CHAT_DAILY_TOKEN_CAP_PER_USER
        )
        key = f"rate_limit:chat:daily_tokens:{user_id}:{_today_utc_suffix()}"
        raw = await self._redis.get(key)
        try:
            current = int(raw) if raw is not None else 0
        except (TypeError, ValueError):
            logger.warning(
                "chat.ratelimit.daily_counter_corrupt",
                extra={"key": key, "raw": str(raw)[:32]},
            )
            current = 0
        if current + projected_tokens > cap:
            raise ChatRateLimitedError(
                correlation_id=correlation_id,
                retry_after_seconds=_seconds_until_utc_midnight(),
                cause="daily_tokens",
            )

    async def record_chat_token_spend(
        self, user_id: str, tokens_used: int
    ) -> None:
        """INCRBY the per-user daily counter; sets a 25h TTL on first write.

        Idempotent — subsequent INCRBYs do not reset the TTL (so the
        daily counter genuinely expires the day after the first spend
        landed in it, regardless of how many turns followed).
        """
        if tokens_used <= 0:
            return
        key = f"rate_limit:chat:daily_tokens:{user_id}:{_today_utc_suffix()}"
        new_total = await self._redis.incrby(key, tokens_used)
        # Conditional EXPIRE: only set if no TTL is currently active. Use
        # `EXPIRE ... NX` if the redis-py API is recent enough; fall back
        # to a TTL-then-EXPIRE two-step otherwise.
        try:
            # redis-py >= 4.6 supports the `nx=True` keyword on expire().
            await self._redis.expire(key, 25 * 3600, nx=True)
        except TypeError:
            ttl = await self._redis.ttl(key)
            if ttl is None or ttl < 0:
                await self._redis.expire(key, 25 * 3600)
        logger.debug(
            "chat.ratelimit.token_spend_recorded",
            extra={
                "user_id_hash": _hash_user_id_for_log(user_id),
                "tokens_added": tokens_used,
                "daily_total_after": int(new_total),
            },
        )


def _hash_user_id_for_log(user_id: str) -> str:
    """Hash a user_id string for log fields (mirrors ``_hash_user_id``).

    Local helper rather than an import from ``session_handler`` so the
    rate-limiter doesn't pull the chat agent module at import time.
    """
    import hashlib
    import uuid as _uuid

    try:
        raw = _uuid.UUID(user_id).bytes
    except (ValueError, AttributeError, TypeError):
        raw = str(user_id).encode("utf-8")
    return hashlib.blake2b(raw, digest_size=8).hexdigest()
