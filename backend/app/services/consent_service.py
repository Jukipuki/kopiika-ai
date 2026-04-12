"""Consent service — append-only grant/read of user consent records."""

from __future__ import annotations

from typing import Any

from sqlmodel import desc, select
from sqlmodel.ext.asyncio.session import AsyncSession as SQLModelAsyncSession

from app.models.consent import UserConsent
from app.models.user import User


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
    record = UserConsent(
        user_id=user.id,
        consent_type=consent_type,
        version=version,
        locale=locale,
        ip=ip,
        user_agent=user_agent,
    )
    session.add(record)
    # Build a detached copy with all attributes eagerly captured. All fields
    # are already populated by the UserConsent constructor (id and granted_at
    # via default_factory), so we don't need a DB round-trip to learn them.
    detached = UserConsent(
        id=record.id,
        user_id=record.user_id,
        consent_type=record.consent_type,
        version=record.version,
        granted_at=record.granted_at,
        locale=record.locale,
        ip=record.ip,
        user_agent=record.user_agent,
    )
    await session.commit()
    return detached


async def get_current_consent_status(
    session: SQLModelAsyncSession,
    user: User,
    consent_type: str,
    version: str,
) -> dict[str, Any]:
    """Return the current consent status for a user + type + version.

    Shape: ``{ hasCurrentConsent, version, grantedAt | None, locale | None }``.
    """
    statement = (
        select(UserConsent)
        .where(UserConsent.user_id == user.id)
        .where(UserConsent.consent_type == consent_type)
        .where(UserConsent.version == version)
        .order_by(desc(UserConsent.granted_at))
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
        }

    return {
        "hasCurrentConsent": True,
        "version": row.version,
        "grantedAt": row.granted_at.isoformat(),
        "locale": row.locale,
    }
