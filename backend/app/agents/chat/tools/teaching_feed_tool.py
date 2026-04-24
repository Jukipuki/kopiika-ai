# Read-only — MUST NOT mutate. Any INSERT/UPDATE/DELETE introduction breaks the Epic 10 no-write-tools invariant.
"""``get_teaching_feed`` — insight titles delivered to the user's teaching feed.

Story 10.4c. Returns card_type, title (== ``insight.headline``), and delivery
date only. Card bodies (``why_it_matters``, ``deep_dive``, ``key_metric``)
are **never** returned — the chat surface is a summary/question layer for
the teaching feed, not a replacement viewer. If the user asks what card X
said, the model is expected to route them back to the teaching feed.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession as SQLModelAsyncSession

from app.models.feedback import CardFeedback
from app.models.insight import Insight


class GetTeachingFeedInput(BaseModel):
    limit: int = Field(default=20, ge=1, le=50)
    only_thumbs_up: bool = False


class TeachingFeedRow(BaseModel):
    insight_id: uuid.UUID
    card_type: str
    title: str
    delivered_at: date
    user_feedback: Optional[str] = None


class GetTeachingFeedOutput(BaseModel):
    rows: list[TeachingFeedRow]
    row_count: int
    truncated: bool


def _to_date(v: datetime | date) -> date:
    if isinstance(v, datetime):
        return v.date()
    return v


async def get_teaching_feed_handler(
    *,
    user_id: uuid.UUID,
    db: SQLModelAsyncSession,
    limit: int = 20,
    only_thumbs_up: bool = False,
) -> GetTeachingFeedOutput:
    # LEFT OUTER JOIN to the user's own card_feedback so we carry the
    # vote alongside the insight. ``card_vote`` is the authoritative
    # source for thumbs-up/down per Epic 7; other feedback_source rows
    # (issue reports, etc.) are ignored here.
    stmt = (
        select(Insight, CardFeedback)
        .join(
            CardFeedback,
            (CardFeedback.card_id == Insight.id)
            & (CardFeedback.user_id == Insight.user_id)
            & (CardFeedback.feedback_source == "card_vote"),
            isouter=True,
        )
        .where(Insight.user_id == user_id)
        .order_by(col(Insight.created_at).desc())
    )

    if only_thumbs_up:
        stmt = stmt.where(CardFeedback.vote == "up")

    stmt = stmt.limit(limit + 1)
    raw_rows = list((await db.exec(stmt)).all())
    truncated = len(raw_rows) > limit
    sliced = raw_rows[:limit]

    out: list[TeachingFeedRow] = []
    for row in sliced:
        # ``session.exec(select(A, B))`` yields rows as tuples; the outer
        # join may leave the CardFeedback side None.
        insight, feedback = row
        vote = feedback.vote if feedback is not None else None
        out.append(
            TeachingFeedRow(
                insight_id=insight.id,
                card_type=insight.card_type,
                title=insight.headline,
                delivered_at=_to_date(insight.created_at),
                user_feedback=vote,
            )
        )

    return GetTeachingFeedOutput(
        rows=out,
        row_count=len(out),
        truncated=truncated,
    )
