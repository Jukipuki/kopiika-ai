"""add_currency_unknown_to_uncategorized_reason

Revision ID: n0o1p2q3r4s5
Revises: m9n0o1p2q3r4
Create Date: 2026-04-16

Widens the ck_transactions_uncategorized_reason CHECK constraint to accept
"currency_unknown" alongside the existing reasons. No data backfill —
existing rows are not modified (AC #5).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "n0o1p2q3r4s5"
down_revision: Union[str, Sequence[str], None] = "m9n0o1p2q3r4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint("ck_transactions_uncategorized_reason", "transactions", type_="check")
    op.create_check_constraint(
        "ck_transactions_uncategorized_reason",
        "transactions",
        sa.column("uncategorized_reason").in_(
            ["low_confidence", "parse_failure", "llm_unavailable", "currency_unknown"]
        )
        | sa.column("uncategorized_reason").is_(None),
    )


def downgrade() -> None:
    op.drop_constraint("ck_transactions_uncategorized_reason", "transactions", type_="check")
    op.create_check_constraint(
        "ck_transactions_uncategorized_reason",
        "transactions",
        sa.column("uncategorized_reason").in_(
            ["low_confidence", "parse_failure", "llm_unavailable"]
        )
        | sa.column("uncategorized_reason").is_(None),
    )
