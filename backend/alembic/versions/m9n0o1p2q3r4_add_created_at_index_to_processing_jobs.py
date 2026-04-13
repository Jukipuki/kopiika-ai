"""add_created_at_index_to_processing_jobs

Revision ID: m9n0o1p2q3r4
Revises: l8m9n0o1p2q3
Create Date: 2026-04-13

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "m9n0o1p2q3r4"
down_revision: Union[str, Sequence[str], None] = "l8m9n0o1p2q3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "ix_processing_jobs_created_at",
        "processing_jobs",
        ["created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_processing_jobs_created_at", table_name="processing_jobs")
