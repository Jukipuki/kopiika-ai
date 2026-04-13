import uuid
from datetime import UTC, datetime
from typing import Optional

import sqlalchemy as sa
from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class ProcessingJob(SQLModel, table=True):
    __tablename__ = "processing_jobs"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="users.id", index=True)
    upload_id: uuid.UUID = Field(foreign_key="uploads.id")
    status: str = Field(default="pending")
    step: Optional[str] = Field(default=None)
    progress: int = Field(default=0)
    error_code: Optional[str] = Field(default=None)
    error_message: Optional[str] = Field(default=None)
    result_data: Optional[dict] = Field(default=None, sa_type=sa.JSON)
    retry_count: int = Field(default=0)
    max_retries: int = Field(default=3)
    failed_step: Optional[str] = Field(default=None)
    last_error_at: Optional[datetime] = Field(default=None)
    is_retryable: bool = Field(default=True)
    started_at: Optional[datetime] = Field(default=None)
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)
