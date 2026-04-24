"""make_granted_at_nullable_for_revoke_rows

Revision ID: c7f9e3d4b1a8
Revises: b5e8d1f2a3c7
Create Date: 2026-04-24 00:00:01.000000

Story 10.1a code-review fix H1: revoke rows must carry ``granted_at = NULL``
so that ``granted_at`` vs ``revoked_at`` act as mutually-exclusive event-type
discriminators. Grant rows keep ``granted_at`` populated as before.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c7f9e3d4b1a8"
down_revision: Union[str, Sequence[str], None] = "b5e8d1f2a3c7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "user_consents",
        "granted_at",
        existing_type=sa.DateTime(timezone=False),
        nullable=True,
    )


def downgrade() -> None:
    # Backfill any revoke rows (granted_at IS NULL) from revoked_at before
    # restoring NOT NULL — required so the downgrade doesn't fail on existing
    # revoke rows produced under the new contract.
    op.execute(
        "UPDATE user_consents SET granted_at = revoked_at "
        "WHERE granted_at IS NULL AND revoked_at IS NOT NULL"
    )
    op.alter_column(
        "user_consents",
        "granted_at",
        existing_type=sa.DateTime(timezone=False),
        nullable=False,
    )
