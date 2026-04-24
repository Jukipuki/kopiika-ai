"""Tests for ``dispatch_tool`` (Story 10.4c AC #6 + #10 + #12)."""

from __future__ import annotations

import logging
import uuid
from contextlib import contextmanager
from unittest.mock import AsyncMock

import pytest
from pydantic import BaseModel
from sqlalchemy.exc import SQLAlchemyError

from app.agents.chat.tools import TOOL_MANIFEST
from app.agents.chat.tools.dispatcher import (
    ToolInvocation,
    dispatch_tool,
)
from app.agents.chat.tools.tool_errors import ChatToolAuthorizationError


@pytest.fixture(autouse=True)
def _propagate_app_logger():
    """The ``app`` logger has propagate=False in production; caplog attaches
    to root, so records never reach it. Flip the whole ``app`` subtree.
    """
    lg = logging.getLogger("app")
    prev = lg.propagate
    lg.propagate = True
    yield
    lg.propagate = prev


@contextmanager
def _patch_spec_handler(tool_name: str, handler):
    """Temporarily swap the ``handler`` on a frozen ToolSpec in TOOL_MANIFEST."""
    for spec in TOOL_MANIFEST:
        if spec.name == tool_name:
            old = spec.handler
            object.__setattr__(spec, "handler", handler)
            try:
                yield
            finally:
                object.__setattr__(spec, "handler", old)
            return
    raise KeyError(tool_name)


@pytest.mark.asyncio
async def test_unknown_tool_returns_not_allowed_result(caplog):
    inv = ToolInvocation(tool_name="does_not_exist", raw_input={}, tool_use_id="tu_1")
    with caplog.at_level("WARNING"):
        result = await dispatch_tool(inv, user_id=uuid.uuid4(), db=None)
    assert result.ok is False
    assert result.error_kind == "not_allowed"
    assert "tool_name" in result.payload
    assert any(r.message == "chat.tool.blocked" for r in caplog.records)


@pytest.mark.asyncio
async def test_schema_error_never_echoes_raw_input(caplog):
    # limit is constrained to 1..200 — pass a string to force ValidationError.
    inv = ToolInvocation(
        tool_name="get_transactions",
        raw_input={"limit": "sqli-attempt-{'x':1}"},
        tool_use_id="tu_2",
    )
    with caplog.at_level("WARNING"):
        result = await dispatch_tool(inv, user_id=uuid.uuid4(), db=None)
    assert result.ok is False
    assert result.error_kind == "schema_error"
    # The adversarial string must not appear anywhere in the returned payload.
    assert "sqli-attempt" not in str(result.payload)


@pytest.mark.asyncio
async def test_sqlalchemy_error_maps_to_execution_error(caplog):
    with _patch_spec_handler(
        "get_transactions", AsyncMock(side_effect=SQLAlchemyError("db-fail"))
    ):
        inv = ToolInvocation(
            tool_name="get_transactions",
            raw_input={"limit": 10},
            tool_use_id="tu_3",
        )
        with caplog.at_level("ERROR"):
            result = await dispatch_tool(inv, user_id=uuid.uuid4(), db=None)
    assert result.ok is False
    assert result.error_kind == "execution_error"
    exec_events = [
        r for r in caplog.records if r.message == "chat.tool.execution_failed"
    ]
    assert exec_events


@pytest.mark.asyncio
async def test_permission_error_raises_authorization_error(caplog):
    with _patch_spec_handler(
        "get_transactions", AsyncMock(side_effect=PermissionError("cross-user"))
    ):
        inv = ToolInvocation(
            tool_name="get_transactions",
            raw_input={"limit": 10},
            tool_use_id="tu_4",
        )
        with caplog.at_level("ERROR"):
            with pytest.raises(ChatToolAuthorizationError):
                await dispatch_tool(inv, user_id=uuid.uuid4(), db=None)
    assert any(r.message == "chat.tool.authorization_failed" for r in caplog.records)


@pytest.mark.asyncio
async def test_output_schema_drift_surfaces_as_execution_error(caplog):
    class _Bogus(BaseModel):
        not_rows: str = "nope"

    with _patch_spec_handler("get_transactions", AsyncMock(return_value=_Bogus())):
        inv = ToolInvocation(
            tool_name="get_transactions",
            raw_input={"limit": 10},
            tool_use_id="tu_5",
        )
        with caplog.at_level("ERROR"):
            result = await dispatch_tool(inv, user_id=uuid.uuid4(), db=None)
    assert result.ok is False
    assert result.error_kind == "execution_error"
    drift_events = [
        r for r in caplog.records if r.message == "chat.tool.output_schema_drift"
    ]
    assert drift_events


@pytest.mark.asyncio
async def test_max_rows_second_layer_truncation():
    # Hand-craft an output with 300 synthetic rows so the dispatcher's
    # second-layer cap (spec.max_rows=200 for get_transactions) trips.
    from app.agents.chat.tools.transactions_tool import (
        GetTransactionsOutput,
        TransactionRow,
    )
    from datetime import date

    rows = [
        TransactionRow(
            id=uuid.uuid4(),
            booked_at=date(2026, 1, 1),
            description=f"x{i}",
            amount_kopiykas=-1,
            currency="UAH",
            category_code=None,
            transaction_kind="spending",
        )
        for i in range(300)
    ]
    oversized = GetTransactionsOutput(rows=rows, row_count=300, truncated=False)
    with _patch_spec_handler("get_transactions", AsyncMock(return_value=oversized)):
        inv = ToolInvocation(
            tool_name="get_transactions",
            raw_input={"limit": 200},
            tool_use_id="tu_6",
        )
        result = await dispatch_tool(inv, user_id=uuid.uuid4(), db=None)
    assert result.ok is True
    assert result.payload["row_count"] == 200
    assert result.payload["truncated"] is True


@pytest.mark.asyncio
async def test_elapsed_ms_is_populated(caplog):
    inv = ToolInvocation(tool_name="does_not_exist", raw_input={}, tool_use_id="tu_7")
    result = await dispatch_tool(inv, user_id=uuid.uuid4(), db=None)
    assert result.elapsed_ms >= 0
