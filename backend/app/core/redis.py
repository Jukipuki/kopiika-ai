import json
from collections.abc import AsyncGenerator

import redis as sync_redis
import redis.asyncio as aioredis

from app.core.config import settings

_redis_client: aioredis.Redis | None = None

# Redis key patterns
JOB_PROGRESS_CHANNEL = "job:progress:{job_id}"
JOB_STATE_KEY = "job:state:{job_id}"
JOB_STATE_TTL = 3600  # 1 hour


async def get_redis() -> aioredis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = aioredis.from_url(
            settings.REDIS_URL, decode_responses=True
        )
    return _redis_client


async def close_redis() -> None:
    global _redis_client
    if _redis_client is not None:
        await _redis_client.aclose()
        _redis_client = None


# --- Sync helpers (for Celery workers) ---


def publish_job_progress(job_id: str, data: dict) -> None:
    """Publish a job progress event via Redis PUBLISH and store latest state.

    Used by Celery tasks (sync context). Creates a short-lived sync Redis
    connection each call to avoid sharing connections across Celery workers.
    """
    channel = JOB_PROGRESS_CHANNEL.format(job_id=job_id)
    state_key = JOB_STATE_KEY.format(job_id=job_id)
    payload = json.dumps(data)

    client = sync_redis.from_url(settings.REDIS_URL, decode_responses=True)
    try:
        # Store latest state for reconnecting clients
        client.set(state_key, payload, ex=JOB_STATE_TTL)
        # Publish to subscribers
        client.publish(channel, payload)
    finally:
        client.close()


# --- Async helpers (for FastAPI SSE endpoint) ---


async def get_job_state(job_id: str) -> dict | None:
    """Get the latest stored job state from Redis (for reconnection)."""
    client = await get_redis()
    state_key = JOB_STATE_KEY.format(job_id=job_id)
    raw = await client.get(state_key)
    if raw is None:
        return None
    return json.loads(raw)


async def subscribe_job_progress(job_id: str) -> AsyncGenerator[dict, None]:
    """Subscribe to job progress events via Redis pub/sub (subscribes EAGERLY).

    This is a coroutine that subscribes to the channel before returning, so
    the subscription is active before the caller checks stored state — preventing
    the race condition where a fast-completing task publishes events before the
    caller starts listening.

    Returns an async generator that yields parsed event dicts and terminates
    after a terminal event (job-complete or job-failed).
    """
    channel = JOB_PROGRESS_CHANNEL.format(job_id=job_id)
    client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    pubsub = client.pubsub()
    await pubsub.subscribe(channel)  # Subscribe NOW, before caller checks state

    async def _listener() -> AsyncGenerator[dict, None]:
        try:
            async for message in pubsub.listen():
                if message["type"] != "message":
                    continue
                data = json.loads(message["data"])
                yield data
                if data.get("event") in ("job-complete", "job-failed"):
                    break
        finally:
            await pubsub.unsubscribe(channel)
            await pubsub.aclose()
            await client.aclose()

    return _listener()
