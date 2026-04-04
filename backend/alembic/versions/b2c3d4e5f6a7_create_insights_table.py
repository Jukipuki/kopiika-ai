"""create_insights_table

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-04-04 00:00:01.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, Sequence[str], None] = "g3h4i5j6k7l8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create insights table."""
    op.create_table(
        "insights",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("upload_id", sa.Uuid(), nullable=True),
        sa.Column("headline", sa.String(), nullable=False),
        sa.Column("key_metric", sa.String(), nullable=False),
        sa.Column("why_it_matters", sa.Text(), nullable=False),
        sa.Column("deep_dive", sa.Text(), nullable=False),
        sa.Column("severity", sa.String(10), nullable=False, server_default="medium"),
        sa.Column("category", sa.String(50), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["upload_id"], ["uploads.id"]),
    )
    op.create_index("ix_insights_user_id", "insights", ["user_id"])


def downgrade() -> None:
    """Drop insights table."""
    op.drop_index("ix_insights_user_id", table_name="insights")
    op.drop_table("insights")
