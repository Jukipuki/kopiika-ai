"""Output-layer canary scan — Story 10.4b AC #3.

# SCOPE: Literal substring search for three canary tokens in LLM output;
# raises ChatPromptLeakDetectedError on the first match. Case-sensitive;
# no regex metacharacters (AC #2 constrains tokens to [A-Za-z0-9_-]) so a
# stdlib ``in`` check is 2-3 orders faster than re.search and semantically
# identical for this alphabet. Whitespace / unicode-normalization tolerance
# is intentionally omitted — TD-tracked (docs/tech-debt.md) as a known
# limitation; Story 10.8b's red-team runner is the gate.
#
# Non-goals (sibling/downstream):
#   - The CanaryLeaked metric + sev-1 alarm    → Story 10.9
#   - Unicode-normalized detection              → TD entry (tracked)
#   - CHAT_REFUSED envelope translation         → Story 10.5
"""

from __future__ import annotations

from typing import Literal

from app.agents.chat.canaries import CanarySet

_PREFIX_LEN = 8


class ChatPromptLeakDetectedError(Exception):
    """Raised when model output contains any canary token."""

    def __init__(
        self,
        matched_canary_prefix: str,
        *,
        matched_position_slot: Literal["a", "b", "c"],
    ) -> None:
        # 8-char prefix is the only canary-derived data that crosses the
        # log/exception boundary. Full tokens live in Secrets Manager + the
        # handler's in-process memory only.
        self.matched_canary_prefix = matched_canary_prefix
        # Private — not surfaced in __repr__ so a stray logger.exception()
        # can't ever leak the slot dimension. Story 10.9's metric filter
        # reads this via explicit attribute access.
        self._matched_position_slot: Literal["a", "b", "c"] = matched_position_slot
        super().__init__(
            f"Chat model output contained a canary token (slot={matched_position_slot})."
        )


def scan_for_canaries(output_text: str, canaries: CanarySet) -> None:
    """Raises ChatPromptLeakDetectedError on first match. No-op otherwise.

    First-match semantic short-circuits; order is (a, b, c) — slot ordering
    lets Story 10.8a's corpus assert per-slot coverage.
    """
    for slot, token in zip(("a", "b", "c"), canaries.as_tuple(), strict=True):
        if token in output_text:
            raise ChatPromptLeakDetectedError(
                matched_canary_prefix=token[:_PREFIX_LEN],
                matched_position_slot=slot,  # type: ignore[arg-type]
            )
