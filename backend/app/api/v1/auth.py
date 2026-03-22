import logging
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Request, status
from jose import jwt as jose_jwt
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator
from pydantic.alias_generators import to_camel
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession as SQLModelAsyncSession

from app.api.deps import get_cognito_service, get_current_user, get_db, get_rate_limiter
from app.models.user import User
from app.services.cognito_service import CognitoService
from app.services.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


def _get_client_ip(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


class SignupRequest(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    email: EmailStr
    password: str = Field(min_length=8)


class SignupResponse(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    message: str
    user_id: str


class VerifyRequest(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    email: EmailStr
    code: str


class MessageResponse(BaseModel):
    message: str


class ResendVerificationRequest(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    email: EmailStr


class LoginRequest(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    email: EmailStr
    password: str = Field(min_length=1)


class UserInfo(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    id: str
    email: str
    locale: str


class LoginResponse(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    access_token: str
    refresh_token: str
    expires_in: int
    user: UserInfo


class RefreshTokenRequest(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    refresh_token: str
    email: EmailStr | None = None


class RefreshTokenResponse(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    access_token: str
    expires_in: int


class UserProfileResponse(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    id: str
    email: str
    locale: str
    is_verified: bool
    created_at: str


class UpdateProfileRequest(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    locale: str

    @field_validator("locale")
    @classmethod
    def validate_locale(cls, v: str) -> str:
        if v not in ("uk", "en"):
            msg = "Locale must be 'uk' or 'en'"
            raise ValueError(msg)
        return v


@router.post("/login", response_model=LoginResponse)
async def login(
    body: LoginRequest,
    request: Request,
    session: Annotated[SQLModelAsyncSession, Depends(get_db)],
    cognito: Annotated[CognitoService, Depends(get_cognito_service)],
    rate_limiter: Annotated[RateLimiter, Depends(get_rate_limiter)],
) -> LoginResponse:
    ip = _get_client_ip(request)

    await rate_limiter.check_rate_limit(ip)

    try:
        tokens = cognito.authenticate_user(email=body.email, password=body.password)
    except Exception:
        await rate_limiter.record_failed_attempt(ip)
        logger.warning("Login failed", extra={"ip": ip, "email": body.email, "action": "login_failure"})
        raise

    claims = jose_jwt.get_unverified_claims(tokens["access_token"])
    cognito_sub = claims["sub"]

    statement = select(User).where(User.cognito_sub == cognito_sub)
    result = await session.exec(statement)
    user = result.first()

    if not user:
        user = User(
            cognito_sub=cognito_sub,
            email=body.email,
            is_verified=True,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)

    await rate_limiter.clear_attempts(ip)

    logger.info("Login successful", extra={"user_id": str(user.id), "ip": ip, "action": "login_success"})

    return LoginResponse(
        access_token=tokens["access_token"],
        refresh_token=tokens["refresh_token"],
        expires_in=tokens["expires_in"],
        user=UserInfo(
            id=str(user.id),
            email=user.email,
            locale=user.locale,
        ),
    )


@router.post("/refresh-token", response_model=RefreshTokenResponse)
async def refresh_token(
    body: RefreshTokenRequest,
    cognito: Annotated[CognitoService, Depends(get_cognito_service)],
) -> RefreshTokenResponse:
    tokens = cognito.refresh_tokens(refresh_token=body.refresh_token, email=body.email)
    return RefreshTokenResponse(
        access_token=tokens["access_token"],
        expires_in=tokens["expires_in"],
    )


@router.get("/me", response_model=UserProfileResponse)
async def get_me(
    current_user: Annotated[User, Depends(get_current_user)],
) -> UserProfileResponse:
    return UserProfileResponse(
        id=str(current_user.id),
        email=current_user.email,
        locale=current_user.locale,
        is_verified=current_user.is_verified,
        created_at=current_user.created_at.isoformat(),
    )


@router.patch("/me", response_model=UserProfileResponse)
async def update_me(
    body: UpdateProfileRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[SQLModelAsyncSession, Depends(get_db)],
) -> UserProfileResponse:
    current_user.locale = body.locale
    current_user.updated_at = datetime.now(UTC)
    session.add(current_user)
    await session.commit()
    await session.refresh(current_user)

    logger.info(
        "Profile updated",
        extra={"user_id": str(current_user.id), "locale": body.locale, "action": "profile_update"},
    )

    return UserProfileResponse(
        id=str(current_user.id),
        email=current_user.email,
        locale=current_user.locale,
        is_verified=current_user.is_verified,
        created_at=current_user.created_at.isoformat(),
    )


@router.post("/logout", response_model=MessageResponse)
async def logout(
    current_user: Annotated[User, Depends(get_current_user)],
    cognito: Annotated[CognitoService, Depends(get_cognito_service)],
) -> MessageResponse:
    cognito.global_sign_out(cognito_sub=current_user.cognito_sub)
    logger.info("Logout successful", extra={"user_id": str(current_user.id), "action": "logout"})
    return MessageResponse(message="Logged out successfully")


@router.post("/signup", response_model=SignupResponse, status_code=status.HTTP_201_CREATED)
async def signup(
    body: SignupRequest,
    session: Annotated[SQLModelAsyncSession, Depends(get_db)],
    cognito: Annotated[CognitoService, Depends(get_cognito_service)],
) -> SignupResponse:
    result = cognito.sign_up(email=body.email, password=body.password)

    user = User(
        cognito_sub=result["user_sub"],
        email=body.email,
        is_verified=False,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)

    return SignupResponse(message="Verification email sent", user_id=str(user.id))


@router.post("/verify", response_model=MessageResponse)
async def verify(
    body: VerifyRequest,
    session: Annotated[SQLModelAsyncSession, Depends(get_db)],
    cognito: Annotated[CognitoService, Depends(get_cognito_service)],
) -> MessageResponse:
    cognito.confirm_sign_up(email=body.email, code=body.code)

    statement = select(User).where(User.email == body.email)
    result = await session.exec(statement)
    user = result.first()
    if user:
        user.is_verified = True
        user.updated_at = datetime.now(UTC)
        session.add(user)
        await session.commit()

    return MessageResponse(message="Email verified")


@router.post("/resend-verification", response_model=MessageResponse)
async def resend_verification(
    body: ResendVerificationRequest,
    cognito: Annotated[CognitoService, Depends(get_cognito_service)],
) -> MessageResponse:
    cognito.resend_confirmation_code(email=body.email)
    return MessageResponse(message="Verification code sent")
