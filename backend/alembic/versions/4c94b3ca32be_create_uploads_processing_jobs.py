"""create_uploads_processing_jobs

Revision ID: 4c94b3ca32be
Revises: feb18f356210
Create Date: 2026-03-27 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes


# revision identifiers, used by Alembic.
revision: str = '4c94b3ca32be'
down_revision: Union[str, Sequence[str], None] = 'feb18f356210'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create uploads table
    op.create_table(
        'uploads',
        sa.Column('id', sa.Uuid(), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('file_name', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('s3_key', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('file_size', sa.Integer(), nullable=False),
        sa.Column('mime_type', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], name='fk_uploads_user_id'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('idx_uploads_user_id', 'uploads', ['user_id'])

    # Create processing_jobs table
    op.create_table(
        'processing_jobs',
        sa.Column('id', sa.Uuid(), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('upload_id', sa.Uuid(), nullable=False),
        sa.Column('status', sqlmodel.sql.sqltypes.AutoString(), nullable=False, server_default='pending'),
        sa.Column('step', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('progress', sa.Integer(), nullable=False, server_default=sa.text('0')),
        sa.Column('error_code', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('error_message', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], name='fk_processing_jobs_user_id'),
        sa.ForeignKeyConstraint(['upload_id'], ['uploads.id'], name='fk_processing_jobs_upload_id'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('idx_processing_jobs_user_id', 'processing_jobs', ['user_id'])
    op.create_index('idx_processing_jobs_status', 'processing_jobs', ['status'])
    op.create_index('idx_processing_jobs_upload_id', 'processing_jobs', ['upload_id'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('idx_processing_jobs_upload_id', table_name='processing_jobs')
    op.drop_index('idx_processing_jobs_status', table_name='processing_jobs')
    op.drop_index('idx_processing_jobs_user_id', table_name='processing_jobs')
    op.drop_table('processing_jobs')
    op.drop_index('idx_uploads_user_id', table_name='uploads')
    op.drop_table('uploads')
