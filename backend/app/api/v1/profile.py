import uuid
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel
from sqlmodel.ext.asyncio.session import AsyncSession as SQLModelAsyncSession

from app.api.deps import get_current_user_id, get_db
from app.services.profile_service import (
    get_category_breakdown,
    get_monthly_comparison,
    get_profile_for_user,
)

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


class CategoryBreakdownItem(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    category: str
    amount: int
    percentage: float


class CategoryBreakdownResponse(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    categories: list[CategoryBreakdownItem]
    total_expenses: int


class CategoryComparisonResponse(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    category: str
    current_amount: int
    previous_amount: int
    change_percent: float
    change_amount: int


class MonthlyComparisonResponse(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    current_month: str
    previous_month: str
    categories: list[CategoryComparisonResponse]
    total_current: int
    total_previous: int
    total_change_percent: float


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


@router.get("/category-breakdown", response_model=CategoryBreakdownResponse | None)
async def get_category_breakdown_endpoint(
    user_id: Annotated[uuid.UUID, Depends(get_current_user_id)],
    session: Annotated[SQLModelAsyncSession, Depends(get_db)],
) -> CategoryBreakdownResponse | None:
    """Get spending breakdown by category for the authenticated user."""
    items = await get_category_breakdown(session=session, user_id=user_id)
    if items is None:
        return None
    total_expenses = sum(item["amount"] for item in items)
    return CategoryBreakdownResponse(
        categories=[CategoryBreakdownItem(**item) for item in items],
        total_expenses=total_expenses,
    )


@router.get("/monthly-comparison", response_model=MonthlyComparisonResponse | None)
async def get_monthly_comparison_endpoint(
    user_id: Annotated[uuid.UUID, Depends(get_current_user_id)],
    session: Annotated[SQLModelAsyncSession, Depends(get_db)],
) -> MonthlyComparisonResponse | None:
    """Get month-over-month spending comparison for the authenticated user."""
    result = await get_monthly_comparison(session=session, user_id=user_id)
    if result is None:
        return None
    return MonthlyComparisonResponse(
        current_month=result["current_month"],
        previous_month=result["previous_month"],
        categories=[CategoryComparisonResponse(**c) for c in result["categories"]],
        total_current=result["total_current"],
        total_previous=result["total_previous"],
        total_change_percent=result["total_change_percent"],
    )
