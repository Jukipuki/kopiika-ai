"""Pytest config for the chat-grounding eval harness (Story 10.6a).

The ``eval`` and ``integration`` markers are registered globally in
``backend/pyproject.toml``; no local registration needed. This file exists
so future harness-only fixtures (synthetic chat user factory, tool-stub
helpers) have a home.
"""

from __future__ import annotations
