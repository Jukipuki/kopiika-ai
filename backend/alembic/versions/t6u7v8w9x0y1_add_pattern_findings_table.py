"""add_pattern_findings_table

Revision ID: t6u7v8w9x0y1
Revises: s5t6u7v8w9x0
Create Date: 2026-04-17

Create the pattern_findings table for the Pattern Detection Agent (Story 8.1).
The agent computes trend, anomaly, and distribution findings over categorized
transactions and persists one row per finding; downstream Triage (Story 8.3)
will consume these rows.
"""

from typing import Sequence, Union

import sqlalchemy as sa
import sqlmodel.sql.sqltypes
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "t6u7v8w9x0y1"
down_revision: Union[str, Sequence[str], None] = "3f046f0dbf8a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "pattern_findings",
        sa.Column(
            "id",
            sa.Uuid(),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("upload_id", sa.Uuid(), nullable=False),
        sa.Column(
            "pattern_type",
            sqlmodel.sql.sqltypes.AutoString(length=20),
            nullable=False,
        ),
        sa.Column(
            "category",
            sqlmodel.sql.sqltypes.AutoString(length=50),
            nullable=True,
        ),
        sa.Column("period_start", sa.Date(), nullable=True),
        sa.Column("period_end", sa.Date(), nullable=True),
        sa.Column("baseline_amount_kopiykas", sa.BigInteger(), nullable=True),
        sa.Column("current_amount_kopiykas", sa.BigInteger(), nullable=True),
        sa.Column("change_percent", sa.Float(), nullable=True),
        sa.Column("finding_json", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["upload_id"], ["uploads.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "pattern_type IN ('trend', 'anomaly', 'distribution')",
            name="ck_pattern_findings_pattern_type",
        ),
    )
    op.create_index(
        "ix_pattern_findings_user_id",
        "pattern_findings",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "ix_pattern_findings_upload_id",
        "pattern_findings",
        ["upload_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_pattern_findings_upload_id", table_name="pattern_findings")
    op.drop_index("ix_pattern_findings_user_id", table_name="pattern_findings")
    op.drop_table("pattern_findings")
