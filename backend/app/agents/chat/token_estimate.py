"""Cheap upper-bound input-token estimator for the daily-cap pre-gate.

Story 10.11 — used by the chat route to call
``RateLimiter.check_chat_daily_token_cap`` BEFORE invoking the model.
The estimator is intentionally an OVER-estimate (denial-of-wallet bias
is correct: occasional false-positive blocks beat under-blocking past
the cap).

Heuristic: ``len(message) // 3 + 8000``.
  - ``len(message) // 3`` ≈ 1 token per 3 chars (English-skewed; UA
    tokens are ~2.5 chars in Bedrock's current tokenizer — the // 3
    over-estimates UA slightly more, which is fine).
  - ``+ 8000`` for the system prompt + memory window per
    ``architecture.md`` L1726-L1727 bound.
  - Output tokens are NOT projected — they're bounded by Bedrock's
    ``maxTokens`` (typically 4096) and the post-turn
    ``record_chat_token_spend`` records actual usage including output,
    so the correction settles into the next-turn projection naturally.

TD-141 tracks replacing this with a Bedrock-side ``count_tokens`` call
once one exists in ``bedrock-runtime``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.chat_session import ChatSession


def estimate_input_tokens(
    message: str, session: "ChatSession | None" = None
) -> int:
    """Upper-bound projection of input + memory tokens for one chat turn.

    The ``session`` parameter is reserved for the eventual TD-141 swap to
    a Bedrock-side ``count_tokens`` call (which will need per-session
    memory context). The current heuristic ignores it.
    """
    del session  # reserved for TD-141.
    return len(message) // 3 + 8000


__all__ = ["estimate_input_tokens"]
