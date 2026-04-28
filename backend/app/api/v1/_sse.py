"""Shared SSE helpers for Story 10.5 chat streaming + existing jobs streaming.

# SCOPE: a single query-string JWT auth helper used by both SSE routes,
# plus common response headers. Extracted so the two routes don't drift
# in auth semantics.
#
# Non-goals:
#   - Rate-limit middleware             → Story 10.11
#   - EventSource reconnect token       → out of scope (the current
#                                        contract is single-shot per turn)
"""

from __future__ import annotations

import uuid

from fastapi import HTTPException, status
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession as SQLModelAsyncSession

from app.core.security import verify_token
from app.models.user import User


SSE_RESPONSE_HEADERS: dict[str, str] = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}


def resolve_sse_jwt(
    authorization: str | None, token: str | None
) -> str:
    """Pick the JWT from ``Authorization: Bearer ...`` or ``?token=`` query.

    Header wins when both are present. Raises 401 if neither yields a value.
    Lifted here so chat + jobs SSE routes share one resolution path — when
    a third SSE endpoint shows up, plumb it through this helper too rather
    than re-implementing the precedence rules in-route.

    Note: the jobs SSE route at ``api/v1/jobs.py`` still uses query-only —
    see TD-144 for the migration plan (the FE jobs client hasn't moved off
    EventSource yet, so there's no live bug there).
    """
    if authorization and authorization.lower().startswith("bearer "):
        bearer = authorization[7:].strip()
        if bearer:
            return bearer
    if token:
        return token
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={
            "error": {
                "code": "MISSING_TOKEN",
                "message": (
                    "Authorization header (Bearer) or ?token= query param "
                    "is required."
                ),
            }
        },
    )


async def get_user_id_from_token(
    token: str, session: SQLModelAsyncSession
) -> uuid.UUID:
    """Extract user_id from a JWT token passed as an SSE query-string arg.

    EventSource does not support Authorization headers, so the two SSE
    endpoints (jobs + chat) both use ?token=<JWT>. Duplicated the
    ``cognito_sub → user_id`` lookup from ``deps.get_current_user_id`` so
    the two paths remain sync'd if ``deps.py`` auth logic changes, update
    this helper as well.
    """
    payload = await verify_token(token)
    cognito_sub = payload.get("sub")
    if not cognito_sub:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": {
                    "code": "INVALID_TOKEN",
                    "message": "Token missing sub claim",
                }
            },
        )
    result = await session.exec(
        select(User.id).where(User.cognito_sub == cognito_sub)
    )
    user_id = result.first()
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": {
                    "code": "USER_NOT_FOUND",
                    "message": "User not found",
                }
            },
        )
    return user_id


__all__ = ["SSE_RESPONSE_HEADERS", "get_user_id_from_token", "resolve_sse_jwt"]
