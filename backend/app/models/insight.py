import uuid
from datetime import UTC, datetime
from typing import Optional

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
    severity: str = Field(default="medium")  # high, medium, low
    category: str
    created_at: datetime = Field(default_factory=_utcnow)
