"""Consent API routes — POST/GET /users/me/consent.

Client-side enforcement story — see the "Client-side enforcement is enough"
design decision in Story 5.2. These endpoints deliberately do NOT gate any
other endpoint in the app; they only record grants and report current
status. Server-side `require_consent` enforcement is tracked as a separate
follow-up alongside Story 5.6 (compliance audit trail).
"""

from __future__ import annotations

import logging
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel
from sqlmodel.ext.asyncio.session import AsyncSession as SQLModelAsyncSession

from app.api.deps import get_current_user, get_db, get_rate_limiter
from app.services.rate_limiter import RateLimiter
from app.core.consent import CONSENT_TYPE_AI_PROCESSING, CURRENT_CONSENT_VERSION
from app.core.request import get_client_ip
from app.models.user import User
from app.services import consent_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/users/me", tags=["consent"])


class GrantConsentRequest(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    version: str = Field(min_length=1)
    locale: Literal["uk", "en"]


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
    """Record a consent grant. Append-only — always creates a new row."""
    await rate_limiter.check_consent_rate_limit(str(current_user.id))

    # Reject stale frontend version strings so the frontend cannot silently
    # grant against an out-of-date privacy text.
    if body.version != CURRENT_CONSENT_VERSION:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": {
                    "code": "CONSENT_VERSION_MISMATCH",
                    "message": (
                        "Consent version does not match current server version."
                    ),
                    "details": {
                        "expected": CURRENT_CONSENT_VERSION,
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
        consent_type=CONSENT_TYPE_AI_PROCESSING,
        version=body.version,
        locale=body.locale,
        ip=ip,
        user_agent=user_agent,
    )

    logger.info(
        "Consent granted",
        extra={
            "user_id": str(record.user_id),
            "consent_type": CONSENT_TYPE_AI_PROCESSING,
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
        Literal["ai_processing"], Query(alias="type")
    ] = CONSENT_TYPE_AI_PROCESSING,
) -> ConsentStatusResponse:
    """Return whether the current user has consented to the current version."""
    status_dict = await consent_service.get_current_consent_status(
        session=session,
        user=current_user,
        consent_type=type,
        version=CURRENT_CONSENT_VERSION,
    )
    return ConsentStatusResponse(
        has_current_consent=status_dict["hasCurrentConsent"],
        version=status_dict["version"],
        granted_at=status_dict["grantedAt"],
        locale=status_dict["locale"],
    )
