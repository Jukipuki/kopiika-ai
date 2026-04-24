"""Consent service — append-only grant/revoke/read of user consent records."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func
from sqlmodel import desc, select
from sqlmodel.ext.asyncio.session import AsyncSession as SQLModelAsyncSession

from app.core.consent import (
    CONSENT_TYPE_CHAT_PROCESSING,
    CURRENT_CHAT_CONSENT_VERSION,
)
from app.models.consent import UserConsent
from app.models.user import User


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
    await session.commit()
    # TODO(10.1b): cascade chat_sessions delete here — terminate any active
    # chat sessions + delete chat_messages per the "Consent Drift Policy"
    # (architecture.md §Consent Drift Policy). 10.1a leaves this as a no-op
    # because chat_sessions / chat_messages do not exist until 10.1b.
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
