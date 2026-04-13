import uuid
from datetime import UTC, datetime
from typing import Any, Optional

from sqlmodel import JSON, Column, Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class Transaction(SQLModel, table=True):
    __tablename__ = "transactions"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="users.id", index=True)
    upload_id: uuid.UUID = Field(foreign_key="uploads.id", index=True)
    date: datetime
    description: str
    mcc: Optional[int] = Field(default=None)
    amount: int  # Integer kopiykas (e.g., -15050 = -150.50 UAH)
    balance: Optional[int] = Field(default=None)  # Integer kopiykas
    currency_code: int = Field(default=980)  # ISO 4217 numeric (980 = UAH)
    raw_data: Optional[dict[str, Any]] = Field(default=None, sa_column=Column(JSON))
    dedup_hash: str = Field(index=True)
    created_at: datetime = Field(default_factory=_utcnow)
    category: Optional[str] = Field(default=None, max_length=50)
    confidence_score: Optional[float] = Field(default=None)
    is_flagged_for_review: bool = Field(default=False)
    uncategorized_reason: Optional[str] = Field(default=None, max_length=50)
