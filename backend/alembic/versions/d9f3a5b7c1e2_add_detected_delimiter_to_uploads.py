"""add_detected_delimiter_to_uploads

Revision ID: d9f3a5b7c1e2
Revises: c8e2f4a6b0d1
Create Date: 2026-03-28 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd9f3a5b7c1e2'
down_revision: Union[str, Sequence[str], None] = 'c8e2f4a6b0d1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add detected_delimiter column to uploads table."""
    op.add_column('uploads', sa.Column('detected_delimiter', sa.String(), nullable=True))


def downgrade() -> None:
    """Remove detected_delimiter column from uploads table."""
    op.drop_column('uploads', 'detected_delimiter')
