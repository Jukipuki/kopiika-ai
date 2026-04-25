"""add_format_detection_fields

Revision ID: a1b2c3d4e5f6
Revises: 4c94b3ca32be
Create Date: 2026-03-28 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
# NOTE: Filename prefix (f3a8b2c1d4e5) differs from revision ID intentionally
# to avoid alphabetical sort collision in tests. See test_alembic_migration_file_exists_and_correct.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '4c94b3ca32be'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add detected_format and detected_encoding columns to uploads table."""
    op.add_column('uploads', sa.Column('detected_format', sa.String(length=50), nullable=True))
    op.add_column('uploads', sa.Column('detected_encoding', sa.String(length=50), nullable=True))


def downgrade() -> None:
    """Remove detected_format and detected_encoding columns from uploads table."""
    op.drop_column('uploads', 'detected_encoding')
    op.drop_column('uploads', 'detected_format')
