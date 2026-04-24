"""Static verification of the ``role='tool'`` migration (Story 10.4c AC #12).

A true upgrade/downgrade roundtrip requires a live Postgres — the migration
uses ``ALTER TABLE ... DROP CONSTRAINT`` which SQLite cannot execute. This
test inspects the migration module's ``upgrade`` and ``downgrade`` calls
via a mocked alembic ``op`` facade so CI (SQLite-only) can still assert
the shape of the DDL the migration emits.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch


MIGRATION_FILE = (
    Path(__file__).resolve().parents[1]
    / "alembic"
    / "versions"
    / "ca1c04c7b2e9_add_chat_message_role_tool.py"
)


def _reload_module():
    # The alembic ``versions`` tree is not a package — load by path.
    spec = importlib.util.spec_from_file_location("mig_ca1c04c7b2e9", MIGRATION_FILE)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_upgrade_drops_then_adds_widened_check():
    mod = _reload_module()
    fake_op = MagicMock()
    with patch.object(mod, "op", fake_op):
        mod.upgrade()
    calls = fake_op.mock_calls
    # drop_constraint fires before create_check_constraint.
    drop_idx = next(i for i, c in enumerate(calls) if c[0] == "drop_constraint")
    create_idx = next(
        i for i, c in enumerate(calls) if c[0] == "create_check_constraint"
    )
    assert drop_idx < create_idx
    # The new CHECK carries 'tool' in the allowed values.
    create_args = fake_op.create_check_constraint.call_args
    _name, _table, condition = create_args[0][:3]
    assert "'tool'" in condition
    assert "ck_chat_messages_role" == _name


def test_downgrade_deletes_tool_rows_before_restoring_old_check():
    mod = _reload_module()
    fake_op = MagicMock()
    with patch.object(mod, "op", fake_op):
        mod.downgrade()
    calls = [(c[0], c[1], c[2]) for c in fake_op.mock_calls]
    # execute(DELETE) must precede drop_constraint + create_check_constraint.
    exec_idx = next(
        i
        for i, (name, args, _kwargs) in enumerate(calls)
        if name == "execute" and "DELETE FROM chat_messages" in args[0]
    )
    drop_idx = next(
        i for i, (name, *_rest) in enumerate(calls) if name == "drop_constraint"
    )
    create_idx = next(
        i for i, (name, *_rest) in enumerate(calls) if name == "create_check_constraint"
    )
    assert exec_idx < drop_idx < create_idx
    # Old CHECK restored WITHOUT 'tool'.
    _name, _table, condition = fake_op.create_check_constraint.call_args[0][:3]
    assert "'tool'" not in condition
    assert (
        "'user'" in condition and "'assistant'" in condition and "'system'" in condition
    )


def test_migration_down_revision_chains_to_chat_messages_head():
    mod = _reload_module()
    assert mod.down_revision == "e3c5f7d9b2a1"
    assert mod.revision == "ca1c04c7b2e9"
