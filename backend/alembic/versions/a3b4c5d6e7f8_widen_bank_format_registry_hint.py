"""widen_bank_format_registry_hint

Revision ID: a3b4c5d6e7f8
Revises: z2a3b4c5d6e7
Create Date: 2026-04-22

`bank_format_registry.detected_bank_hint` was originally sized at
VARCHAR(64), which is implausibly tight for a free-text LLM hint. Production
upload failed with `StringDataRightTruncation` on a 102-char hint. Widen to
VARCHAR(255) — the field is informational (display/audit only), not a key.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a3b4c5d6e7f8"
down_revision: Union[str, Sequence[str], None] = "z2a3b4c5d6e7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "bank_format_registry",
        "detected_bank_hint",
        existing_type=sa.String(length=64),
        type_=sa.String(length=255),
        existing_nullable=True,
    )


def downgrade() -> None:
    # Downgrade is lossy if any row stores a hint > 64 chars. Truncate in
    # place so the ALTER doesn't fail on existing data.
    op.execute(
        "UPDATE bank_format_registry "
        "SET detected_bank_hint = LEFT(detected_bank_hint, 64) "
        "WHERE detected_bank_hint IS NOT NULL AND LENGTH(detected_bank_hint) > 64"
    )
    op.alter_column(
        "bank_format_registry",
        "detected_bank_hint",
        existing_type=sa.String(length=255),
        type_=sa.String(length=64),
        existing_nullable=True,
    )
