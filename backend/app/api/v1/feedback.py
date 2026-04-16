"""POST /api/v1/cards/interactions — record implicit Teaching Feed engagement (Story 7.1)."""
import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel
from sqlmodel.ext.asyncio.session import AsyncSession as SQLModelAsyncSession

from app.api.deps import get_current_user_id, get_db, get_rate_limiter
from app.services import feedback_service
from app.services.rate_limiter import RateLimiter

router = APIRouter(prefix="/cards", tags=["feedback"])


class CardInteractionIn(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    card_id: uuid.UUID
    time_on_card_ms: int = Field(ge=0)
    education_expanded: bool
    education_depth_reached: int = Field(ge=0, le=2)
    swipe_direction: Literal["left", "right", "none"]
    card_position_in_feed: int = Field(ge=0)


class CardInteractionBatch(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    interactions: list[CardInteractionIn] = Field(min_length=1, max_length=20)


@router.post("/interactions", status_code=status.HTTP_204_NO_CONTENT)
async def record_card_interactions(
    batch: CardInteractionBatch,
    user_id: Annotated[uuid.UUID, Depends(get_current_user_id)],
    session: Annotated[SQLModelAsyncSession, Depends(get_db)],
    rate_limiter: Annotated[RateLimiter, Depends(get_rate_limiter)],
) -> None:
    """Persist a batch of implicit card-interaction signals with computed engagement scores."""
    await rate_limiter.check_feedback_rate_limit(str(user_id))
    await feedback_service.store_card_interactions(
        interactions=batch.interactions,
        user_id=user_id,
        session=session,
    )
