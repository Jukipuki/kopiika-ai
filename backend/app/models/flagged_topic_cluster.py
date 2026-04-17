import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, Column, UniqueConstraint
from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class FlaggedTopicCluster(SQLModel, table=True):
    __tablename__ = "flagged_topic_clusters"
    __table_args__ = (
        UniqueConstraint("cluster_id", name="uq_flagged_cluster_id"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    cluster_id: str = Field(max_length=100, index=True)
    thumbs_down_rate: float
    total_votes: int
    total_down_votes: int
    top_reason_chips: dict[str, Any] = Field(
        sa_column=Column(JSON, nullable=False), default_factory=dict
    )
    sample_card_ids: list[str] = Field(
        sa_column=Column(JSON, nullable=False), default_factory=list
    )
    flagged_at: datetime = Field(default_factory=_utcnow)
    last_evaluated_at: datetime = Field(default_factory=_utcnow)
