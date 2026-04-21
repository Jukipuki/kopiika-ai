"""add_user_iban_registry_and_transaction_counterparty

Revision ID: y1z2a3b4c5d6
Revises: x0y1z2a3b4c5
Create Date: 2026-04-21

Story 11.10 (TD-049). Two related schema changes in one migration because
they ship together:

1. `user_iban_registry` table — per-user known IBANs with application-level
   AES-GCM envelope encryption and a SHA-256 fingerprint for lookups.
2. `transactions` gains `counterparty_name`, `counterparty_tax_id`,
   `counterparty_account` columns so the categorization pipeline can consume
   signals populated by AIDetectedParser (PE-statement rows).
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "y1z2a3b4c5d6"
down_revision: Union[str, Sequence[str], None] = "x0y1z2a3b4c5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user_iban_registry",
        sa.Column(
            "id",
            sa.Uuid(),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("iban_encrypted", sa.LargeBinary(), nullable=False),
        sa.Column("iban_fingerprint", sa.CHAR(64), nullable=False),
        sa.Column("label", sa.String(length=64), nullable=True),
        sa.Column("first_seen_upload_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            ondelete="CASCADE",
            name="fk_user_iban_registry_user",
        ),
        sa.ForeignKeyConstraint(
            ["first_seen_upload_id"],
            ["uploads.id"],
            ondelete="SET NULL",
            name="fk_user_iban_registry_upload",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_user_iban_registry_user_fingerprint",
        "user_iban_registry",
        ["user_id", "iban_fingerprint"],
        unique=True,
    )

    # --- transactions: counterparty columns ---------------------------------
    op.add_column(
        "transactions",
        sa.Column("counterparty_name", sa.String(length=256), nullable=True),
    )
    op.add_column(
        "transactions",
        sa.Column("counterparty_tax_id", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "transactions",
        sa.Column("counterparty_account", sa.String(length=64), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("transactions", "counterparty_account")
    op.drop_column("transactions", "counterparty_tax_id")
    op.drop_column("transactions", "counterparty_name")
    op.drop_index(
        "ix_user_iban_registry_user_fingerprint", table_name="user_iban_registry"
    )
    op.drop_table("user_iban_registry")
