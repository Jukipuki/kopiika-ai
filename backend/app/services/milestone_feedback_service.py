"""Milestone feedback service (Story 7.7): Teaching-Feed end-of-feed cards.

Two triggers are implemented:

- ``milestone_3rd_upload``: user has completed 3+ uploads (one-time).
- ``health_score_change``: most recent two FinancialHealthScore rows differ by
  >= 5 points.

Frequency is capped at one card per 30 days and the ``feedback_responses``
table's ``(user_id, feedback_card_type)`` unique constraint guarantees a given
card type never re-appears after any response (including dismissal).
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Optional

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession as SQLModelAsyncSession

from app.models.feedback_response import FeedbackResponse
from app.models.financial_health_score import FinancialHealthScore
from app.models.processing_job import ProcessingJob


THIRD_UPLOAD_CARD_TYPE = "milestone_3rd_upload"
HEALTH_SCORE_CARD_TYPE = "health_score_change"

_UPLOAD_THRESHOLD = 3
_HEALTH_SCORE_DELTA_THRESHOLD = 5
_MONTHLY_CAP_DAYS = 30


async def get_pending_milestone_cards(
    user_id: uuid.UUID, db: SQLModelAsyncSession
) -> list[dict]:
    """Return at most one pending milestone card for the user.

    Enforces (in order):
      1. Monthly frequency cap — any response within the last 30 days
         suppresses all milestone cards.
      2. Per-card-type "never again" via response history.
      3. 3rd-upload trigger (priority) vs. health-score-change trigger.
    """
    # Load all responses once — needed for frequency cap AND type suppression.
    responses = (
        await db.exec(
            select(
                FeedbackResponse.feedback_card_type,
                FeedbackResponse.created_at,
            ).where(FeedbackResponse.user_id == user_id)
        )
    ).all()

    responded_types = {row[0] for row in responses}
    cap_cutoff = datetime.now(UTC) - timedelta(days=_MONTHLY_CAP_DAYS)
    # Compare timezone-aware to timezone-aware; treat naive timestamps as UTC
    # to support SQLite test backend (stores naive) and Postgres (stores aware).
    for _card_type, created_at in responses:
        created_aware = (
            created_at if created_at.tzinfo else created_at.replace(tzinfo=UTC)
        )
        if created_aware >= cap_cutoff:
            return []

    # 3rd-upload trigger has priority.
    if THIRD_UPLOAD_CARD_TYPE not in responded_types:
        completed_uploads = await db.scalar(
            select(func.count()).select_from(ProcessingJob).where(
                ProcessingJob.user_id == user_id,
                ProcessingJob.status == "completed",
            )
        )
        if (completed_uploads or 0) >= _UPLOAD_THRESHOLD:
            return [{"card_type": THIRD_UPLOAD_CARD_TYPE, "variant": "emoji_rating"}]

    # Health-score-change trigger.
    if HEALTH_SCORE_CARD_TYPE not in responded_types:
        score_rows = (
            await db.exec(
                select(FinancialHealthScore.score)
                .where(FinancialHealthScore.user_id == user_id)
                .order_by(FinancialHealthScore.calculated_at.desc())
                .limit(2)
            )
        ).all()

        if (
            len(score_rows) >= 2
            and abs(score_rows[0] - score_rows[1]) >= _HEALTH_SCORE_DELTA_THRESHOLD
        ):
            return [{"card_type": HEALTH_SCORE_CARD_TYPE, "variant": "yes_no"}]

    return []


async def save_milestone_response(
    user_id: uuid.UUID,
    card_type: str,
    response_value: str,
    free_text: Optional[str],
    db: SQLModelAsyncSession,
) -> None:
    """Insert the response row. Idempotent under the unique constraint — on
    duplicate, the existing row is preserved (the new values are dropped)."""
    record = FeedbackResponse(
        user_id=user_id,
        feedback_card_type=card_type,
        response_value=response_value,
        free_text=free_text,
    )
    db.add(record)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
