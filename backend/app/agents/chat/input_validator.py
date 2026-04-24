"""Input-layer validator — Story 10.4b AC #4.

# SCOPE: Length cap + Unicode-category allowlist + jailbreak-pattern blocklist
# on user chat input. Runs BEFORE memory bounds / model invocation; short-
# circuits on first violation. First-match wins for jailbreak patterns — the
# matched text is never logged (logging an attacker's payload would let them
# steer the log-shipping pipeline); only a Blake2b prefix hash + the
# pattern_id cross the logging boundary.
#
# Decision (Story 10.4b Debug Log, 2026-04-24): the \\p{S} symbol category
# IS ALLOWED — emoji pass. Ukrainian chat UX is hostile without emoji; the
# threat of emoji-borne injection is already covered by the jailbreak
# blocklist and by format-character rejection.
#
# Non-goals (sibling/downstream):
#   - CHAT_REFUSED envelope                    → Story 10.5
#   - Full red-team corpus                     → Stories 10.8a / 10.8b
#   - Bedrock Guardrail input attachment       → Story 10.5
"""

from __future__ import annotations

import hashlib
from importlib import resources
from typing import Literal

import regex as re
import yaml

from app.core.config import settings


class ChatInputBlockedError(Exception):
    """Raised when user input violates any of the three layers."""

    def __init__(
        self,
        reason: Literal[
            "empty", "too_long", "disallowed_characters", "jailbreak_pattern"
        ],
        detail: str,
        pattern_id: str | None = None,
    ) -> None:
        self.reason = reason
        self.detail = detail
        self.pattern_id = pattern_id
        super().__init__(detail)


# Seeded from settings at import. A module-level constant keeps the value
# greppable; the cross-check below fails loud on settings drift.
MAX_CHAT_INPUT_CHARS: int = settings.CHAT_INPUT_MAX_CHARS


# Allowlist: Unicode letters + marks + numbers + symbols (emoji) + punctuation
# + separator-space + explicit whitespace controls. Excludes \p{C} (control,
# format, private-use, surrogate) except for \n \r \t explicitly — this is
# the common prompt-injection steganography surface.
_ALLOWED_CHARSET = re.compile(
    r"^[\p{L}\p{M}\p{N}\p{S}\p{P}\p{Zs}\n\r\t]+$",
    flags=re.V1,
)


def _load_patterns() -> tuple[str, list[tuple[str, "re.Pattern"]]]:
    raw = (
        resources.files("app.agents.chat")
        .joinpath("jailbreak_patterns.yaml")
        .read_text()
    )
    doc = yaml.safe_load(raw)
    if not isinstance(doc, dict) or "patterns" not in doc:
        raise RuntimeError(
            "jailbreak_patterns.yaml is malformed — expected top-level "
            "keys 'version' + 'patterns'."
        )
    version = str(doc.get("version", "unknown"))
    compiled: list[tuple[str, re.Pattern]] = []
    for entry in doc["patterns"]:
        pid = entry["id"]
        pat = re.compile(entry["regex"], flags=re.V1)
        compiled.append((pid, pat))
    return version, compiled


INPUT_VALIDATOR_VERSION, _COMPILED_PATTERNS = _load_patterns()


# Cross-check: MAX_CHAT_INPUT_CHARS must equal settings.CHAT_INPUT_MAX_CHARS.
# Keeping load-test tuning a config flip — a future drift between this
# module's constant and settings would silently mismatch at runtime.
if MAX_CHAT_INPUT_CHARS != settings.CHAT_INPUT_MAX_CHARS:
    raise RuntimeError(
        "input_validator.MAX_CHAT_INPUT_CHARS drifted from "
        "settings.CHAT_INPUT_MAX_CHARS — settings is the single source of truth."
    )


def _prefix_hash(s: str) -> str:
    return hashlib.blake2b(s[:64].encode("utf-8"), digest_size=8).hexdigest()


def validate_input(user_message: str) -> None:
    """Raises ChatInputBlockedError on any violation; otherwise returns.

    Evaluation order: length → character-class → jailbreak patterns. First
    violation short-circuits. For jailbreak matches, ``detail`` carries the
    ``pattern_id`` — never the matched text.
    """
    # 1. Empty / whitespace-only rejection. An empty user message has
    #    nothing for the LLM to act on and can't carry a jailbreak payload,
    #    but it also can't be usefully classified — block at the boundary
    #    so SSE callers see a clean refusal rather than a zero-length turn.
    if not user_message or not user_message.strip():
        raise ChatInputBlockedError(
            reason="empty",
            detail="Input is empty or whitespace-only.",
        )

    # 2. Length cap.
    if len(user_message) > MAX_CHAT_INPUT_CHARS:
        raise ChatInputBlockedError(
            reason="too_long",
            detail=(
                f"Input is {len(user_message)} chars; max is {MAX_CHAT_INPUT_CHARS}."
            ),
        )

    # 3. Character-class allowlist.
    if not _ALLOWED_CHARSET.match(user_message):
        raise ChatInputBlockedError(
            reason="disallowed_characters",
            detail="Input contains control / format / private-use characters.",
        )

    # 4. Jailbreak blocklist. First match wins.
    for pattern_id, pattern in _COMPILED_PATTERNS:
        if pattern.search(user_message):
            raise ChatInputBlockedError(
                reason="jailbreak_pattern",
                detail=pattern_id,
                pattern_id=pattern_id,
            )


__all__ = [
    "ChatInputBlockedError",
    "INPUT_VALIDATOR_VERSION",
    "MAX_CHAT_INPUT_CHARS",
    "validate_input",
]
