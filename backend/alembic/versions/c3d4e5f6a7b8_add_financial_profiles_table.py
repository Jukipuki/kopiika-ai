"""add_financial_profiles_table

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-04-08 00:00:01.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, Sequence[str], None] = "b2c3d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create financial_profiles table."""
    op.create_table(
        "financial_profiles",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("total_income", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_expenses", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("category_totals", JSONB(), nullable=True),
        sa.Column("period_start", sa.DateTime(), nullable=True),
        sa.Column("period_end", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.UniqueConstraint("user_id"),
    )
    op.create_index(
        "idx_financial_profiles_user_id", "financial_profiles", ["user_id"]
    )


def downgrade() -> None:
    """Drop financial_profiles table."""
    op.drop_index("idx_financial_profiles_user_id", table_name="financial_profiles")
    op.drop_table("financial_profiles")
