"""add_categorization_fields_to_transactions

Revision ID: f2a4b6c8d0e1
Revises: e1a2b3c4d5f6
Create Date: 2026-03-30 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f2a4b6c8d0e1"
down_revision: Union[str, Sequence[str], None] = "e1a2b3c4d5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add categorization columns to transactions table."""
    op.add_column(
        "transactions",
        sa.Column("category", sa.String(50), nullable=True),
    )
    op.add_column(
        "transactions",
        sa.Column("confidence_score", sa.Float(), nullable=True),
    )
    op.add_column(
        "transactions",
        sa.Column("is_flagged_for_review", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.create_index(
        "ix_transactions_category",
        "transactions",
        ["user_id", "category"],
    )


def downgrade() -> None:
    """Remove categorization columns from transactions table."""
    op.drop_index("ix_transactions_category", table_name="transactions")
    op.drop_column("transactions", "is_flagged_for_review")
    op.drop_column("transactions", "confidence_score")
    op.drop_column("transactions", "category")
