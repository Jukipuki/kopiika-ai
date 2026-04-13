"""add_retry_fields_to_processing_job

Revision ID: j6k7l8m9n0o1
Revises: i5j6k7l8m9n0
Create Date: 2026-04-13

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "j6k7l8m9n0o1"
down_revision: Union[str, Sequence[str], None] = "i5j6k7l8m9n0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("processing_jobs", sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("processing_jobs", sa.Column("max_retries", sa.Integer(), nullable=False, server_default="3"))
    op.add_column("processing_jobs", sa.Column("failed_step", sa.String(), nullable=True))
    op.add_column("processing_jobs", sa.Column("last_error_at", sa.DateTime(), nullable=True))
    op.add_column("processing_jobs", sa.Column("is_retryable", sa.Boolean(), nullable=False, server_default="true"))


def downgrade() -> None:
    op.drop_column("processing_jobs", "is_retryable")
    op.drop_column("processing_jobs", "last_error_at")
    op.drop_column("processing_jobs", "failed_step")
    op.drop_column("processing_jobs", "max_retries")
    op.drop_column("processing_jobs", "retry_count")
