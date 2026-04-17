"""add_index_card_interactions_created_at

Revision ID: 3f046f0dbf8a
Revises: s5t6u7v8w9x0
Create Date: 2026-04-17 20:02:13.136102

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '3f046f0dbf8a'
down_revision: Union[str, Sequence[str], None] = 's5t6u7v8w9x0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        'ix_card_interactions_created_at',
        'card_interactions',
        ['created_at'],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index('ix_card_interactions_created_at', table_name='card_interactions')
