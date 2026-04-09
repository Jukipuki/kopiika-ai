import uuid
from datetime import UTC, datetime
from typing import Any, Optional

from sqlalchemy import JSON
from sqlmodel import Column, Field, SQLModel, UniqueConstraint


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class FinancialProfile(SQLModel, table=True):
    __tablename__ = "financial_profiles"
    __table_args__ = (UniqueConstraint("user_id"),)

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="users.id", index=True)
    total_income: int = Field(default=0)  # Integer kopiykas
    total_expenses: int = Field(default=0)  # Integer kopiykas
    category_totals: dict[str, Any] = Field(
        default_factory=dict, sa_column=Column(JSON)
    )
    period_start: Optional[datetime] = Field(default=None)
    period_end: Optional[datetime] = Field(default=None)
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)
