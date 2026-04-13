"""add_cascade_delete_user_fks

Revision ID: h4i5j6k7l8m9
Revises: a7b9c1d2e3f4
Create Date: 2026-04-12

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "h4i5j6k7l8m9"
down_revision: Union[str, Sequence[str], None] = "a7b9c1d2e3f4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Tables that need ON DELETE CASCADE on their user_id FK to users.id
# user_consents already has CASCADE — skip it.
FK_CHANGES = [
    # (table, constraint_name, column, referenced_table)
    ("uploads", "fk_uploads_user_id", "user_id", "users"),
    ("transactions", "fk_transactions_user_id", "user_id", "users"),
    ("processing_jobs", "fk_processing_jobs_user_id", "user_id", "users"),
    ("insights", "insights_user_id_fkey", "user_id", "users"),
    ("financial_profiles", "financial_profiles_user_id_fkey", "user_id", "users"),
    ("financial_health_scores", "financial_health_scores_user_id_fkey", "user_id", "users"),
    ("flagged_import_rows", "fk_flagged_import_rows_user_id", "user_id", "users"),
    # upload_id FKs — cascade through uploads deletion
    ("transactions", "fk_transactions_upload_id", "upload_id", "uploads"),
    ("processing_jobs", "fk_processing_jobs_upload_id", "upload_id", "uploads"),
    ("insights", "insights_upload_id_fkey", "upload_id", "uploads"),
    ("flagged_import_rows", "fk_flagged_import_rows_upload_id", "upload_id", "uploads"),
]


def upgrade() -> None:
    for table, constraint, column, ref_table in FK_CHANGES:
        op.drop_constraint(constraint, table, type_="foreignkey")
        op.create_foreign_key(
            constraint,
            table,
            ref_table,
            [column],
            ["id"],
            ondelete="CASCADE",
        )


def downgrade() -> None:
    for table, constraint, column, ref_table in FK_CHANGES:
        op.drop_constraint(constraint, table, type_="foreignkey")
        op.create_foreign_key(
            constraint,
            table,
            ref_table,
            [column],
            ["id"],
        )
