"""Single source of truth for the application's runtime version.

Reads the repo-root ``VERSION`` file once at module import so the backend,
tests, and any other consumer stay in lockstep with whatever the frontend
ships via ``NEXT_PUBLIC_APP_VERSION``. See ``docs/versioning.md`` for the
bump policy.
"""

from __future__ import annotations

import logging
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


APP_VERSION: str = _read_version_file()
