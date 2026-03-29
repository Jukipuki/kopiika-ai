"""add_dedup_hash_to_transactions

Revision ID: e1a2b3c4d5f6
Revises: d9f3a5b7c1e2
Create Date: 2026-03-29 10:00:00.000000

"""

import hashlib
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "e1a2b3c4d5f6"
down_revision: Union[str, Sequence[str], None] = "d9f3a5b7c1e2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _compute_hash(user_id: str, date_str: str, amount: int, description: str) -> str:
    """Compute SHA-256 dedup hash matching the application logic."""
    normalized = f"{user_id}:{date_str}:{amount}:{description.strip().lower()}"
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def upgrade() -> None:
    """Add dedup_hash column, backfill existing rows, then add unique constraint."""
    # 1. Add nullable column first (for backfill)
    op.add_column(
        "transactions",
        sa.Column("dedup_hash", sa.String(64), nullable=True),
    )

    # 2. Backfill existing transactions in batches to avoid loading all rows into memory
    conn = op.get_bind()
    BATCH_SIZE = 1000
    offset = 0
    while True:
        rows = conn.execute(
            sa.text(
                "SELECT id, user_id, date, amount, description FROM transactions"
                " LIMIT :limit OFFSET :offset"
            ),
            {"limit": BATCH_SIZE, "offset": offset},
        ).fetchall()
        if not rows:
            break
        for row in rows:
            tx_id, user_id, date_val, amount, description = row
            date_str = str(date_val)[:10]  # YYYY-MM-DD
            dedup_hash = _compute_hash(str(user_id), date_str, amount, description or "")
            conn.execute(
                sa.text("UPDATE transactions SET dedup_hash = :hash WHERE id = :id"),
                {"hash": dedup_hash, "id": tx_id},
            )
        offset += BATCH_SIZE

    # 3. Make column NOT NULL after backfill
    op.alter_column("transactions", "dedup_hash", nullable=False)

    # 4. Add index for fast lookups
    op.create_index("ix_transactions_dedup_hash", "transactions", ["dedup_hash"])

    # 5. Add unique constraint on (user_id, dedup_hash)
    op.create_unique_constraint(
        "uq_transactions_user_dedup", "transactions", ["user_id", "dedup_hash"]
    )


def downgrade() -> None:
    """Remove dedup_hash column and related constraints."""
    op.drop_constraint("uq_transactions_user_dedup", "transactions", type_="unique")
    op.drop_index("ix_transactions_dedup_hash", table_name="transactions")
    op.drop_column("transactions", "dedup_hash")
