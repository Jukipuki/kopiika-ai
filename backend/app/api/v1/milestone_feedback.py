"""Milestone feedback API (Story 7.7): end-of-feed milestone cards."""
import uuid
from typing import Annotated, Literal, Optional

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel
from sqlmodel.ext.asyncio.session import AsyncSession as SQLModelAsyncSession

from app.api.deps import get_current_user_id, get_db, get_rate_limiter
from app.services import milestone_feedback_service
from app.services.rate_limiter import RateLimiter

router = APIRouter(prefix="/milestone-feedback", tags=["milestone-feedback"])


MilestoneCardType = Literal["milestone_3rd_upload", "health_score_change"]
MilestoneVariant = Literal["emoji_rating", "yes_no"]


class MilestoneFeedbackCardOut(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    card_type: MilestoneCardType
    variant: MilestoneVariant


class PendingMilestoneCardsOut(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    cards: list[MilestoneFeedbackCardOut]


class MilestoneResponseIn(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    card_type: MilestoneCardType
    response_value: str = Field(min_length=1, max_length=50)
    free_text: Optional[str] = Field(default=None, max_length=500)


class MilestoneResponseOut(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    ok: bool


@router.get("/pending", response_model=PendingMilestoneCardsOut)
async def get_pending_cards(
    user_id: Annotated[uuid.UUID, Depends(get_current_user_id)],
    session: Annotated[SQLModelAsyncSession, Depends(get_db)],
) -> PendingMilestoneCardsOut:
    """Return the pending milestone card for the user (at most one)."""
    cards = await milestone_feedback_service.get_pending_milestone_cards(
        user_id=user_id, db=session
    )
    return PendingMilestoneCardsOut(
        cards=[MilestoneFeedbackCardOut(**c) for c in cards]
    )


@router.post(
    "/respond",
    response_model=MilestoneResponseOut,
    status_code=status.HTTP_200_OK,
)
async def respond(
    body: MilestoneResponseIn,
    user_id: Annotated[uuid.UUID, Depends(get_current_user_id)],
    session: Annotated[SQLModelAsyncSession, Depends(get_db)],
    rate_limiter: Annotated[RateLimiter, Depends(get_rate_limiter)],
) -> MilestoneResponseOut:
    """Record the user's response (or dismissal) to a milestone card."""
    await rate_limiter.check_feedback_rate_limit(str(user_id))
    await milestone_feedback_service.save_milestone_response(
        user_id=user_id,
        card_type=body.card_type,
        response_value=body.response_value,
        free_text=body.free_text,
        db=session,
    )
    return MilestoneResponseOut(ok=True)
