"""add_langgraph_checkpoint_tables

Revision ID: i5j6k7l8m9n0
Revises: h4i5j6k7l8m9
Create Date: 2026-04-13

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "i5j6k7l8m9n0"
down_revision: Union[str, Sequence[str], None] = "h4i5j6k7l8m9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create LangGraph checkpoint tables via PostgresSaver.setup()."""
    from app.agents.checkpointer import _get_psycopg_conn_string

    from psycopg import Connection
    from langgraph.checkpoint.postgres import PostgresSaver

    conn_string = _get_psycopg_conn_string()
    with Connection.connect(conn_string) as conn:
        checkpointer = PostgresSaver(conn)
        checkpointer.setup()


def downgrade() -> None:
    """Drop LangGraph checkpoint tables."""
    op.execute("DROP TABLE IF EXISTS checkpoint_writes CASCADE")
    op.execute("DROP TABLE IF EXISTS checkpoint_blobs CASCADE")
    op.execute("DROP TABLE IF EXISTS checkpoints CASCADE")
    op.execute("DROP TABLE IF EXISTS checkpoint_migrations CASCADE")
