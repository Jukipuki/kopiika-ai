"""add_detected_subscriptions_table

Revision ID: u7v8w9x0y1z2
Revises: t6u7v8w9x0y1
Create Date: 2026-04-18

Create the detected_subscriptions table for Story 8.2. The recurring detector
in pattern_detection/detectors/recurring.py emits one row per merchant that is
billed on a regular monthly or annual cadence with consistent amounts.
"""

from typing import Sequence, Union

import sqlalchemy as sa
import sqlmodel.sql.sqltypes
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "u7v8w9x0y1z2"
down_revision: Union[str, Sequence[str], None] = "t6u7v8w9x0y1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "detected_subscriptions",
        sa.Column(
            "id",
            sa.Uuid(),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("upload_id", sa.Uuid(), nullable=False),
        sa.Column(
            "merchant_name",
            sqlmodel.sql.sqltypes.AutoString(length=200),
            nullable=False,
        ),
        sa.Column("estimated_monthly_cost_kopiykas", sa.BigInteger(), nullable=False),
        sa.Column(
            "billing_frequency",
            sqlmodel.sql.sqltypes.AutoString(length=20),
            nullable=False,
        ),
        sa.Column("last_charge_date", sa.Date(), nullable=False),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column("months_with_no_activity", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["upload_id"], ["uploads.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "billing_frequency IN ('monthly', 'annual')",
            name="ck_detected_subscriptions_billing_frequency",
        ),
    )
    op.create_index(
        "ix_detected_subscriptions_user_id",
        "detected_subscriptions",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "ix_detected_subscriptions_upload_id",
        "detected_subscriptions",
        ["upload_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_detected_subscriptions_upload_id",
        table_name="detected_subscriptions",
    )
    op.drop_index(
        "ix_detected_subscriptions_user_id",
        table_name="detected_subscriptions",
    )
    op.drop_table("detected_subscriptions")
