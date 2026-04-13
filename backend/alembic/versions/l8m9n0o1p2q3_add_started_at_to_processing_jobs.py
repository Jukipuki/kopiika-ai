"""add_started_at_to_processing_jobs

Revision ID: l8m9n0o1p2q3
Revises: k7l8m9n0o1p2
Create Date: 2026-04-13

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "l8m9n0o1p2q3"
down_revision: Union[str, Sequence[str], None] = "k7l8m9n0o1p2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "processing_jobs",
        sa.Column("started_at", sa.DateTime(), nullable=True),
    )
    op.create_index(
        "ix_processing_jobs_status_started_at",
        "processing_jobs",
        ["status", "started_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_processing_jobs_status_started_at", table_name="processing_jobs")
    op.drop_column("processing_jobs", "started_at")
