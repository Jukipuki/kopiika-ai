import uuid
from datetime import UTC, date, datetime
from typing import Any, Optional

from sqlmodel import JSON, Column, Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class PatternFinding(SQLModel, table=True):
    __tablename__ = "pattern_findings"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="users.id", index=True)
    upload_id: uuid.UUID = Field(foreign_key="uploads.id", index=True)
    pattern_type: str = Field(max_length=20)
    category: Optional[str] = Field(default=None, max_length=50)
    period_start: Optional[date] = Field(default=None)
    period_end: Optional[date] = Field(default=None)
    baseline_amount_kopiykas: Optional[int] = Field(default=None)
    current_amount_kopiykas: Optional[int] = Field(default=None)
    change_percent: Optional[float] = Field(default=None)
    # JSON here (not JSONB) for SQLite test compatibility.
    # Alembic migration uses postgresql.JSONB for production.
    finding_json: dict[str, Any] = Field(
        sa_column=Column(JSON, nullable=False), default_factory=dict
    )
    created_at: datetime = Field(default_factory=_utcnow)
