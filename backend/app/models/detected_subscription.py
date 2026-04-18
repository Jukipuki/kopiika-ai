import uuid
from datetime import UTC, date, datetime
from typing import Optional

from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class DetectedSubscription(SQLModel, table=True):
    __tablename__ = "detected_subscriptions"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="users.id", index=True)
    upload_id: uuid.UUID = Field(foreign_key="uploads.id", index=True)
    merchant_name: str = Field(max_length=200)
    estimated_monthly_cost_kopiykas: int
    billing_frequency: str = Field(max_length=20)
    last_charge_date: date
    is_active: bool = Field(default=True)
    months_with_no_activity: Optional[int] = Field(default=None)
    created_at: datetime = Field(default_factory=_utcnow)
