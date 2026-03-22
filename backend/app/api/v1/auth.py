from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from pydantic.alias_generators import to_camel
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession as SQLModelAsyncSession

from app.api.deps import get_cognito_service, get_db
from app.models.user import User
from app.services.cognito_service import CognitoService

router = APIRouter(prefix="/auth", tags=["auth"])


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
