import time

import redis.asyncio as aioredis

from app.core.exceptions import AuthenticationError


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
