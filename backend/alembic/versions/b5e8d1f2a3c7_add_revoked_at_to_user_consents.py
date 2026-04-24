"""add_revoked_at_to_user_consents

Revision ID: b5e8d1f2a3c7
Revises: e0f04e4194bc
Create Date: 2026-04-24 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b5e8d1f2a3c7"
down_revision: Union[str, Sequence[str], None] = "e0f04e4194bc"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add nullable revoked_at column for chat-consent revocation rows."""
    op.add_column(
        "user_consents",
        sa.Column("revoked_at", sa.DateTime(timezone=False), nullable=True),
    )


def downgrade() -> None:
    """Drop revoked_at column."""
    op.drop_column("user_consents", "revoked_at")
