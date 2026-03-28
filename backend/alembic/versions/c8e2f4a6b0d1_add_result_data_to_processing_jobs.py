"""add_result_data_to_processing_jobs

Revision ID: c8e2f4a6b0d1
Revises: b7d9e1f3a2c4
Create Date: 2026-03-28 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c8e2f4a6b0d1'
down_revision: Union[str, Sequence[str], None] = 'b7d9e1f3a2c4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add result_data JSON column to processing_jobs table."""
    op.add_column('processing_jobs', sa.Column('result_data', sa.JSON(), nullable=True))


def downgrade() -> None:
    """Remove result_data column from processing_jobs table."""
    op.drop_column('processing_jobs', 'result_data')
