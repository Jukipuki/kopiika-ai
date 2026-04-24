"""Chat canary token loader — Story 10.4b AC #2.

# SCOPE: Loads three high-entropy tokens from AWS Secrets Manager
# (`{AWS_SECRETS_PREFIX}/chat-canaries`) for injection into the hardened chat
# system prompt. Never logs canary values. Caches for 15 minutes so the
# operator rotation cadence (monthly, via `aws secretsmanager put-secret-value`)
# propagates within one cache window. No explicit "rotate now" hook — the TTL
# is the only invalidation path.
#
# Non-goals (owned by sibling/downstream stories):
#   - Rotation schedule / runbook              → Story 10.9
#   - CanaryLeaked CloudWatch metric + alarm   → Story 10.9
#   - The detector itself                      → canary_detector.py
#   - The system-prompt that consumes these    → system_prompt.py
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from dataclasses import dataclass

from app.core.config import settings

logger = logging.getLogger(__name__)

# Module-level lock so concurrent cold-cache turns share a single Secrets
# Manager round-trip. Without this, two turns entering `get_canary_set`
# simultaneously on a cold/expired cache would each hit AWS and each emit
# `chat.canary.loaded` with `cache_hit=False`, breaking AC #2's "one AWS
# hit per TTL window" invariant.
_cache_lock = asyncio.Lock()

_CANARY_PATTERN = re.compile(r"^[A-Za-z0-9_-]{24,}$")

# 15-minute default TTL (AC #2). Not env-overridable here — sourced from
# settings.CHAT_CANARY_CACHE_TTL_SECONDS at first-call for load-test tuning.
_CANARY_CACHE_TTL_SECONDS: int = 900

# Dev-fallback tokens (AC #2). NOT a secret; production uses Secrets Manager.
# Three distinct 32-char url-safe strings so the full handler pipeline is
# exercisable end-to-end under LLM_PROVIDER != "bedrock" without mocking AWS.
# High-entropy by design — low-entropy placeholders (e.g. `devAAAA...`) would
# false-positive against any prose mentioning "devA..." and let dev-time
# wording iteration silently trip the canary scan. If you regenerate these,
# use `python -c "import secrets; print(secrets.token_urlsafe(24))"`.
_DEV_FALLBACK_CANARIES = (
    "kAn3_fQ9mT2rN5pX8vW1jL4hY7eA6dB0",
    "mVr6_KpZ2nY9dA3hF1wB5jX8cQ7gL4tM",
    "pGu7_RqL3vN9kX2sT6hY1bM4wA0dC5fJ",
)
_DEV_FALLBACK_VERSION_ID = "dev-fallback"


@dataclass(frozen=True)
class CanarySet:
    canary_a: str
    canary_b: str
    canary_c: str
    version_id: str  # AWSCURRENT version id from Secrets Manager, or "dev-fallback"

    def as_tuple(self) -> tuple[str, str, str]:
        return (self.canary_a, self.canary_b, self.canary_c)


class CanaryLoadError(Exception):
    """Raised on Secrets Manager shape/validation drift.

    Hard-fails the turn — the Story 10.9 rotation runbook generates tokens
    via ``python -c "import secrets; print(secrets.token_urlsafe(24))"`` so
    shape drift means someone rotated by hand with the wrong format.
    """


# ----------------------------------------------------------------------
# Cache
# ----------------------------------------------------------------------

_cache: CanarySet | None = None
_cache_expires_at: float = 0.0


def _resolve_secret_id() -> str:
    """Explicit override → setting; else construct from AWS_SECRETS_PREFIX."""
    if settings.CHAT_CANARIES_SECRET_ID:
        return settings.CHAT_CANARIES_SECRET_ID
    prefix = settings.AWS_SECRETS_PREFIX
    if not prefix:
        raise CanaryLoadError(
            "Neither CHAT_CANARIES_SECRET_ID nor AWS_SECRETS_PREFIX is set; "
            "cannot resolve the chat-canaries secret name."
        )
    return f"{prefix}/chat-canaries"


def _validate_payload(raw: str) -> tuple[str, str, str]:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise CanaryLoadError(
            "Secret payload is not valid JSON. Expected "
            '{"canary_a": "<token>", "canary_b": "<token>", "canary_c": "<token>"}.'
        ) from exc
    if not isinstance(payload, dict):
        raise CanaryLoadError(
            "Secret payload must be a JSON object with three canary_* keys."
        )
    missing = [k for k in ("canary_a", "canary_b", "canary_c") if k not in payload]
    if missing:
        raise CanaryLoadError(
            f"Secret payload missing required key(s): {', '.join(missing)}."
        )
    tokens = (payload["canary_a"], payload["canary_b"], payload["canary_c"])
    for name, token in zip(("canary_a", "canary_b", "canary_c"), tokens, strict=True):
        if not isinstance(token, str) or not _CANARY_PATTERN.match(token):
            raise CanaryLoadError(
                f"Token {name} fails validation: must be >= 24 chars, "
                "charset [A-Za-z0-9_-]."
            )
    if len(set(tokens)) != 3:
        raise CanaryLoadError("Canary tokens must be distinct.")
    return tokens


async def _fetch_from_secrets_manager() -> CanarySet:
    # boto3 synchronous client in a threadpool — the repo already uses this
    # pattern for kms/s3 (no aioboto3 dep). See app/core/crypto.py:44-46.
    import boto3  # local import: heavy, optional in unit tests
    from botocore.exceptions import BotoCoreError, ClientError

    secret_id = _resolve_secret_id()

    def _call() -> dict:
        client = boto3.client("secretsmanager", region_name=settings.AWS_REGION)
        return client.get_secret_value(SecretId=secret_id)

    try:
        resp = await asyncio.to_thread(_call)
    except (ClientError, BotoCoreError) as exc:
        # Do NOT emit `chat.canary.load_failed` here — the session handler
        # owns that event so Story 10.9's metric filter sees exactly one
        # emission per failed turn (with correlation_id + db_session_id).
        raise CanaryLoadError(
            f"Secrets Manager get_secret_value failed: {type(exc).__name__}"
        ) from exc

    raw = resp.get("SecretString")
    if not raw:
        raise CanaryLoadError("Secret has no SecretString (binary-only unsupported).")
    tokens = _validate_payload(raw)
    version_id = resp.get("VersionId") or "unknown"
    return CanarySet(
        canary_a=tokens[0],
        canary_b=tokens[1],
        canary_c=tokens[2],
        version_id=version_id,
    )


async def load_canaries() -> CanarySet:
    """Uncached load. ``get_canary_set`` is the normal entry point."""
    if settings.LLM_PROVIDER != "bedrock":
        return CanarySet(
            canary_a=_DEV_FALLBACK_CANARIES[0],
            canary_b=_DEV_FALLBACK_CANARIES[1],
            canary_c=_DEV_FALLBACK_CANARIES[2],
            version_id=_DEV_FALLBACK_VERSION_ID,
        )
    return await _fetch_from_secrets_manager()


async def get_canary_set() -> CanarySet:
    """Cached load. TTL = ``settings.CHAT_CANARY_CACHE_TTL_SECONDS`` (900s default).

    Emits ``chat.canary.loaded`` at DEBUG on each call (per-turn observability,
    filtered out of INFO-and-above prod ingestion).
    """
    global _cache, _cache_expires_at
    now = time.monotonic()
    cache_hit = _cache is not None and now < _cache_expires_at
    if not cache_hit:
        async with _cache_lock:
            # Re-check under the lock — a concurrent waiter may have
            # populated the cache while we were queued.
            now = time.monotonic()
            cache_hit = _cache is not None and now < _cache_expires_at
            if not cache_hit:
                _cache = await load_canaries()
                ttl = (
                    settings.CHAT_CANARY_CACHE_TTL_SECONDS or _CANARY_CACHE_TTL_SECONDS
                )
                _cache_expires_at = now + ttl
    assert _cache is not None
    logger.debug(
        "chat.canary.loaded",
        extra={
            "canary_set_version_id": _cache.version_id,
            "canary_set_source": (
                "secrets_manager"
                if _cache.version_id != _DEV_FALLBACK_VERSION_ID
                else "dev-fallback"
            ),
            "cache_hit": cache_hit,
        },
    )
    return _cache


def _reset_canary_cache_for_tests() -> None:
    """Test-only helper — clears the cache so TTL behavior can be exercised."""
    global _cache, _cache_expires_at
    _cache = None
    _cache_expires_at = 0.0
