"""Chat message — one row per turn in a chat session.

Story 10.1b. Cascade-deleted via ``chat_messages.session_id`` →
``chat_sessions.id``. ``role`` and ``guardrail_action`` are guarded by
named CHECK constraints rather than Postgres ENUMs (repo convention —
ALTER TYPE is painful under Alembic).
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any, Literal

from sqlalchemy import JSON, CheckConstraint, Column, DateTime, ForeignKey, Index, Text, text
from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class ChatMessage(SQLModel, table=True):
    __tablename__ = "chat_messages"
    __table_args__ = (
        CheckConstraint(
            "role IN ('user','assistant','system','tool')",
            name="ck_chat_messages_role",
        ),
        CheckConstraint(
            "guardrail_action IN ('none','blocked','modified')",
            name="ck_chat_messages_guardrail_action",
        ),
        Index(
            "ix_chat_messages_session_id_created_at",
            "session_id",
            "created_at",
        ),
        Index(
            "ix_chat_messages_guardrail_action_nonzero",
            "guardrail_action",
            postgresql_where=text("guardrail_action != 'none'"),
            sqlite_where=text("guardrail_action != 'none'"),
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    session_id: uuid.UUID = Field(
        sa_column=Column(
            ForeignKey("chat_sessions.id", ondelete="CASCADE"),
            nullable=False,
        )
    )
    role: Literal["user", "assistant", "system", "tool"] = Field(
        sa_column=Column(Text, nullable=False)
    )
    content: str = Field(sa_column=Column(Text, nullable=False))
    # JSON here (not JSONB) for SQLite test compatibility — the Alembic
    # migration uses postgresql.JSONB for production.
    redaction_flags: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False, server_default=text("'{}'")),
    )
    guardrail_action: Literal["none", "blocked", "modified"] = Field(
        default="none",
        sa_column=Column(Text, nullable=False, server_default=text("'none'")),
    )
    created_at: datetime = Field(
        default_factory=_utcnow, sa_type=DateTime(timezone=True)
    )
