import uuid
from datetime import UTC, datetime
from typing import Optional

from sqlalchemy import SmallInteger
from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(UTC)


class CardInteraction(SQLModel, table=True):
    __tablename__ = "card_interactions"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="users.id", nullable=False, index=True)
    card_id: uuid.UUID = Field(foreign_key="insights.id", nullable=False, index=True)
    time_on_card_ms: Optional[int] = Field(default=None)
    education_expanded: Optional[bool] = Field(default=None)
    education_depth_reached: Optional[int] = Field(
        default=None, sa_type=SmallInteger
    )
    swipe_direction: Optional[str] = Field(default=None, max_length=10)
    card_position_in_feed: Optional[int] = Field(
        default=None, sa_type=SmallInteger
    )
    engagement_score: Optional[int] = Field(default=None, sa_type=SmallInteger)
    created_at: datetime = Field(default_factory=_utcnow)
