import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, Index
from sqlmodel import Column, Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class FinancialHealthScore(SQLModel, table=True):
    __tablename__ = "financial_health_scores"
    __table_args__ = (
        Index("idx_financial_health_scores_user_id", "user_id"),
        Index(
            "idx_financial_health_scores_user_id_calculated_at",
            "user_id",
            "calculated_at",
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="users.id")
    score: int = Field(ge=0, le=100)
    calculated_at: datetime = Field(default_factory=_utcnow)
    # JSON here (not JSONB) for SQLite test compatibility.
    # Alembic migration uses postgresql.JSONB for production.
    breakdown: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
