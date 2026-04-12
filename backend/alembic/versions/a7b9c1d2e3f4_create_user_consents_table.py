"""create_user_consents_table

Revision ID: a7b9c1d2e3f4
Revises: 0a5a47b6bb15
Create Date: 2026-04-11 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
import sqlmodel.sql.sqltypes
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a7b9c1d2e3f4"
down_revision: Union[str, Sequence[str], None] = "0a5a47b6bb15"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create append-only user_consents audit table."""
    op.create_table(
        "user_consents",
        sa.Column(
            "id",
            sa.Uuid(),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "consent_type",
            sqlmodel.sql.sqltypes.AutoString(),
            nullable=False,
            server_default="ai_processing",
        ),
        sa.Column("version", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column(
            "granted_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("locale", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("ip", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("user_agent", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_user_consents_user_id_users",
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        op.f("ix_user_consents_user_id"),
        "user_consents",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_user_consents_consent_type"),
        "user_consents",
        ["consent_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_user_consents_version"),
        "user_consents",
        ["version"],
        unique=False,
    )
    op.create_index(
        "ix_user_consents_user_id_consent_type_version",
        "user_consents",
        ["user_id", "consent_type", "version"],
        unique=False,
    )


def downgrade() -> None:
    """Drop user_consents table."""
    op.drop_index(
        "ix_user_consents_user_id_consent_type_version",
        table_name="user_consents",
    )
    op.drop_index(op.f("ix_user_consents_version"), table_name="user_consents")
    op.drop_index(op.f("ix_user_consents_consent_type"), table_name="user_consents")
    op.drop_index(op.f("ix_user_consents_user_id"), table_name="user_consents")
    op.drop_table("user_consents")
