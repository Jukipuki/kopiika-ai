"""add_bank_format_registry

Revision ID: x0y1z2a3b4c5
Revises: w9x0y1z2a3b4
Create Date: 2026-04-21

Create the bank_format_registry table for Story 11.7 / ADR-0002. Caches the
column mapping detected by the AI-assisted schema-detection stage, keyed by a
SHA-256 fingerprint of the canonicalized header row. Hits avoid the LLM call;
operators can override a bad detection by writing `override_mapping`.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision: str = "x0y1z2a3b4c5"
down_revision: Union[str, Sequence[str], None] = "w9x0y1z2a3b4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "bank_format_registry",
        sa.Column(
            "id",
            sa.Uuid(),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("header_fingerprint", sa.CHAR(64), nullable=False),
        sa.Column("detected_mapping", JSONB(), nullable=False),
        sa.Column("override_mapping", JSONB(), nullable=True),
        sa.Column("detection_confidence", sa.REAL(), nullable=True),
        sa.Column("detected_bank_hint", sa.String(length=64), nullable=True),
        sa.Column("sample_header", sa.Text(), nullable=False),
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
        sa.Column(
            "last_used_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "use_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("1"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "header_fingerprint", name="uq_bank_format_registry_fingerprint"
        ),
    )
    op.create_index(
        "ix_bank_format_registry_fingerprint",
        "bank_format_registry",
        ["header_fingerprint"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_bank_format_registry_fingerprint", table_name="bank_format_registry"
    )
    op.drop_table("bank_format_registry")
