"""Chat session — per-conversation anchor pinning the consent version.

Story 10.1b. Each chat session is owned by a user and carries the
``chat_processing`` consent version that authorized its creation (Consent
Drift Policy). Cascade-deleted when the user is deleted (account deletion)
or when ``chat_processing`` consent is revoked (see
``consent_service.revoke_chat_consent``). Messages cascade via
``chat_messages.session_id``.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Index, desc
from sqlmodel import Column, Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class ChatSession(SQLModel, table=True):
    __tablename__ = "chat_sessions"
    __table_args__ = (
        Index(
            "ix_chat_sessions_user_id_last_active_at",
            "user_id",
            desc("last_active_at"),
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(
        sa_column=Column(
            ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        )
    )
    created_at: datetime = Field(
        default_factory=_utcnow, sa_type=DateTime(timezone=True)
    )
    last_active_at: datetime = Field(
        default_factory=_utcnow, sa_type=DateTime(timezone=True)
    )
    consent_version_at_creation: str = Field(nullable=False)
