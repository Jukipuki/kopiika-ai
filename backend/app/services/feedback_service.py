"""Feedback service: engagement score computation and batch persistence (Story 7.1)."""
import uuid
from typing import Protocol, Sequence

from sqlmodel.ext.asyncio.session import AsyncSession as SQLModelAsyncSession

from app.models.feedback import CardInteraction

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
