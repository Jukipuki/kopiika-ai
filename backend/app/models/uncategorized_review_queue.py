"""Low-confidence categorization review queue (Story 11.8).

Rows inserted at persist time when the categorization pipeline flags a
transaction as `uncategorized_reason='low_confidence'` with an LLM
suggestion attached. Users resolve (apply a category) or dismiss entries
via the `/api/v1/transactions/review-queue` API.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Optional

from sqlalchemy import CheckConstraint, ForeignKey, Index
from sqlmodel import Column, Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class UncategorizedReviewQueue(SQLModel, table=True):
    __tablename__ = "uncategorized_review_queue"
    __table_args__ = (
        Index("ix_uncat_queue_user_status", "user_id", "status"),
        CheckConstraint(
            "status IN ('pending','resolved','dismissed')",
            name="ck_uncat_review_queue_status",
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(
        sa_column=Column(
            ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        )
    )
    transaction_id: uuid.UUID = Field(
        sa_column=Column(
            ForeignKey("transactions.id", ondelete="CASCADE"), nullable=False
        )
    )
    categorization_confidence: float
    suggested_category: Optional[str] = Field(default=None, max_length=32)
    suggested_kind: Optional[str] = Field(default=None, max_length=16)
    status: str = Field(default="pending", max_length=16)
    created_at: datetime = Field(default_factory=_utcnow)
    resolved_at: Optional[datetime] = Field(default=None)
    resolved_category: Optional[str] = Field(default=None, max_length=32)
    resolved_kind: Optional[str] = Field(default=None, max_length=16)
