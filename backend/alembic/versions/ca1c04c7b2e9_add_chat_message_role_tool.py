"""add_chat_message_role_tool

Revision ID: ca1c04c7b2e9
Revises: e3c5f7d9b2a1
Create Date: 2026-04-24 03:00:00.000000

Story 10.4c. Extends the ``chat_messages.role`` CHECK constraint to include
``'tool'`` so the dispatcher can persist per-tool rows with
``role='tool'`` + ``redaction_flags.filter_source='tool_dispatcher'``.

``downgrade()`` deletes any ``role='tool'`` rows before restoring the old
CHECK — the previous constraint would otherwise be violated. This mirrors
the posture of 10.1b's own downgrade (data loss is accepted on downgrade
because the old form simply cannot hold the new rows).
"""

from typing import Sequence, Union

from alembic import op

revision: str = "ca1c04c7b2e9"
down_revision: Union[str, Sequence[str], None] = "e3c5f7d9b2a1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # DROP + ADD — the CHECK constraint is renamed back in place with the
    # wider allowed-values tuple.
    op.drop_constraint("ck_chat_messages_role", "chat_messages", type_="check")
    op.create_check_constraint(
        "ck_chat_messages_role",
        "chat_messages",
        "role IN ('user','assistant','system','tool')",
    )


def downgrade() -> None:
    # Delete any rows the old CHECK would reject, then restore the old
    # form. Data-loss invariant documented in the module docstring.
    op.execute("DELETE FROM chat_messages WHERE role = 'tool'")
    op.drop_constraint("ck_chat_messages_role", "chat_messages", type_="check")
    op.create_check_constraint(
        "ck_chat_messages_role",
        "chat_messages",
        "role IN ('user','assistant','system')",
    )
