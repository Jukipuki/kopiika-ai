"""Consent service — append-only grant/revoke/read of user consent records."""

from __future__ import annotations

import hashlib
import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete as sa_delete
from sqlalchemy import func
from sqlmodel import desc, select
from sqlmodel.ext.asyncio.session import AsyncSession as SQLModelAsyncSession

from app.core.consent import (
    CONSENT_TYPE_CHAT_PROCESSING,
    CURRENT_CHAT_CONSENT_VERSION,
)
from app.models.consent import UserConsent
from app.models.user import User

_logger = logging.getLogger(__name__)


def _hash_user_id(user_id: uuid.UUID) -> str:
    # 64-bit blake2b prefix — matches session_handler._hash_user_id so
    # chat.* log events join across modules. Per Story 10.4a AC #12.
    return hashlib.blake2b(user_id.bytes, digest_size=8).hexdigest()


def _utcnow_naive() -> datetime:
    # Match the UserConsent model's convention (tz-naive UTC) so granted_at
    # and revoked_at are directly comparable without tz gymnastics.
    return datetime.now(UTC).replace(tzinfo=None)


async def grant_consent(
    session: SQLModelAsyncSession,
    user: User,
    consent_type: str,
    version: str,
    locale: str,
    ip: str | None,
    user_agent: str | None,
) -> UserConsent:
    """Insert a new UserConsent row. Append-only — never updates existing rows.

    Captures the returned record's attributes into a detached copy before
    ``session.commit()`` expires the original instance, so callers can read
    fields (``id``, ``granted_at``, …) without triggering an implicit refresh
    round-trip.
    """
    granted_at = _utcnow_naive()
    record = UserConsent(
        user_id=user.id,
        consent_type=consent_type,
        version=version,
        granted_at=granted_at,
        locale=locale,
        ip=ip,
        user_agent=user_agent,
    )
    session.add(record)
    # Build a detached copy with all attributes eagerly captured so callers
    # can read fields without triggering a post-commit refresh round-trip.
    detached = UserConsent(
        id=record.id,
        user_id=record.user_id,
        consent_type=record.consent_type,
        version=record.version,
        granted_at=record.granted_at,
        locale=record.locale,
        ip=record.ip,
        user_agent=record.user_agent,
        revoked_at=record.revoked_at,
    )
    await session.commit()
    return detached


async def revoke_chat_consent(
    session: SQLModelAsyncSession,
    user: User,
    locale: str,
    ip: str | None,
    user_agent: str | None,
) -> UserConsent:
    """Revoke chat_processing consent by appending a new row with revoked_at set.

    Append-only: never UPDATEs an existing row. The revocation event is
    represented by a new row where ``consent_type='chat_processing'``,
    ``version=CURRENT_CHAT_CONSENT_VERSION``, and ``revoked_at`` is set to
    the current UTC timestamp. ``get_current_consent_status`` reads
    "most-recent row wins" to resolve grant→revoke→regrant sequences.

    Uses the same detached-copy pattern as ``grant_consent`` to avoid
    post-commit attribute expiry under the async session.
    """
    revoked_at = _utcnow_naive()
    # granted_at=None is load-bearing: revoke rows are discriminated from
    # grant rows by having granted_at NULL + revoked_at set. See H1 fix.
    record = UserConsent(
        user_id=user.id,
        consent_type=CONSENT_TYPE_CHAT_PROCESSING,
        version=CURRENT_CHAT_CONSENT_VERSION,
        granted_at=None,
        locale=locale,
        ip=ip,
        user_agent=user_agent,
        revoked_at=revoked_at,
    )
    session.add(record)
    detached = UserConsent(
        id=record.id,
        user_id=record.user_id,
        consent_type=record.consent_type,
        version=record.version,
        granted_at=None,
        locale=record.locale,
        ip=record.ip,
        user_agent=record.user_agent,
        revoked_at=record.revoked_at,
    )
    # Cascade: delete all chat_sessions for this user in the same transaction
    # as the revocation-row INSERT. The ON DELETE CASCADE on
    # ``chat_messages.session_id`` removes their messages atomically. Per the
    # Consent Drift Policy, revoke succeeds iff cascade succeeds.
    #
    # Story 10.4a: terminate backend chat sessions *before* the DB cascade so
    # in-flight streams cancel cleanly (Phase A per ADR-0004 — no remote
    # state, so the terminator is a no-op iteration; Phase B will call
    # bedrock-agentcore:DeleteSession per session). Fail-open: termination
    # errors are logged but do NOT block revocation — consent revocation is
    # legally required to succeed, and an orphan backend session becomes a
    # paper tiger once its chat_sessions row is gone. Do NOT "fix" this into
    # a fail-closed that propagates the exception.
    #
    # Local imports mirror the 10.1b hand-off pattern (avoids circular risk
    # if chat_session_service ever grows a consent read).
    from app.agents.chat.session_handler import (
        terminate_all_user_sessions_fail_open,
    )
    from app.models.chat_session import ChatSession

    try:
        await terminate_all_user_sessions_fail_open(session, user)
    except Exception as exc:  # noqa: BLE001 — fail-open is load-bearing
        _logger.error(
            "chat.session.termination_failed",
            extra={
                "user_id_hash": _hash_user_id(user.id),
                "error_class": type(exc).__name__,
                "error_message": str(exc)[:200],
            },
        )

    await session.exec(
        sa_delete(ChatSession).where(ChatSession.user_id == user.id)
    )
    await session.commit()
    return detached


async def get_current_consent_status(
    session: SQLModelAsyncSession,
    user: User,
    consent_type: str,
    version: str,
) -> dict[str, Any]:
    """Return the current consent status for a user + type + required version.

    Resolution: the most-recent row for ``(user_id, consent_type)`` wins.
    ``hasCurrentConsent`` is true IFF that row exists AND is not revoked AND
    its version matches the required version. This handles grant→revoke and
    grant→revoke→regrant sequences uniformly.

    Shape: ``{ hasCurrentConsent, version, grantedAt | None, locale | None,
    revokedAt | None }``.
    """
    # Order by event-time = COALESCE(granted_at, revoked_at) so grant rows
    # (granted_at set, revoked_at NULL) and revoke rows (granted_at NULL,
    # revoked_at set) both sort by the moment they happened. Secondary sort
    # on ``id`` (M4 fix) guarantees deterministic ordering when two rows
    # share a timestamp down to the microsecond (possible under clock skew
    # or clock-mocked tests).
    event_time = func.coalesce(UserConsent.granted_at, UserConsent.revoked_at)
    statement = (
        select(UserConsent)
        .where(UserConsent.user_id == user.id)
        .where(UserConsent.consent_type == consent_type)
        .order_by(desc(event_time), desc(UserConsent.id))
        .limit(1)
    )
    result = await session.exec(statement)
    row = result.first()

    if row is None:
        return {
            "hasCurrentConsent": False,
            "version": version,
            "grantedAt": None,
            "locale": None,
            "revokedAt": None,
        }

    has_current = row.revoked_at is None and row.version == version
    # ``version`` in the response is the server's required/current version
    # (same shape as Story 5.2), not the stored row's version. ``grantedAt``
    # is populated only on grant rows; ``revokedAt`` only on revoke rows —
    # the two are mutually exclusive per-row, so the client always sees
    # exactly one timestamp reflecting the most-recent event.
    return {
        "hasCurrentConsent": has_current,
        "version": version,
        "grantedAt": row.granted_at.isoformat() if row.granted_at else None,
        "locale": row.locale,
        "revokedAt": row.revoked_at.isoformat() if row.revoked_at else None,
    }
