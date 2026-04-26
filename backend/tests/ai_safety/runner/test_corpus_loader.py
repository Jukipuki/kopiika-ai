"""Default-collected unit test for ``corpus_loader.py`` (Story 10.8b AC #8)."""

from __future__ import annotations

import asyncio

import pytest

from app.agents.chat.canaries import CanarySet
from tests.ai_safety.runner import corpus_loader
from tests.ai_safety.runner.corpus_loader import (
    CANARY_LABEL,
    CANARY_PLACEHOLDERS,
    EXPECTED_FILES,
    load_corpus,
)

_FAKE_SET = CanarySet(
    canary_a="fakeA_aaaaaaaaaaaaaaaaaaaaaaaaaaa",
    canary_b="fakeB_bbbbbbbbbbbbbbbbbbbbbbbbbbb",
    canary_c="fakeC_ccccccccccccccccccccccccccc",
    version_id="unit-test-fake",
)


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro) if False else asyncio.run(coro)


def test_load_corpus_substitutes_canary_placeholders() -> None:
    entries = _run(load_corpus(canary_set=_FAKE_SET))
    assert entries
    canary_entries = [e for e in entries if e.file == "canary_extraction.jsonl"]
    assert canary_entries, "canary_extraction.jsonl produced zero entries"
    for entry in canary_entries:
        # Placeholders MUST be gone from must_not_contain
        for placeholder in CANARY_PLACEHOLDERS:
            assert placeholder not in entry.expected.must_not_contain, (
                f"{entry.id}: placeholder {placeholder} not substituted"
            )
        assert _FAKE_SET.canary_a in entry.expected.must_not_contain
        assert _FAKE_SET.canary_b in entry.expected.must_not_contain
        assert _FAKE_SET.canary_c in entry.expected.must_not_contain
        # Prose anchor preserved verbatim
        assert CANARY_LABEL in entry.expected.must_not_contain


def test_load_corpus_repr_redacts_canary_values() -> None:
    entries = _run(load_corpus(canary_set=_FAKE_SET))
    canary_entries = [e for e in entries if e.file == "canary_extraction.jsonl"]
    sample = canary_entries[0]
    text = repr(sample)
    # The literal canary value must NEVER appear in the repr
    assert _FAKE_SET.canary_a not in text
    assert _FAKE_SET.canary_b not in text
    assert _FAKE_SET.canary_c not in text
    # Redacted slot labels appear instead
    assert "<canary-A>" in text
    assert "<canary-B>" in text
    assert "<canary-C>" in text


def test_load_corpus_loads_all_five_files_with_minimum_counts() -> None:
    entries = _run(load_corpus(canary_set=_FAKE_SET))
    by_file: dict[str, int] = {}
    for entry in entries:
        by_file[entry.file] = by_file.get(entry.file, 0) + 1

    minima = {
        "owasp_llm_top10.jsonl": 35,
        "jailbreaks.jsonl": 16,
        "ua_adversarial.jsonl": 20,
        "canary_extraction.jsonl": 12,
        "cross_user_probes.jsonl": 10,
    }
    for fname in EXPECTED_FILES:
        assert by_file.get(fname, 0) >= minima[fname], (
            f"{fname}: loaded {by_file.get(fname)} entries, expected ≥ {minima[fname]}"
        )
    assert sum(by_file.values()) >= 93


def test_load_corpus_uses_get_canary_set_when_no_override(monkeypatch) -> None:
    """When ``canary_set`` is omitted the loader calls ``get_canary_set()``."""
    called: list[bool] = []

    async def _fake_get_canary_set() -> CanarySet:
        called.append(True)
        return _FAKE_SET

    monkeypatch.setattr(corpus_loader, "get_canary_set", _fake_get_canary_set)
    entries = _run(load_corpus())
    assert entries
    assert called == [True]


def test_load_corpus_fails_fast_on_invalid_json(tmp_path) -> None:
    bad = tmp_path / "owasp_llm_top10.jsonl"
    bad.write_text("{not valid json}\n", encoding="utf-8")
    # Add minimal placeholders for the other expected files so the missing-file
    # guard does not fire first.
    for other in EXPECTED_FILES:
        if other == "owasp_llm_top10.jsonl":
            continue
        (tmp_path / other).write_text("", encoding="utf-8")
    with pytest.raises(corpus_loader.CorpusLoadError, match="invalid JSON"):
        _run(load_corpus(canary_set=_FAKE_SET, corpus_dir=tmp_path))
