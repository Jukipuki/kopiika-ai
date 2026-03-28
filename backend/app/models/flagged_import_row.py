import uuid
from datetime import UTC, datetime
from typing import Any, Optional

from sqlmodel import JSON, Column, Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class FlaggedImportRow(SQLModel, table=True):
    __tablename__ = "flagged_import_rows"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="users.id", index=True)
    upload_id: uuid.UUID = Field(foreign_key="uploads.id", index=True)
    row_number: int
    raw_data: Optional[dict[str, Any]] = Field(default=None, sa_column=Column(JSON))
    reason: str
    created_at: datetime = Field(default_factory=_utcnow)
