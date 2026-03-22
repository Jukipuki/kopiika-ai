from collections.abc import AsyncGenerator
from typing import Annotated, Any

from fastapi import Depends, HTTPException, status
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession as SQLModelAsyncSession

from app.core.database import get_session
from app.core.redis import get_redis
from app.core.security import get_current_user_payload
from app.models.user import User
from app.services.cognito_service import CognitoService
from app.services.rate_limiter import RateLimiter

_cognito_service: CognitoService | None = None


async def get_db() -> AsyncGenerator[SQLModelAsyncSession, None]:
    async for session in get_session():
        yield session


def get_cognito_service() -> CognitoService:
    global _cognito_service
    if _cognito_service is None:
        _cognito_service = CognitoService()
    return _cognito_service


async def get_rate_limiter() -> RateLimiter:
    redis = await get_redis()
    return RateLimiter(redis=redis)


async def get_current_user(
    payload: Annotated[dict[str, Any], Depends(get_current_user_payload)],
    session: Annotated[SQLModelAsyncSession, Depends(get_db)],
) -> User:
    cognito_sub = payload.get("sub")
    if not cognito_sub:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "INVALID_TOKEN", "message": "Token missing sub claim"}},
        )

    statement = select(User).where(User.cognito_sub == cognito_sub)
    result = await session.exec(statement)
    user = result.first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "USER_NOT_FOUND", "message": "User not found"}},
        )
    return user
