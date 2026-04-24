"""Tests for the chat tool manifest (Story 10.4c AC #1)."""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from app.agents.chat.tools import (
    CHAT_TOOL_MANIFEST_VERSION,
    TOOL_ALLOWLIST,
    TOOL_MANIFEST,
    ToolSpec,
    get_tool_spec,
    render_bedrock_tool_config,
)
from app.agents.chat.tools.tool_errors import ChatToolNotAllowedError


EXPECTED_NAMES = (
    "get_transactions",
    "get_profile",
    "get_teaching_feed",
    "search_financial_corpus",
)


def test_tool_manifest_is_frozen_tuple_in_authored_order():
    assert isinstance(TOOL_MANIFEST, tuple)
    assert tuple(spec.name for spec in TOOL_MANIFEST) == EXPECTED_NAMES
    for spec in TOOL_MANIFEST:
        assert isinstance(spec, ToolSpec)
        assert spec.max_rows >= 1


def test_tool_allowlist_is_frozenset_with_exact_members():
    assert isinstance(TOOL_ALLOWLIST, frozenset)
    assert TOOL_ALLOWLIST == frozenset(EXPECTED_NAMES)


def test_get_tool_spec_unknown_raises_not_allowed():
    with pytest.raises(ChatToolNotAllowedError) as exc:
        get_tool_spec("does_not_exist")
    assert exc.value.tool_name == "does_not_exist"


def test_get_tool_spec_known_returns_spec():
    spec = get_tool_spec("get_transactions")
    assert spec.name == "get_transactions"
    assert spec.max_rows == 200


def test_render_bedrock_tool_config_shape():
    cfg = render_bedrock_tool_config()
    assert set(cfg.keys()) == {"tools", "toolChoice"}
    assert cfg["toolChoice"] == {"auto": {}}
    assert len(cfg["tools"]) == 4
    for entry, spec in zip(cfg["tools"], TOOL_MANIFEST):
        assert set(entry.keys()) == {"toolSpec"}
        ts = entry["toolSpec"]
        assert ts["name"] == spec.name
        assert ts["description"] == spec.description
        assert "json" in ts["inputSchema"]
        # Pydantic v2 JSON Schema has a "type": "object" at the root for a
        # BaseModel — sanity check.
        assert ts["inputSchema"]["json"].get("type") == "object"


def test_manifest_version_matches_pattern():
    assert re.match(r"^10\.4c-v\d+$", CHAT_TOOL_MANIFEST_VERSION)


def test_no_handler_module_imports_sqlalchemy_write_ops():
    """AST-level grep — asserts the tool handler modules do not import
    ``sqlalchemy.update``, ``sqlalchemy.insert``, or ``sqlalchemy.delete``.
    Writes are forbidden by the Epic 10 no-write-tools invariant (AC #12).
    """
    tools_dir = (
        Path(__file__).resolve().parents[3] / "app" / "agents" / "chat" / "tools"
    )
    assert tools_dir.is_dir()

    banned_names = {"update", "insert", "delete"}
    banned_attr_paths = {"sa_update", "sa_insert", "sa_delete"}

    offenders: list[str] = []
    for py in tools_dir.glob("*.py"):
        source = py.read_text()
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module == "sqlalchemy":
                for alias in node.names:
                    if alias.name in banned_names:
                        offenders.append(
                            f"{py.name}:from sqlalchemy import {alias.name}"
                        )
                    if (alias.asname or alias.name) in banned_attr_paths:
                        offenders.append(
                            f"{py.name}:from sqlalchemy import {alias.name} as {alias.asname}"
                        )
    assert not offenders, f"Write-op imports detected: {offenders}"
