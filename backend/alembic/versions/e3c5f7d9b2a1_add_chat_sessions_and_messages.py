"""add_chat_sessions_and_messages

Revision ID: e3c5f7d9b2a1
Revises: d8a0f2c4e6b9
Create Date: 2026-04-24 01:00:00.000000

Story 10.1b. Creates ``chat_sessions`` and ``chat_messages`` tables, both
ON DELETE CASCADE from their parents. The ``revoke_chat_consent`` service
deletes ``chat_sessions`` rows explicitly, relying on the
``chat_messages.session_id`` cascade to remove messages atomically.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "e3c5f7d9b2a1"
down_revision: Union[str, Sequence[str], None] = "d8a0f2c4e6b9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "chat_sessions",
        sa.Column(
            "id",
            sa.Uuid(),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "last_active_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("consent_version_at_creation", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_chat_sessions"),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_chat_sessions_user_id_users",
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "ix_chat_sessions_user_id_last_active_at",
        "chat_sessions",
        ["user_id", sa.text("last_active_at DESC")],
        unique=False,
    )

    op.create_table(
        "chat_messages",
        sa.Column(
            "id",
            sa.Uuid(),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "redaction_flags",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "guardrail_action",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'none'"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id", name="pk_chat_messages"),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["chat_sessions.id"],
            name="fk_chat_messages_session_id_chat_sessions",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "role IN ('user','assistant','system')",
            name="ck_chat_messages_role",
        ),
        sa.CheckConstraint(
            "guardrail_action IN ('none','blocked','modified')",
            name="ck_chat_messages_guardrail_action",
        ),
    )
    op.create_index(
        "ix_chat_messages_session_id_created_at",
        "chat_messages",
        ["session_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_chat_messages_guardrail_action_nonzero",
        "chat_messages",
        ["guardrail_action"],
        unique=False,
        postgresql_where=sa.text("guardrail_action != 'none'"),
    )


def downgrade() -> None:
    op.drop_index(
        "ix_chat_messages_guardrail_action_nonzero", table_name="chat_messages"
    )
    op.drop_index(
        "ix_chat_messages_session_id_created_at", table_name="chat_messages"
    )
    op.drop_table("chat_messages")
    op.drop_index(
        "ix_chat_sessions_user_id_last_active_at", table_name="chat_sessions"
    )
    op.drop_table("chat_sessions")
