"""Feedback service: engagement score computation and batch persistence (Story 7.1),
explicit card vote/feedback (Story 7.2)."""
import uuid
from typing import Optional, Protocol, Sequence

from sqlalchemy.exc import IntegrityError
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession as SQLModelAsyncSession

from app.models.feedback import CardFeedback, CardInteraction

_TIME_WEIGHT = 0.30
_EDUCATION_EXPANDED_WEIGHT = 0.25
_EDUCATION_DEPTH_WEIGHT = 0.25
_SWIPE_WEIGHT = 0.10
_POSITION_WEIGHT = 0.10

_TIME_CAP_MS = 30_000
_MAX_EDUCATION_DEPTH = 2
_MAX_POSITION_SCORE_IDX = 10

_SWIPE_NORMALIZED = {"right": 1.0, "none": 0.5, "left": 0.0}


class CardInteractionInput(Protocol):
    """Shape the service needs; matches the Pydantic CardInteractionIn schema."""

    card_id: uuid.UUID
    time_on_card_ms: int
    education_expanded: bool
    education_depth_reached: int
    swipe_direction: str
    card_position_in_feed: int


def compute_engagement_score(
    time_on_card_ms: int,
    education_expanded: bool,
    education_depth_reached: int,
    swipe_direction: str,
    card_position_in_feed: int,
) -> int:
    """Compute a 0–100 engagement score from implicit card-interaction signals.

    Weighted sum of five normalized signals:
      - time_on_card_ms: capped at 30s, contributes up to 30 pts
      - education_expanded: boolean, 25 pts when True
      - education_depth_reached: 0–2, linearly scaled up to 25 pts
      - swipe_direction: right → 10, none → 5, left → 0
      - card_position_in_feed: position 0 = 10, decays by 1/position, floor 0
    """
    time_component = min(max(time_on_card_ms, 0) / _TIME_CAP_MS, 1.0) * 100 * _TIME_WEIGHT

    expanded_component = (100 * _EDUCATION_EXPANDED_WEIGHT) if education_expanded else 0.0

    depth_clamped = max(0, min(education_depth_reached, _MAX_EDUCATION_DEPTH))
    depth_component = (depth_clamped / _MAX_EDUCATION_DEPTH) * 100 * _EDUCATION_DEPTH_WEIGHT

    swipe_ratio = _SWIPE_NORMALIZED.get(swipe_direction, 0.5)
    swipe_component = swipe_ratio * 100 * _SWIPE_WEIGHT

    position_raw = max(_MAX_POSITION_SCORE_IDX - max(card_position_in_feed, 0), 0)
    position_component = (position_raw / _MAX_POSITION_SCORE_IDX) * 100 * _POSITION_WEIGHT

    total = (
        time_component
        + expanded_component
        + depth_component
        + swipe_component
        + position_component
    )
    return max(0, min(100, round(total)))


async def store_card_interactions(
    interactions: Sequence[CardInteractionInput],
    user_id: uuid.UUID,
    session: SQLModelAsyncSession,
) -> None:
    """Compute an engagement score per interaction and bulk-insert CardInteraction rows."""
    if not interactions:
        return

    records = [
        CardInteraction(
            user_id=user_id,
            card_id=item.card_id,
            time_on_card_ms=item.time_on_card_ms,
            education_expanded=item.education_expanded,
            education_depth_reached=item.education_depth_reached,
            swipe_direction=item.swipe_direction,
            card_position_in_feed=item.card_position_in_feed,
            engagement_score=compute_engagement_score(
                time_on_card_ms=item.time_on_card_ms,
                education_expanded=item.education_expanded,
                education_depth_reached=item.education_depth_reached,
                swipe_direction=item.swipe_direction,
                card_position_in_feed=item.card_position_in_feed,
            ),
        )
        for item in interactions
    ]
    session.add_all(records)
    await session.commit()


async def submit_card_vote(
    card_id: uuid.UUID,
    user_id: uuid.UUID,
    vote: str,
    card_type: str,
    session: SQLModelAsyncSession,
    feedback_source: str = "card_vote",
) -> CardFeedback:
    """Insert or update a card vote.

    Uses SELECT-then-INSERT/UPDATE. On concurrent first-vote races the INSERT
    raises IntegrityError; we roll back and re-load the winner's row, then
    update its vote — keeping the endpoint's response correct instead of 500.
    """
    existing_stmt = select(CardFeedback).where(
        CardFeedback.user_id == user_id,
        CardFeedback.card_id == card_id,
        CardFeedback.feedback_source == feedback_source,
    )

    existing = (await session.exec(existing_stmt)).one_or_none()

    if existing is not None:
        existing.vote = vote
        record = existing
        await session.flush()
    else:
        record = CardFeedback(
            user_id=user_id,
            card_id=card_id,
            card_type=card_type,
            vote=vote,
            feedback_source=feedback_source,
        )
        session.add(record)
        try:
            await session.flush()
        except IntegrityError:
            await session.rollback()
            winner = (await session.exec(existing_stmt)).one_or_none()
            if winner is None:
                raise
            winner.vote = vote
            record = winner
            await session.flush()

    snapshot = CardFeedback(
        id=record.id,
        user_id=record.user_id,
        card_id=record.card_id,
        card_type=record.card_type,
        vote=record.vote,
        reason_chip=record.reason_chip,
        free_text=record.free_text,
        feedback_source=record.feedback_source,
        issue_category=record.issue_category,
        created_at=record.created_at,
    )
    await session.commit()
    return snapshot


_MAX_FREE_TEXT_LEN = 500


async def submit_issue_report(
    card_id: uuid.UUID,
    user_id: uuid.UUID,
    issue_category: str,
    free_text: Optional[str],
    card_type: str,
    session: SQLModelAsyncSession,
) -> tuple[CardFeedback, bool]:
    """Insert a one-time issue report. Returns (snapshot, created).

    created=False means the user already reported this card — caller returns 409.
    Does NOT update an existing report (unlike vote upsert).
    """
    if free_text is not None and len(free_text) > _MAX_FREE_TEXT_LEN:
        raise ValueError(
            f"free_text exceeds {_MAX_FREE_TEXT_LEN} characters"
        )

    existing_stmt = select(CardFeedback).where(
        CardFeedback.user_id == user_id,
        CardFeedback.card_id == card_id,
        CardFeedback.feedback_source == "issue_report",
    )

    existing = (await session.exec(existing_stmt)).one_or_none()
    if existing is not None:
        snapshot = CardFeedback(
            id=existing.id,
            user_id=existing.user_id,
            card_id=existing.card_id,
            card_type=existing.card_type,
            vote=existing.vote,
            reason_chip=existing.reason_chip,
            free_text=existing.free_text,
            feedback_source=existing.feedback_source,
            issue_category=existing.issue_category,
            created_at=existing.created_at,
        )
        await session.commit()
        return snapshot, False

    record = CardFeedback(
        user_id=user_id,
        card_id=card_id,
        card_type=card_type,
        vote=None,
        issue_category=issue_category,
        free_text=free_text,
        feedback_source="issue_report",
    )
    session.add(record)
    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        winner = (await session.exec(existing_stmt)).one_or_none()
        if winner is None:
            raise
        snapshot = CardFeedback(
            id=winner.id,
            user_id=winner.user_id,
            card_id=winner.card_id,
            card_type=winner.card_type,
            vote=winner.vote,
            reason_chip=winner.reason_chip,
            free_text=winner.free_text,
            feedback_source=winner.feedback_source,
            issue_category=winner.issue_category,
            created_at=winner.created_at,
        )
        return snapshot, False

    snapshot = CardFeedback(
        id=record.id,
        user_id=record.user_id,
        card_id=record.card_id,
        card_type=record.card_type,
        vote=record.vote,
        reason_chip=record.reason_chip,
        free_text=record.free_text,
        feedback_source=record.feedback_source,
        issue_category=record.issue_category,
        created_at=record.created_at,
    )
    await session.commit()
    return snapshot, True


async def update_reason_chip(
    feedback_id: uuid.UUID,
    user_id: uuid.UUID,
    reason_chip: str,
    session: SQLModelAsyncSession,
) -> Optional[CardFeedback]:
    """Set reason_chip on an existing feedback row owned by user_id.

    Filters by both id and user_id to avoid leaking the existence of other
    users' feedback IDs. Returns None if no such row exists (caller → 404).
    """
    existing = (
        await session.exec(
            select(CardFeedback).where(
                CardFeedback.id == feedback_id,
                CardFeedback.user_id == user_id,
            )
        )
    ).one_or_none()
    if existing is None:
        return None
    existing.reason_chip = reason_chip
    await session.flush()
    snapshot = CardFeedback(
        id=existing.id,
        user_id=existing.user_id,
        card_id=existing.card_id,
        card_type=existing.card_type,
        vote=existing.vote,
        reason_chip=existing.reason_chip,
        free_text=existing.free_text,
        feedback_source=existing.feedback_source,
        issue_category=existing.issue_category,
        created_at=existing.created_at,
    )
    await session.commit()
    return snapshot


async def get_card_feedback(
    card_id: uuid.UUID,
    user_id: uuid.UUID,
    session: SQLModelAsyncSession,
    feedback_source: str = "card_vote",
) -> Optional[CardFeedback]:
    """Return the user's feedback for a specific card, or None if not found."""
    result = (
        await session.exec(
            select(CardFeedback).where(
                CardFeedback.user_id == user_id,
                CardFeedback.card_id == card_id,
                CardFeedback.feedback_source == feedback_source,
            )
        )
    ).one_or_none()
    if result is None:
        return None
    # Return a detached snapshot to avoid MissingGreenlet after session closes
    return CardFeedback(
        id=result.id,
        user_id=result.user_id,
        card_id=result.card_id,
        card_type=result.card_type,
        vote=result.vote,
        reason_chip=result.reason_chip,
        free_text=result.free_text,
        feedback_source=result.feedback_source,
        issue_category=result.issue_category,
        created_at=result.created_at,
    )
