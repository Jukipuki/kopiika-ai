"""create_transactions_table

Revision ID: b7d9e1f3a2c4
Revises: a1b2c3d4e5f6
Create Date: 2026-03-28 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes


# revision identifiers, used by Alembic.
revision: str = 'b7d9e1f3a2c4'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create transactions and flagged_import_rows tables."""
    op.create_table(
        'transactions',
        sa.Column('id', sa.Uuid(), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('upload_id', sa.Uuid(), nullable=False),
        sa.Column('date', sa.DateTime(), nullable=False),
        sa.Column('description', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('mcc', sa.Integer(), nullable=True),
        sa.Column('amount', sa.Integer(), nullable=False),
        sa.Column('balance', sa.Integer(), nullable=True),
        sa.Column('currency_code', sa.Integer(), nullable=False, server_default=sa.text('980')),
        sa.Column('raw_data', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], name='fk_transactions_user_id'),
        sa.ForeignKeyConstraint(['upload_id'], ['uploads.id'], name='fk_transactions_upload_id'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('idx_transactions_user_id', 'transactions', ['user_id'])
    op.create_index('idx_transactions_upload_id', 'transactions', ['upload_id'])
    op.create_index('idx_transactions_date', 'transactions', ['date'])

    op.create_table(
        'flagged_import_rows',
        sa.Column('id', sa.Uuid(), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('upload_id', sa.Uuid(), nullable=False),
        sa.Column('row_number', sa.Integer(), nullable=False),
        sa.Column('raw_data', sa.JSON(), nullable=True),
        sa.Column('reason', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], name='fk_flagged_import_rows_user_id'),
        sa.ForeignKeyConstraint(['upload_id'], ['uploads.id'], name='fk_flagged_import_rows_upload_id'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('idx_flagged_import_rows_user_id', 'flagged_import_rows', ['user_id'])
    op.create_index('idx_flagged_import_rows_upload_id', 'flagged_import_rows', ['upload_id'])


def downgrade() -> None:
    """Drop transactions and flagged_import_rows tables."""
    op.drop_index('idx_flagged_import_rows_upload_id', table_name='flagged_import_rows')
    op.drop_index('idx_flagged_import_rows_user_id', table_name='flagged_import_rows')
    op.drop_table('flagged_import_rows')
    op.drop_index('idx_transactions_date', table_name='transactions')
    op.drop_index('idx_transactions_upload_id', table_name='transactions')
    op.drop_index('idx_transactions_user_id', table_name='transactions')
    op.drop_table('transactions')
