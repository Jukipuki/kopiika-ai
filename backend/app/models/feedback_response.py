"""FeedbackResponse model (Story 7.7): milestone feedback card responses.

Each row represents a user's response to a milestone-triggered feedback card
in the Teaching Feed. The unique constraint on (user_id, feedback_card_type)
enforces the "never again" guarantee — a given card type is shown at most
once per user across their lifetime.
"""
import uuid
from datetime import UTC, datetime
from typing import Optional

from sqlalchemy import DateTime, Index, UniqueConstraint
from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(UTC)


class FeedbackResponse(SQLModel, table=True):
    __tablename__ = "feedback_responses"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "feedback_card_type",
            name="uq_feedback_response_user_type",
        ),
        Index("ix_feedback_response_user_id", "user_id"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(
        foreign_key="users.id",
        ondelete="CASCADE",
        nullable=False,
    )
    feedback_card_type: str = Field(max_length=50, nullable=False)
    response_value: str = Field(max_length=50, nullable=False)
    free_text: Optional[str] = Field(default=None, nullable=True)
    created_at: datetime = Field(
        default_factory=_utcnow, sa_type=DateTime(timezone=True)
    )
