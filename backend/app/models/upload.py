import uuid
from datetime import UTC, datetime

from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class Upload(SQLModel, table=True):
    __tablename__ = "uploads"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="users.id", index=True)
    file_name: str = Field()
    s3_key: str = Field()
    file_size: int = Field()
    mime_type: str = Field()
    created_at: datetime = Field(default_factory=_utcnow)
