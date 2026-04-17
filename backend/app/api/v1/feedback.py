"""Feedback API routers (Story 7.1: implicit interactions, Story 7.2: explicit votes)."""
import uuid
from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession as SQLModelAsyncSession

from app.api.deps import get_current_user_id, get_db, get_rate_limiter
from app.models.insight import Insight
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


# ---------------------------------------------------------------------------
# Story 7.2 — Explicit card vote router
# ---------------------------------------------------------------------------

feedback_vote_router = APIRouter(prefix="/feedback", tags=["feedback"])


class CardVoteIn(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    vote: Literal["up", "down"]


class CardVoteOut(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    id: uuid.UUID
    card_id: uuid.UUID
    vote: str
    created_at: datetime


class CardFeedbackResponse(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    id: uuid.UUID
    vote: str | None
    reason_chip: str | None
    created_at: datetime


@feedback_vote_router.post(
    "/cards/{card_id}/vote",
    status_code=status.HTTP_201_CREATED,
    response_model=CardVoteOut,
)
async def submit_vote(
    card_id: uuid.UUID,
    body: CardVoteIn,
    user_id: Annotated[uuid.UUID, Depends(get_current_user_id)],
    session: Annotated[SQLModelAsyncSession, Depends(get_db)],
    rate_limiter: Annotated[RateLimiter, Depends(get_rate_limiter)],
) -> CardVoteOut:
    """Submit or update a thumbs-up/down vote on a Teaching Feed card."""
    await rate_limiter.check_feedback_rate_limit(str(user_id))

    insight = (
        await session.exec(select(Insight).where(Insight.id == card_id))
    ).one_or_none()
    if insight is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    record = await feedback_service.submit_card_vote(
        card_id=card_id,
        user_id=user_id,
        vote=body.vote,
        card_type=insight.category,
        session=session,
    )
    return CardVoteOut(
        id=record.id,
        card_id=record.card_id,
        vote=record.vote,
        created_at=record.created_at,
    )


class ReasonChipIn(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    reason_chip: Literal[
        "not_relevant", "already_knew", "seems_incorrect", "hard_to_understand",
        "learned_something", "actionable", "well_explained",
    ]


class ReasonChipOut(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    id: uuid.UUID
    reason_chip: str


@feedback_vote_router.patch("/{feedback_id}", response_model=ReasonChipOut)
async def update_reason_chip(
    feedback_id: uuid.UUID,
    body: ReasonChipIn,
    user_id: Annotated[uuid.UUID, Depends(get_current_user_id)],
    session: Annotated[SQLModelAsyncSession, Depends(get_db)],
    rate_limiter: Annotated[RateLimiter, Depends(get_rate_limiter)],
) -> ReasonChipOut:
    """Attach a reason chip to an existing feedback record (Story 7.5 Layer 2)."""
    await rate_limiter.check_feedback_rate_limit(str(user_id))
    record = await feedback_service.update_reason_chip(
        feedback_id=feedback_id,
        user_id=user_id,
        reason_chip=body.reason_chip,
        session=session,
    )
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return ReasonChipOut(id=record.id, reason_chip=record.reason_chip)


class IssueReportIn(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    issue_category: Literal["bug", "incorrect_info", "confusing", "other"]
    free_text: str | None = Field(default=None, max_length=500)


class IssueReportOut(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    id: uuid.UUID
    card_id: uuid.UUID
    issue_category: str


@feedback_vote_router.post(
    "/cards/{card_id}/report",
    status_code=status.HTTP_201_CREATED,
    response_model=IssueReportOut,
)
async def submit_report(
    card_id: uuid.UUID,
    body: IssueReportIn,
    user_id: Annotated[uuid.UUID, Depends(get_current_user_id)],
    session: Annotated[SQLModelAsyncSession, Depends(get_db)],
    rate_limiter: Annotated[RateLimiter, Depends(get_rate_limiter)],
) -> IssueReportOut:
    """Submit a one-time issue report for a Teaching Feed card."""
    await rate_limiter.check_feedback_rate_limit(str(user_id))

    insight = (
        await session.exec(select(Insight).where(Insight.id == card_id))
    ).one_or_none()
    if insight is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    record, created = await feedback_service.submit_issue_report(
        card_id=card_id,
        user_id=user_id,
        issue_category=body.issue_category,
        free_text=body.free_text,
        card_type=insight.category,
        session=session,
    )
    if not created:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="already_reported"
        )
    return IssueReportOut(
        id=record.id,
        card_id=record.card_id,
        issue_category=record.issue_category,
    )


@feedback_vote_router.get(
    "/cards/{card_id}",
    response_model=CardFeedbackResponse,
)
async def get_card_feedback(
    card_id: uuid.UUID,
    user_id: Annotated[uuid.UUID, Depends(get_current_user_id)],
    session: Annotated[SQLModelAsyncSession, Depends(get_db)],
) -> CardFeedbackResponse:
    """Get the current user's feedback for a specific card."""
    record = await feedback_service.get_card_feedback(
        card_id=card_id,
        user_id=user_id,
        session=session,
    )
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return CardFeedbackResponse(
        id=record.id,
        vote=record.vote,
        reason_chip=record.reason_chip,
        created_at=record.created_at,
    )
