"""add_uncategorized_reason_to_transactions

Revision ID: k7l8m9n0o1p2
Revises: j6k7l8m9n0o1
Create Date: 2026-04-13

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "k7l8m9n0o1p2"
down_revision: Union[str, Sequence[str], None] = "j6k7l8m9n0o1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "transactions",
        sa.Column("uncategorized_reason", sa.String(50), nullable=True),
    )
    op.create_check_constraint(
        "ck_transactions_uncategorized_reason",
        "transactions",
        sa.column("uncategorized_reason").in_(
            ["low_confidence", "parse_failure", "llm_unavailable"]
        )
        | sa.column("uncategorized_reason").is_(None),
    )
    op.create_index(
        "ix_transactions_user_flagged_date",
        "transactions",
        ["user_id", "is_flagged_for_review", "date"],
    )


def downgrade() -> None:
    op.drop_index("ix_transactions_user_flagged_date", table_name="transactions")
    op.drop_constraint("ck_transactions_uncategorized_reason", "transactions")
    op.drop_column("transactions", "uncategorized_reason")
