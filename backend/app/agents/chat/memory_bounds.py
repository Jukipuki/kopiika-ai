"""Pure-policy memory-window + summarization-trigger primitives for chat.

Story 10.4a (Phase A per ADR-0004). No I/O, no DB, no network. The
``ChatSessionHandler`` imports these functions to decide whether a session
needs summarization before the next model invocation.

Token accounting uses ``tiktoken`` with the ``cl100k_base`` encoding as an
EN/UA-safe approximation. AWS does not publish a first-party Anthropic
tokenizer for Python; ``cl100k_base`` over-counts Ukrainian text by roughly
15–20% vs. the real Anthropic tokenization. That is the safe direction for a
bound — we trigger summarization *slightly early*, never late — and matches
the safety-margin posture of architecture.md §Memory & Session Bounds
(L1717–L1721): 20 turns or 8k tokens, whichever is first.

Network-hitting a tokenizer endpoint inside a policy helper would defeat the
point of splitting policy from the handler, so this module deliberately
prefers the local approximation.
"""

from __future__ import annotations

import functools

import tiktoken

from app.models.chat_message import ChatMessage


@functools.lru_cache(maxsize=1)
def _encoding() -> tiktoken.Encoding:
    return tiktoken.get_encoding("cl100k_base")


def count_turns(messages: list[ChatMessage]) -> int:
    """Number of user-role messages. One turn == one user prompt (+ its reply).

    An unpaired trailing user message still counts as one turn — the next
    assistant reply completes that same turn.
    """
    return sum(1 for m in messages if m.role == "user")


def estimate_tokens(messages: list[ChatMessage]) -> int:
    """Approximate token count of the conversation content using cl100k_base.

    Sums only ``content`` — role markers, tool markers, and system-prompt
    padding are handler-layer concerns and not included here. Slight
    over-count for UA is intentional (see module docstring).
    """
    if not messages:
        return 0
    enc = _encoding()
    total = 0
    for m in messages:
        total += len(enc.encode(m.content))
    return total


def should_summarize(turns: int, tokens: int, max_turns: int, max_tokens: int) -> bool:
    """True iff either bound is met. Literal reading of "whichever is first"."""
    return turns >= max_turns or tokens >= max_tokens


def split_for_summarization(
    messages: list[ChatMessage], keep_recent: int
) -> tuple[list[ChatMessage], list[ChatMessage]]:
    """Split ``messages`` into ``(older, recent)`` preserving chronological order.

    ``recent`` is the tail of ``keep_recent`` turns, where each turn pairs a
    ``user`` message with its following ``assistant`` reply. If the tail
    starts mid-turn (e.g. an orphan ``assistant`` row) the split walks
    backwards from the end until it has collected the requested turns;
    returned ``recent`` may therefore contain more than ``keep_recent * 2``
    rows if summary/system rows are interleaved.

    If the input has fewer than ``keep_recent`` complete turns, returns
    ``([], messages)`` — there is nothing worth summarizing yet and the
    caller should continue with the full context.
    """
    if keep_recent <= 0 or not messages:
        return ([], messages)

    user_positions = [i for i, m in enumerate(messages) if m.role == "user"]
    if len(user_positions) <= keep_recent:
        return ([], messages)

    # The first user message of the tail we want to keep is the
    # ``keep_recent``-th from the end of ``user_positions``.
    cut = user_positions[-keep_recent]
    return (messages[:cut], messages[cut:])
