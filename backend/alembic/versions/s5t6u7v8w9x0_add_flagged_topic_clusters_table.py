"""add_flagged_topic_clusters_table

Revision ID: s5t6u7v8w9x0
Revises: r4s5t6u7v8w9
Create Date: 2026-04-17

Create the flagged_topic_clusters table for auto-flagged RAG topic clusters
(Story 7.8). A nightly Celery batch scans card_feedback votes, and when a
cluster (insight category) has >=10 votes with >30% thumbs-down rate, a
record is upserted here for developer review.
"""

from typing import Sequence, Union

import sqlalchemy as sa
import sqlmodel.sql.sqltypes
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "s5t6u7v8w9x0"
down_revision: Union[str, Sequence[str], None] = "r4s5t6u7v8w9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "flagged_topic_clusters",
        sa.Column(
            "id",
            sa.Uuid(),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "cluster_id",
            sqlmodel.sql.sqltypes.AutoString(length=100),
            nullable=False,
        ),
        sa.Column("thumbs_down_rate", sa.Float(), nullable=False),
        sa.Column("total_votes", sa.Integer(), nullable=False),
        sa.Column("total_down_votes", sa.Integer(), nullable=False),
        sa.Column("top_reason_chips", sa.JSON(), nullable=False),
        sa.Column("sample_card_ids", sa.JSON(), nullable=False),
        sa.Column(
            "flagged_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "last_evaluated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("cluster_id", name="uq_flagged_cluster_id"),
    )
    op.create_index(
        "ix_flagged_topic_clusters_cluster_id",
        "flagged_topic_clusters",
        ["cluster_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_flagged_topic_clusters_cluster_id",
        table_name="flagged_topic_clusters",
    )
    op.drop_table("flagged_topic_clusters")
