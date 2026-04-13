from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from sqlmodel.ext.asyncio.session import AsyncSession as SQLModelAsyncSession

from app.api.deps import get_cognito_service, get_current_user, get_db
from app.models.user import User
from app.services.account_deletion_service import (
    delete_all_user_data,
    get_user_s3_keys,
)
from app.services.cognito_service import CognitoService

router = APIRouter(prefix="/users/me", tags=["user-data"])


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def delete_account(
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[SQLModelAsyncSession, Depends(get_db)],
    cognito_service: Annotated[CognitoService, Depends(get_cognito_service)],
) -> Response:
    s3_keys = await get_user_s3_keys(session, user.id)
    await delete_all_user_data(
        session=session,
        user_id=user.id,
        cognito_sub=user.cognito_sub,
        s3_keys=s3_keys,
        cognito_service=cognito_service,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
