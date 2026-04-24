"""Unit tests for memory_bounds — pure-policy module, no DB, no AWS, no LLM."""

from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest

from app.agents.chat import memory_bounds
from app.models.chat_message import ChatMessage


def _msg(role: str, content: str) -> ChatMessage:
    return ChatMessage(
        id=uuid.uuid4(),
        session_id=uuid.uuid4(),
        role=role,  # type: ignore[arg-type]
        content=content,
    )


# ---------------------------------------------------------------------------
# count_turns
# ---------------------------------------------------------------------------


def test_count_turns_empty_returns_zero():
    assert memory_bounds.count_turns([]) == 0


def test_count_turns_counts_user_messages_only():
    msgs = [
        _msg("system", "summary"),
        _msg("user", "q1"),
        _msg("assistant", "a1"),
        _msg("user", "q2"),
        _msg("assistant", "a2"),
    ]
    assert memory_bounds.count_turns(msgs) == 2


def test_count_turns_unpaired_trailing_user_counts():
    msgs = [
        _msg("user", "q1"),
        _msg("assistant", "a1"),
        _msg("user", "q2"),  # unpaired — still a turn
    ]
    assert memory_bounds.count_turns(msgs) == 2


def test_count_turns_ignores_system_and_assistant():
    msgs = [_msg("assistant", "hi"), _msg("system", "s")]
    assert memory_bounds.count_turns(msgs) == 0


# ---------------------------------------------------------------------------
# estimate_tokens — over-count direction asserted via known fixture
# ---------------------------------------------------------------------------


FIXTURE_PATH = (
    Path(__file__).parent.parent.parent
    / "fixtures"
    / "chat"
    / "tokenization_samples.json"
)


@pytest.fixture(scope="module")
def tokenization_fixture() -> list[dict]:
    data = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    return data["samples"]


def test_estimate_tokens_empty_list_is_zero():
    assert memory_bounds.estimate_tokens([]) == 0


def test_estimate_tokens_single_empty_content_is_zero():
    assert memory_bounds.estimate_tokens([_msg("user", "")]) == 0


def test_estimate_tokens_matches_fixture(tokenization_fixture):
    """Every fixture sample matches the captured cl100k_base count exactly.

    The fixture pins the encoding's behavior on representative EN/UA inputs,
    so an accidental change of encoding or a tiktoken upgrade that alters
    cl100k_base will surface here immediately.
    """
    for sample in tokenization_fixture:
        msgs = [_msg("user", sample["text"])]
        assert memory_bounds.estimate_tokens(msgs) == sample["cl100k_tokens"], (
            f"sample={sample['name']!r}"
        )


def test_estimate_tokens_overcounts_ukrainian_vs_ascii_chars(tokenization_fixture):
    """cl100k_base yields more tokens per character for UA than plain ASCII.

    This is the documented over-count direction (module docstring): UA
    inflates because the encoder splits each Ukrainian glyph across several
    byte-level BPE tokens. The *direction* is what matters for the bound —
    we never under-count Ukrainian, so the 8k-token ceiling stays a safe
    upper bound whichever Anthropic tokenizer is used server-side.
    """
    ua_long = next(s for s in tokenization_fixture if s["name"] == "ua_long")
    en_long = next(s for s in tokenization_fixture if s["name"] == "en_long")
    ua_tokens_per_char = ua_long["cl100k_tokens"] / max(len(ua_long["text"]), 1)
    en_tokens_per_char = en_long["cl100k_tokens"] / max(len(en_long["text"]), 1)
    assert ua_tokens_per_char > en_tokens_per_char


def test_estimate_tokens_sums_multiple_messages(tokenization_fixture):
    s1 = next(s for s in tokenization_fixture if s["name"] == "en_short")
    s2 = next(s for s in tokenization_fixture if s["name"] == "ua_short")
    msgs = [_msg("user", s1["text"]), _msg("assistant", s2["text"])]
    assert (
        memory_bounds.estimate_tokens(msgs) == s1["cl100k_tokens"] + s2["cl100k_tokens"]
    )


# ---------------------------------------------------------------------------
# should_summarize — boundary cases
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "turns,tokens,expected",
    [
        (19, 7999, False),  # both below
        (20, 7999, True),  # turns boundary (==)
        (19, 8000, True),  # tokens boundary (==)
        (21, 8100, True),  # both above
        (0, 0, False),  # empty
        (20, 0, True),  # turns alone
        (0, 8000, True),  # tokens alone
    ],
)
def test_should_summarize_boundaries(turns, tokens, expected):
    assert memory_bounds.should_summarize(turns, tokens, 20, 8000) is expected


# ---------------------------------------------------------------------------
# split_for_summarization — edge cases
# ---------------------------------------------------------------------------


def test_split_empty_list():
    assert memory_bounds.split_for_summarization([], keep_recent=6) == ([], [])


def test_split_fewer_than_keep_recent_turns():
    msgs = [
        _msg("user", "u1"),
        _msg("assistant", "a1"),
        _msg("user", "u2"),
        _msg("assistant", "a2"),
    ]
    older, recent = memory_bounds.split_for_summarization(msgs, keep_recent=6)
    assert older == []
    assert recent == msgs


def test_split_exactly_keep_recent_turns():
    # 3 turns, keep_recent=3 → no split (len <= keep_recent)
    msgs: list[ChatMessage] = []
    for i in range(3):
        msgs.append(_msg("user", f"u{i}"))
        msgs.append(_msg("assistant", f"a{i}"))
    older, recent = memory_bounds.split_for_summarization(msgs, keep_recent=3)
    assert older == []
    assert recent == msgs


def test_split_keeps_recent_tail():
    # 10 turns, keep_recent=3 → older=7 turns (14 msgs), recent=3 turns (6 msgs)
    msgs: list[ChatMessage] = []
    for i in range(10):
        msgs.append(_msg("user", f"u{i}"))
        msgs.append(_msg("assistant", f"a{i}"))
    older, recent = memory_bounds.split_for_summarization(msgs, keep_recent=3)
    assert len(older) == 14
    assert len(recent) == 6
    # recent contains the last 3 user prompts in order
    assert [m.content for m in recent if m.role == "user"] == ["u7", "u8", "u9"]


def test_split_unpaired_trailing_user():
    # 4 turns of user+assistant, then trailing user row
    msgs: list[ChatMessage] = []
    for i in range(4):
        msgs.append(_msg("user", f"u{i}"))
        msgs.append(_msg("assistant", f"a{i}"))
    msgs.append(_msg("user", "u4"))  # unpaired
    older, recent = memory_bounds.split_for_summarization(msgs, keep_recent=2)
    # user count = 5; keep last 2 turns means cut at user-3
    user_contents_in_recent = [m.content for m in recent if m.role == "user"]
    assert user_contents_in_recent == ["u3", "u4"]
    # older preserves chronological order, no duplication
    assert older == msgs[: len(msgs) - len(recent)]


def test_split_preserves_interleaved_system_rows():
    # system summary row at position 0 then full conversation
    msgs: list[ChatMessage] = [_msg("system", "summary-of-earlier")]
    for i in range(5):
        msgs.append(_msg("user", f"u{i}"))
        msgs.append(_msg("assistant", f"a{i}"))
    older, recent = memory_bounds.split_for_summarization(msgs, keep_recent=2)
    # system row is not a user turn → stays in older
    assert any(m.role == "system" for m in older)
    assert len([m for m in recent if m.role == "user"]) == 2


def test_split_keep_recent_zero_returns_empty_older():
    msgs = [_msg("user", "u1"), _msg("assistant", "a1")]
    older, recent = memory_bounds.split_for_summarization(msgs, keep_recent=0)
    assert older == []
    assert recent == msgs
