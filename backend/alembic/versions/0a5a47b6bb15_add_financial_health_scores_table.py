"""add financial_health_scores table

Revision ID: 0a5a47b6bb15
Revises: c3d4e5f6a7b8
Create Date: 2026-04-09 13:29:35.090072

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0a5a47b6bb15'
down_revision: Union[str, Sequence[str], None] = 'c3d4e5f6a7b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('financial_health_scores',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('score', sa.Integer(), nullable=False),
    sa.Column('calculated_at', sa.DateTime(), nullable=False),
    sa.Column('breakdown', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_financial_health_scores_user_id', 'financial_health_scores', ['user_id'], unique=False)
    op.create_index('idx_financial_health_scores_user_id_calculated_at', 'financial_health_scores', ['user_id', 'calculated_at'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('idx_financial_health_scores_user_id_calculated_at', table_name='financial_health_scores')
    op.drop_index('idx_financial_health_scores_user_id', table_name='financial_health_scores')
    op.drop_table('financial_health_scores')
