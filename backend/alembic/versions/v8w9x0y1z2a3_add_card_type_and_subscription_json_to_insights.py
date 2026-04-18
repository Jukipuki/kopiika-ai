"""add_card_type_and_subscription_json_to_insights

Revision ID: v8w9x0y1z2a3
Revises: u7v8w9x0y1z2
Create Date: 2026-04-18

Add card_type and subscription_json columns to the insights table so the
Teaching Feed can differentiate regular insight cards (card_type='insight')
from subscription alert cards (card_type='subscriptionAlert') introduced by
Story 8.2. Existing rows default to card_type='insight' and
subscription_json IS NULL, so no backfill is needed.
"""

from typing import Sequence, Union

import sqlalchemy as sa
import sqlmodel.sql.sqltypes
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "v8w9x0y1z2a3"
down_revision: Union[str, Sequence[str], None] = "u7v8w9x0y1z2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "insights",
        sa.Column(
            "card_type",
            sqlmodel.sql.sqltypes.AutoString(length=50),
            nullable=False,
            server_default=sa.text("'insight'"),
        ),
    )
    op.add_column(
        "insights",
        sa.Column(
            "subscription_json",
            postgresql.JSONB(),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("insights", "subscription_json")
    op.drop_column("insights", "card_type")
