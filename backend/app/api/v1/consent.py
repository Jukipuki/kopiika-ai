"""Consent API routes — POST/GET/DELETE /users/me/consent.

Client-side enforcement story — see the "Client-side enforcement is enough"
design decision in Story 5.2. These endpoints deliberately do NOT gate any
other endpoint in the app; they only record grants/revocations and report
current status.

Two independent consent streams share these endpoints:
- ``ai_processing`` (Story 5.2) — batch pipeline; revocation is whole-account
  deletion via ``DELETE /users/me/account``.
- ``chat_processing`` (Story 10.1a) — conversational surface; independently
  revocable via ``DELETE /users/me/consent?type=chat_processing``.
"""

from __future__ import annotations

import logging
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel
from sqlmodel import desc, select
from sqlmodel.ext.asyncio.session import AsyncSession as SQLModelAsyncSession

from app.api.deps import get_current_user, get_db, get_rate_limiter
from app.core.consent import (
    CONSENT_TYPE_AI_PROCESSING,
    CONSENT_TYPE_CHAT_PROCESSING,
    CURRENT_CHAT_CONSENT_VERSION,
    CURRENT_CONSENT_VERSION,
)
from app.core.request import get_client_ip
from app.models.consent import UserConsent
from app.models.user import User
from app.services import consent_service
from app.services.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/users/me", tags=["consent"])


ConsentTypeLiteral = Literal["ai_processing", "chat_processing"]


def _required_version(consent_type: str) -> str:
    if consent_type == CONSENT_TYPE_CHAT_PROCESSING:
        return CURRENT_CHAT_CONSENT_VERSION
    return CURRENT_CONSENT_VERSION


class GrantConsentRequest(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    version: str = Field(min_length=1)
    locale: Literal["uk", "en"]
    # Default preserves backward compatibility with Story 5.2 clients that
    # POST without a consent_type field.
    consent_type: ConsentTypeLiteral = CONSENT_TYPE_AI_PROCESSING


class ConsentResponse(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    id: str
    user_id: str
    consent_type: str
    version: str
    granted_at: str
    locale: str
    ip: str | None = None
    user_agent: str | None = None


class ConsentStatusResponse(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    has_current_consent: bool
    version: str
    granted_at: str | None = None
    locale: str | None = None
    revoked_at: str | None = None


@router.post(
    "/consent",
    response_model=ConsentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def grant_consent_endpoint(
    body: GrantConsentRequest,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[SQLModelAsyncSession, Depends(get_db)],
    rate_limiter: Annotated[RateLimiter, Depends(get_rate_limiter)],
) -> ConsentResponse:
    """Record a consent grant. Append-only — always creates a new row.

    Version validation is per-type: ``ai_processing`` must match
    ``CURRENT_CONSENT_VERSION``, ``chat_processing`` must match
    ``CURRENT_CHAT_CONSENT_VERSION``. Mismatch returns 422 with the
    consent_type echoed in ``details`` so the client can recover.
    """
    await rate_limiter.check_consent_rate_limit(str(current_user.id))

    expected_version = _required_version(body.consent_type)
    if body.version != expected_version:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": {
                    "code": "CONSENT_VERSION_MISMATCH",
                    "message": (
                        "Consent version does not match current server version."
                    ),
                    "details": {
                        "consentType": body.consent_type,
                        "expected": expected_version,
                        "received": body.version,
                    },
                }
            },
        )

    ip = get_client_ip(request)
    user_agent = request.headers.get("user-agent")

    record = await consent_service.grant_consent(
        session=session,
        user=current_user,
        consent_type=body.consent_type,
        version=body.version,
        locale=body.locale,
        ip=ip,
        user_agent=user_agent,
    )

    logger.info(
        "Consent granted",
        extra={
            "user_id": str(record.user_id),
            "consent_type": body.consent_type,
            "version": body.version,
            "action": "consent_grant",
        },
    )

    return ConsentResponse(
        id=str(record.id),
        user_id=str(record.user_id),
        consent_type=record.consent_type,
        version=record.version,
        granted_at=record.granted_at.isoformat(),
        locale=record.locale,
        ip=record.ip,
        user_agent=record.user_agent,
    )


@router.get("/consent", response_model=ConsentStatusResponse)
async def get_consent_status_endpoint(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[SQLModelAsyncSession, Depends(get_db)],
    type: Annotated[
        ConsentTypeLiteral, Query(alias="type")
    ] = CONSENT_TYPE_AI_PROCESSING,
) -> ConsentStatusResponse:
    """Return whether the current user has consented to the current version
    of the given consent stream."""
    required_version = _required_version(type)
    status_dict = await consent_service.get_current_consent_status(
        session=session,
        user=current_user,
        consent_type=type,
        version=required_version,
    )
    return ConsentStatusResponse(
        has_current_consent=status_dict["hasCurrentConsent"],
        version=status_dict["version"],
        granted_at=status_dict["grantedAt"],
        locale=status_dict["locale"],
        revoked_at=status_dict["revokedAt"],
    )


@router.delete("/consent", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_consent_endpoint(
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[SQLModelAsyncSession, Depends(get_db)],
    rate_limiter: Annotated[RateLimiter, Depends(get_rate_limiter)],
    type: Annotated[ConsentTypeLiteral, Query(alias="type")],
) -> None:
    """Revoke consent. Currently only ``chat_processing`` is revocable here.

    ``ai_processing`` revocation is whole-account deletion (Story 5.5) — we
    reject it explicitly with ``CONSENT_TYPE_NOT_REVOCABLE`` rather than
    silently no-opping, so a client misuse is surfaced.
    """
    if type == CONSENT_TYPE_AI_PROCESSING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": {
                    "code": "CONSENT_TYPE_NOT_REVOCABLE",
                    "message": (
                        "ai_processing consent is revoked via account deletion "
                        "— see DELETE /users/me/account."
                    ),
                    "details": {"consentType": type},
                }
            },
        )

    # Grant + revoke share the same rate-limit bucket (AC #8) so abuse
    # (grant→revoke loop to spam audit log) is bounded.
    await rate_limiter.check_consent_rate_limit(str(current_user.id))

    # Reject revoke-without-prior-consent (M2 fix). A user who has never
    # granted chat consent cannot revoke it — silently inserting an orphan
    # revoke row would pollute the audit log and open a cheap INSERT vector.
    if not await _has_any_chat_consent_row(session, current_user):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": {
                    "code": "NO_ACTIVE_CONSENT_TO_REVOKE",
                    "message": (
                        "No chat_processing consent has been granted — "
                        "nothing to revoke."
                    ),
                    "details": {"consentType": type},
                }
            },
        )

    ip = get_client_ip(request)
    user_agent = request.headers.get("user-agent")
    # ``locale`` isn't part of the DELETE contract — fall back to the most
    # recent chat-consent row's locale, else "en". This keeps the audit row
    # populated without adding a body to a DELETE.
    locale = await _resolve_revoke_locale(session, current_user)

    await consent_service.revoke_chat_consent(
        session=session,
        user=current_user,
        locale=locale,
        ip=ip,
        user_agent=user_agent,
    )

    logger.info(
        "Consent revoked",
        extra={
            "user_id": str(current_user.id),
            "consent_type": CONSENT_TYPE_CHAT_PROCESSING,
            "action": "consent_revoke",
        },
    )


async def _has_any_chat_consent_row(
    session: SQLModelAsyncSession, user: User
) -> bool:
    """Return True iff the user has *any* chat_processing row (grant or revoke).

    M2 fix: DELETE is only legal once a grant has existed. We don't require
    the most-recent row to be non-revoked — a re-revoke is idempotent and
    still legal for users with prior history.
    """
    statement = (
        select(UserConsent.id)
        .where(UserConsent.user_id == user.id)
        .where(UserConsent.consent_type == CONSENT_TYPE_CHAT_PROCESSING)
        .limit(1)
    )
    result = await session.exec(statement)
    return result.first() is not None


async def _resolve_revoke_locale(
    session: SQLModelAsyncSession, user: User
) -> str:
    """Pick the locale from the most-recent chat-consent grant row.

    Prefers grant rows (granted_at IS NOT NULL) — the grant locale is the
    user's actual preference at the time they consented; revoke rows just
    re-use whatever locale was resolved on the previous revoke.
    """
    statement = (
        select(UserConsent.locale)
        .where(UserConsent.user_id == user.id)
        .where(UserConsent.consent_type == CONSENT_TYPE_CHAT_PROCESSING)
        .where(UserConsent.granted_at.is_not(None))
        .order_by(desc(UserConsent.granted_at), desc(UserConsent.id))
        .limit(1)
    )
    result = await session.exec(statement)
    locale = result.first()
    return locale or "en"
