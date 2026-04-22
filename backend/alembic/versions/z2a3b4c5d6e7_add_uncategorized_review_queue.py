"""add_uncategorized_review_queue

Revision ID: z2a3b4c5d6e7
Revises: y1z2a3b4c5d6
Create Date: 2026-04-21

Story 11.8. Introduces the `uncategorized_review_queue` table that surfaces
low-confidence LLM categorizations (confidence < 0.6) to users for manual
resolution, alongside the three-tier threshold routing in the categorization
pipeline. Schema per tech spec §2.5.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "z2a3b4c5d6e7"
down_revision: Union[str, Sequence[str], None] = "y1z2a3b4c5d6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "uncategorized_review_queue",
        sa.Column(
            "id",
            sa.Uuid(),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("transaction_id", sa.Uuid(), nullable=False),
        sa.Column("categorization_confidence", sa.REAL(), nullable=False),
        sa.Column("suggested_category", sa.String(length=32), nullable=True),
        sa.Column("suggested_kind", sa.String(length=16), nullable=True),
        sa.Column(
            "status",
            sa.String(length=16),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_category", sa.String(length=32), nullable=True),
        sa.Column("resolved_kind", sa.String(length=16), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            ondelete="CASCADE",
            name="fk_uncat_review_queue_user",
        ),
        sa.ForeignKeyConstraint(
            ["transaction_id"],
            ["transactions.id"],
            ondelete="CASCADE",
            name="fk_uncat_review_queue_transaction",
        ),
        sa.CheckConstraint(
            "status IN ('pending','resolved','dismissed')",
            name="ck_uncat_review_queue_status",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_uncat_queue_user_status",
        "uncategorized_review_queue",
        ["user_id", "status"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_uncat_queue_user_status", table_name="uncategorized_review_queue"
    )
    op.drop_table("uncategorized_review_queue")
