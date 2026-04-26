"""Shared fixtures for the AI safety harness.

Story 10.8a left this as a placeholder; Story 10.8b adds:

  - ``safety_runner_user_holder`` — a mutable dict the test populates with
    the authenticated user's UUID inside its own asyncio loop. Read by the
    tool stubs at call time so cross-user authorization checks always see
    the live user.
  - ``safety_runner_handler`` — a ``ChatSessionHandler`` with the read-only
    tool manifest patched to return synthetic data scoped to whichever
    user_id is in ``safety_runner_user_holder["id"]`` at call time.

The handler-loop pattern mirrors
``backend/tests/eval/chat_grounding/test_chat_grounding_harness.py`` —
session-scoped async fixtures cannot share asyncpg connections with
``asyncio.run()`` inside the test body (different loops), so user creation
happens inside the test's own loop.

The default-collected unit tests (``runner/test_*.py``) do not depend on
these fixtures and pay no DB / Bedrock cost.
"""

from __future__ import annotations

import pytest


@pytest.fixture
def safety_runner_user_holder() -> dict:
    """Mutable holder; the test sets ``["id"]`` to the live user's UUID
    before driving the first row, so tool stubs see a stable target.
    """
    return {"id": None}


@pytest.fixture
def safety_runner_handler(monkeypatch, safety_runner_user_holder):
    """Yield a ``ChatSessionHandler`` with read-only tool stubs installed.

    The stubs read ``safety_runner_user_holder["id"]`` at call time (closure),
    so the test only needs to populate the holder once before the first
    ``send_turn``. Foreign-user data is never returned (tool stubs raise
    ``ChatToolAuthorizationError`` on a mismatched ``user_id`` kwarg).
    """
    from app.agents.chat.session_handler import ChatSessionHandler, build_backend
    from tests.ai_safety.runner.tool_stubs import install_tool_stubs

    install_tool_stubs(monkeypatch, user_id_holder=safety_runner_user_holder)
    yield ChatSessionHandler(build_backend())
