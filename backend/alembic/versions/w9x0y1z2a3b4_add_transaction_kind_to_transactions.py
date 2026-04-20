"""add_transaction_kind_to_transactions

Revision ID: w9x0y1z2a3b4
Revises: v8w9x0y1z2a3
Create Date: 2026-04-20

Add `transaction_kind` to the transactions table as a first-class field per
Epic 11 / ADR-0001. Stores cash-flow semantics (spending, income, savings,
transfer) so downstream consumers (health score, savings ratio, spending
breakdowns, pattern detection) can filter without re-deriving from ad-hoc
rules. Greenfield project — no existing rows; the server default 'spending'
exists purely for schema validity.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "w9x0y1z2a3b4"
down_revision: Union[str, Sequence[str], None] = "v8w9x0y1z2a3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "transactions",
        sa.Column(
            "transaction_kind",
            sa.String(16),
            nullable=False,
            server_default=sa.text("'spending'"),
        ),
    )
    op.create_check_constraint(
        "ck_transactions_transaction_kind",
        "transactions",
        "transaction_kind IN ('spending','income','savings','transfer')",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_transactions_transaction_kind", "transactions", type_="check"
    )
    op.drop_column("transactions", "transaction_kind")
