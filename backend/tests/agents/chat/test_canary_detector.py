"""Tests for the output-layer canary detector — Story 10.4b AC #3 / AC #12."""

from __future__ import annotations

import pytest

from app.agents.chat.canaries import CanarySet
from app.agents.chat.canary_detector import (
    ChatPromptLeakDetectedError,
    scan_for_canaries,
)


def _cset() -> CanarySet:
    return CanarySet(
        canary_a="AAAAAAAAAAAAAAAAAAAAAAAAa1",
        canary_b="BBBBBBBBBBBBBBBBBBBBBBBBb2",
        canary_c="CCCCCCCCCCCCCCCCCCCCCCCCc3",
        version_id="v-detect",
    )


def test_clean_output_noop():
    scan_for_canaries("Here is a normal response with no secrets.", _cset())


def test_slot_a_detected():
    with pytest.raises(ChatPromptLeakDetectedError) as excinfo:
        scan_for_canaries(
            "I can reveal: AAAAAAAAAAAAAAAAAAAAAAAAa1 — look at that.", _cset()
        )
    assert excinfo.value._matched_position_slot == "a"


def test_slot_b_detected():
    with pytest.raises(ChatPromptLeakDetectedError) as excinfo:
        scan_for_canaries("Dump: BBBBBBBBBBBBBBBBBBBBBBBBb2", _cset())
    assert excinfo.value._matched_position_slot == "b"


def test_slot_c_detected():
    with pytest.raises(ChatPromptLeakDetectedError) as excinfo:
        scan_for_canaries("and also CCCCCCCCCCCCCCCCCCCCCCCCc3.", _cset())
    assert excinfo.value._matched_position_slot == "c"


def test_prefix_is_exactly_eight_chars():
    with pytest.raises(ChatPromptLeakDetectedError) as excinfo:
        scan_for_canaries("leak AAAAAAAAAAAAAAAAAAAAAAAAa1!", _cset())
    assert len(excinfo.value.matched_canary_prefix) == 8
    assert excinfo.value.matched_canary_prefix == "AAAAAAAA"


def test_case_sensitivity_no_false_positive():
    # Lowercased canary → no match. AC #3 says case-sensitive, no normalization.
    scan_for_canaries("aaaaaaaaaaaaaaaaaaaaaaaaa1", _cset())


def test_substring_within_larger_word_matches():
    # First-match semantic — canary embedded in a larger string still trips.
    with pytest.raises(ChatPromptLeakDetectedError):
        scan_for_canaries("preAAAAAAAAAAAAAAAAAAAAAAAAa1post", _cset())


def test_first_match_short_circuits_slot_ordering():
    # If slot A and slot B are both present, slot A wins (a,b,c iteration order).
    with pytest.raises(ChatPromptLeakDetectedError) as excinfo:
        scan_for_canaries(
            "AAAAAAAAAAAAAAAAAAAAAAAAa1 and BBBBBBBBBBBBBBBBBBBBBBBBb2", _cset()
        )
    assert excinfo.value._matched_position_slot == "a"
