"""Single source of truth for the application's runtime version.

Reads the repo-root ``VERSION`` file once at module import so the backend,
tests, and any other consumer stay in lockstep with whatever the frontend
ships via ``NEXT_PUBLIC_APP_VERSION``. See ``docs/versioning.md`` for the
bump policy.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

_FALLBACK_VERSION = "0.0.0+unknown"


def _read_version_file() -> str:
    # Walk up from this file looking for a sibling VERSION at the repo root.
    # Tests may run from either ``backend/`` or the repo root, so relying on
    # cwd is brittle; the file's own location is the stable anchor.
    for candidate in Path(__file__).resolve().parents:
        version_file = candidate / "VERSION"
        if version_file.is_file():
            return version_file.read_text(encoding="utf-8").strip()

    logger.warning(
        "VERSION file not found walking up from %s; falling back to %s",
        Path(__file__).resolve(),
        _FALLBACK_VERSION,
    )
    return _FALLBACK_VERSION


def _resolve_version() -> str:
    # Built-image path: the Dockerfile bakes APP_VERSION as an env var via
    # --build-arg, sourced from the repo-root VERSION file in CI. The repo-
    # root file isn't inside the backend/ build context so we can't COPY it.
    # Local-dev path: walk up to find the VERSION file.
    env_value = os.environ.get("APP_VERSION", "").strip()
    if env_value and env_value != _FALLBACK_VERSION:
        return env_value
    return _read_version_file()


APP_VERSION: str = _resolve_version()
