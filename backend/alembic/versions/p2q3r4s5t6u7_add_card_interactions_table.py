"""add_card_interactions_table

Revision ID: p2q3r4s5t6u7
Revises: o1p2q3r4s5t6
Create Date: 2026-04-16

Create the card_interactions table for implicit user engagement signal
tracking on Teaching Feed cards (Story 7.1). Stores per-card timing,
expansion depth, swipe direction, position, and a computed engagement
score 0–100 used as content-quality feedback.
"""

from typing import Sequence, Union

import sqlalchemy as sa
import sqlmodel.sql.sqltypes
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "p2q3r4s5t6u7"
down_revision: Union[str, Sequence[str], None] = "o1p2q3r4s5t6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "card_interactions",
        sa.Column(
            "id",
            sa.Uuid(),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("card_id", sa.Uuid(), nullable=False),
        sa.Column("time_on_card_ms", sa.Integer(), nullable=True),
        sa.Column("education_expanded", sa.Boolean(), nullable=True),
        sa.Column("education_depth_reached", sa.SmallInteger(), nullable=True),
        sa.Column(
            "swipe_direction",
            sqlmodel.sql.sqltypes.AutoString(length=10),
            nullable=True,
        ),
        sa.Column("card_position_in_feed", sa.SmallInteger(), nullable=True),
        sa.Column("engagement_score", sa.SmallInteger(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["card_id"], ["insights.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_card_interactions_user_id",
        "card_interactions",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "idx_card_interactions_card_id",
        "card_interactions",
        ["card_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_card_interactions_card_id", table_name="card_interactions")
    op.drop_index("idx_card_interactions_user_id", table_name="card_interactions")
    op.drop_table("card_interactions")
