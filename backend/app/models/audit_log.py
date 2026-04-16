import uuid
from datetime import UTC, datetime
from typing import Optional

from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class AuditLog(SQLModel, table=True):
    __tablename__ = "audit_logs"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: str = Field(max_length=64, index=True)  # cognito_sub or sha256 hash post-anonymization
    timestamp: datetime = Field(default_factory=_utcnow, index=True)
    action_type: str = Field(max_length=10)  # 'read', 'write', 'delete'
    resource_type: str = Field(max_length=50, index=True)  # 'transactions', 'insights', etc.
    resource_id: Optional[str] = Field(default=None, max_length=255)  # UUID path param if present
    ip_address: Optional[str] = Field(default=None, max_length=45)  # IPv4 or IPv6
    user_agent: Optional[str] = Field(default=None, max_length=500)  # UA string, capped to avoid bloat
