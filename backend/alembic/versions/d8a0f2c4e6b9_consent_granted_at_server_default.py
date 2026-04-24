"""add_server_default_now_to_user_consents_granted_at

Revision ID: d8a0f2c4e6b9
Revises: c7f9e3d4b1a8
Create Date: 2026-04-24 00:00:02.000000

Story 10.1a code-review fix M4: add a DB-side ``DEFAULT now()`` on
``user_consents.granted_at`` so any INSERT path that omits the column gets a
monotonic, DB-assigned timestamp rather than relying on the Python caller's
wall clock. Defense-in-depth — the app path still sets ``granted_at``
explicitly today, but a secondary sort by ``id`` (added in the same story
review) guarantees deterministic ordering regardless of timestamp ties.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d8a0f2c4e6b9"
down_revision: Union[str, Sequence[str], None] = "c7f9e3d4b1a8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "user_consents",
        "granted_at",
        existing_type=sa.DateTime(timezone=False),
        existing_nullable=True,
        server_default=sa.text("now()"),
    )


def downgrade() -> None:
    op.alter_column(
        "user_consents",
        "granted_at",
        existing_type=sa.DateTime(timezone=False),
        existing_nullable=True,
        server_default=None,
    )
