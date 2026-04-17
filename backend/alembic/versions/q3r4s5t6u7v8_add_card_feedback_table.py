"""add_card_feedback_table

Revision ID: q3r4s5t6u7v8
Revises: p2q3r4s5t6u7
Create Date: 2026-04-17

Create the card_feedback table for explicit user feedback (thumbs up/down)
on Teaching Feed cards (Story 7.2). Supports vote, reason chips, free text,
and issue categories for future feedback layers.
"""

from typing import Sequence, Union

import sqlalchemy as sa
import sqlmodel.sql.sqltypes
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "q3r4s5t6u7v8"
down_revision: Union[str, Sequence[str], None] = "p2q3r4s5t6u7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "card_feedback",
        sa.Column(
            "id",
            sa.Uuid(),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("card_id", sa.Uuid(), nullable=False),
        sa.Column(
            "card_type",
            sqlmodel.sql.sqltypes.AutoString(length=50),
            nullable=False,
        ),
        sa.Column(
            "vote",
            sqlmodel.sql.sqltypes.AutoString(length=10),
            nullable=True,
        ),
        sa.Column(
            "reason_chip",
            sqlmodel.sql.sqltypes.AutoString(length=50),
            nullable=True,
        ),
        sa.Column("free_text", sa.Text(), nullable=True),
        sa.Column(
            "feedback_source",
            sqlmodel.sql.sqltypes.AutoString(length=20),
            nullable=False,
            server_default="card_vote",
        ),
        sa.Column(
            "issue_category",
            sqlmodel.sql.sqltypes.AutoString(length=30),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "vote IN ('up', 'down')", name="ck_card_feedback_vote"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["card_id"], ["insights.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "card_id",
            "feedback_source",
            name="uq_card_feedback_user_card_source",
        ),
    )
    op.create_index(
        "idx_card_feedback_user_id",
        "card_feedback",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "idx_card_feedback_card_id",
        "card_feedback",
        ["card_id"],
        unique=False,
    )
    op.create_index(
        "idx_card_feedback_card_type_vote",
        "card_feedback",
        ["card_type", "vote"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "idx_card_feedback_card_type_vote", table_name="card_feedback"
    )
    op.drop_index("idx_card_feedback_card_id", table_name="card_feedback")
    op.drop_index("idx_card_feedback_user_id", table_name="card_feedback")
    op.drop_table("card_feedback")
