import uuid
from datetime import UTC, datetime
from typing import Any, Optional

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class Insight(SQLModel, table=True):
    __tablename__ = "insights"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="users.id", index=True)
    upload_id: Optional[uuid.UUID] = Field(default=None, foreign_key="uploads.id")
    headline: str
    key_metric: str
    why_it_matters: str
    deep_dive: str
    severity: str = Field(default="info")  # critical, warning, info (pre-8.3 rows may contain high/medium/low — handled in insight_service.py)
    category: str
    card_type: str = Field(default="insight", max_length=50)
    # JSON here (not JSONB) for SQLite test compatibility. The Alembic migration
    # uses postgresql.JSONB for production, mirroring PatternFinding.finding_json.
    subscription_json: Optional[dict[str, Any]] = Field(
        default=None, sa_column=Column(JSON, nullable=True)
    )
    created_at: datetime = Field(default_factory=_utcnow)
