import uuid
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel
from sqlmodel.ext.asyncio.session import AsyncSession as SQLModelAsyncSession

from app.api.deps import get_current_user_id, get_db
from app.services.profile_service import get_profile_for_user

router = APIRouter(prefix="/profile", tags=["profile"])


class ProfileResponse(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    id: str
    total_income: int
    total_expenses: int
    category_totals: dict[str, int]
    period_start: Optional[str] = None
    period_end: Optional[str] = None
    updated_at: str


@router.get("", response_model=ProfileResponse)
async def get_profile(
    user_id: Annotated[uuid.UUID, Depends(get_current_user_id)],
    session: Annotated[SQLModelAsyncSession, Depends(get_db)],
) -> ProfileResponse:
    """Get the financial profile for the authenticated user."""
    profile = await get_profile_for_user(session=session, user_id=user_id)

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "PROFILE_NOT_FOUND", "message": "No financial profile found. Upload a statement first."}},
        )

    return ProfileResponse(
        id=str(profile.id),
        total_income=profile.total_income,
        total_expenses=profile.total_expenses,
        category_totals=profile.category_totals or {},
        period_start=profile.period_start.isoformat() if profile.period_start else None,
        period_end=profile.period_end.isoformat() if profile.period_end else None,
        updated_at=profile.updated_at.isoformat() + "Z",
    )
