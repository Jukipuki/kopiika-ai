"""Red-team corpus loader (Story 10.8b AC #8).

Reads ``backend/tests/ai_safety/corpus/*.jsonl`` (frozen 10.8a output),
substitutes ``<CANARY_*>`` placeholders against the live canary set, and
returns a deterministic tuple of :class:`CorpusEntry` records.

# SCOPE: This module is internal to the safety test harness. It must never
# be imported from ``app.*`` runtime code. It MAY import from
# ``app.agents.chat.canaries`` (read-only, type definitions only). The
# loader never logs canary values; ``__repr__`` redacts the canary slots.
#
# Out-of-scope here (per Story 10.8b §Scope Boundaries):
#   - Schema validation        → 10.8a's ``test_corpus_schema.py``
#   - Per-row driver / asserts → ``test_red_team_runner.py``
#   - Run-report writing       → ``runner/report.py``
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.agents.chat.canaries import CanarySet, get_canary_set

CORPUS_DIR = Path(__file__).resolve().parent.parent / "corpus"
CANARY_PLACEHOLDERS: tuple[str, ...] = ("<CANARY_A>", "<CANARY_B>", "<CANARY_C>")
CANARY_LABEL = "Internal trace markers"

# File-glob order is alphabetical; AC #6 mandates this order in the report.
EXPECTED_FILES: tuple[str, ...] = (
    "canary_extraction.jsonl",
    "cross_user_probes.jsonl",
    "jailbreaks.jsonl",
    "owasp_llm_top10.jsonl",
    "ua_adversarial.jsonl",
)


class CorpusLoadError(RuntimeError):
    """Raised on unparseable JSONL or schema-shape failure at load time."""


@dataclass
class _ExpectedBlock:
    outcome: str
    refusal_reasons: tuple[str, ...]
    must_not_contain: tuple[str, ...]
    must_contain_any: tuple[str, ...]
    max_tool_hops: int


@dataclass
class CorpusEntry:
    """One adversarial corpus row, post canary substitution."""

    id: str
    file: str
    title: str
    language: str
    prompt: str
    expected: _ExpectedBlock
    notes: str
    tags: tuple[str, ...]
    owasp_category: str | None = None
    jailbreak_family: str | None = None
    line_number: int = 0
    extra: dict[str, Any] = field(default_factory=dict)

    def __repr__(self) -> str:  # noqa: D401 — redaction is the contract
        redacted_must_not = tuple(
            "<canary-A>"
            if s == CANARY_PLACEHOLDERS[0] or _looks_like_canary_a(s)
            else "<canary-B>"
            if s == CANARY_PLACEHOLDERS[1] or _looks_like_canary_b(s)
            else "<canary-C>"
            if s == CANARY_PLACEHOLDERS[2] or _looks_like_canary_c(s)
            else s
            for s in self.expected.must_not_contain
        )
        return (
            f"CorpusEntry(id={self.id!r}, file={self.file!r}, "
            f"language={self.language!r}, "
            f"expected.outcome={self.expected.outcome!r}, "
            f"expected.must_not_contain={list(redacted_must_not)!r}, "
            f"prompt=<{len(self.prompt)} chars>)"
        )


# Canary-substitution memo populated per-load (NOT module-level — would
# pin a dev-fallback set across Bedrock / non-Bedrock invocations).
_CANARY_SUBSTITUTION_HOLDER: dict[str, tuple[str, str, str]] = {}


def _looks_like_canary_a(s: str) -> bool:
    return bool(_CANARY_SUBSTITUTION_HOLDER) and s == _CANARY_SUBSTITUTION_HOLDER["v"][0]


def _looks_like_canary_b(s: str) -> bool:
    return bool(_CANARY_SUBSTITUTION_HOLDER) and s == _CANARY_SUBSTITUTION_HOLDER["v"][1]


def _looks_like_canary_c(s: str) -> bool:
    return bool(_CANARY_SUBSTITUTION_HOLDER) and s == _CANARY_SUBSTITUTION_HOLDER["v"][2]


def _validate_required(entry: dict, file_name: str, line_number: int) -> None:
    missing_top = {"id", "language", "prompt", "expected"} - entry.keys()
    if missing_top:
        raise CorpusLoadError(
            f"{file_name}:{line_number}: missing required keys {sorted(missing_top)}"
        )
    expected = entry["expected"]
    if not isinstance(expected, dict):
        raise CorpusLoadError(
            f"{file_name}:{line_number}: 'expected' must be a JSON object"
        )
    missing_exp = {
        "outcome",
        "refusal_reasons",
        "must_not_contain",
        "must_contain_any",
        "max_tool_hops",
    } - expected.keys()
    if missing_exp:
        raise CorpusLoadError(
            f"{file_name}:{line_number}: 'expected' missing {sorted(missing_exp)}"
        )
    if expected["outcome"] in {"refused", "refused_or_answered_safely"}:
        if not expected["refusal_reasons"]:
            raise CorpusLoadError(
                f"{file_name}:{line_number}: 'refusal_reasons' must be non-empty "
                f"when outcome={expected['outcome']!r}"
            )


def _substitute_canaries(strings: list[str], subs: tuple[str, str, str]) -> tuple[str, ...]:
    out: list[str] = []
    for s in strings:
        replaced = (
            s.replace(CANARY_PLACEHOLDERS[0], subs[0])
            .replace(CANARY_PLACEHOLDERS[1], subs[1])
            .replace(CANARY_PLACEHOLDERS[2], subs[2])
        )
        out.append(replaced)
    return tuple(out)


def _detect_jailbreak_family(tags: list[str]) -> str | None:
    families = {
        "dan-style",
        "developer-mode",
        "role-play",
        "translation-bypass",
        "encoding-bypass",
        "hypothetical-framing",
        "emotional-manipulation",
        "completion-bait",
    }
    for tag in tags:
        if tag in families:
            return tag
    return None


def _entry_from_dict(
    entry: dict,
    *,
    file_name: str,
    line_number: int,
    canary_substitution: tuple[str, str, str],
) -> CorpusEntry:
    _validate_required(entry, file_name, line_number)
    raw_expected = entry["expected"]
    must_not = list(raw_expected["must_not_contain"])
    must_any = list(raw_expected["must_contain_any"])

    expected = _ExpectedBlock(
        outcome=str(raw_expected["outcome"]),
        refusal_reasons=tuple(raw_expected["refusal_reasons"]),
        must_not_contain=_substitute_canaries(must_not, canary_substitution),
        must_contain_any=tuple(must_any),
        max_tool_hops=int(raw_expected["max_tool_hops"]),
    )

    tags = tuple(entry.get("tags", []) or [])
    return CorpusEntry(
        id=str(entry["id"]),
        file=file_name,
        title=str(entry.get("title", "")),
        language=str(entry["language"]),
        prompt=str(entry["prompt"]),
        expected=expected,
        notes=str(entry.get("notes", "")),
        tags=tags,
        owasp_category=entry.get("owasp_category"),
        jailbreak_family=_detect_jailbreak_family(list(tags)),
        line_number=line_number,
    )


def _parse_jsonl(path: Path) -> list[tuple[int, dict]]:
    out: list[tuple[int, dict]] = []
    text = path.read_text(encoding="utf-8")
    for lineno, raw in enumerate(text.splitlines(), start=1):
        if not raw.strip():
            continue
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise CorpusLoadError(
                f"{path.name}:{lineno}: invalid JSON ({exc.msg})"
            ) from exc
        if not isinstance(obj, dict):
            raise CorpusLoadError(
                f"{path.name}:{lineno}: top-level value must be a JSON object"
            )
        out.append((lineno, obj))
    return out


async def load_corpus(
    *,
    canary_set: CanarySet | None = None,
    corpus_dir: Path | None = None,
) -> tuple[CorpusEntry, ...]:
    """Load every ``corpus/*.jsonl`` file in deterministic order.

    Order is alphabetical-by-file then by `id` within each file (matches
    AC #6's report-row order). Canary substitution uses ``canary_set``
    when provided (test injection point) or ``get_canary_set()`` otherwise.
    """
    target_dir = corpus_dir or CORPUS_DIR
    cs = canary_set if canary_set is not None else await get_canary_set()
    subs = (cs.canary_a, cs.canary_b, cs.canary_c)
    _CANARY_SUBSTITUTION_HOLDER["v"] = subs

    out: list[CorpusEntry] = []
    discovered = sorted(target_dir.glob("*.jsonl"))
    discovered_names = {p.name for p in discovered}
    missing = set(EXPECTED_FILES) - discovered_names
    if missing:
        raise CorpusLoadError(
            f"corpus/ missing required files: {sorted(missing)}"
        )

    for path in discovered:
        rows = _parse_jsonl(path)
        rows.sort(key=lambda pair: pair[1].get("id", ""))
        for lineno, obj in rows:
            out.append(
                _entry_from_dict(
                    obj,
                    file_name=path.name,
                    line_number=lineno,
                    canary_substitution=subs,
                )
            )
    return tuple(out)


__all__ = [
    "CANARY_LABEL",
    "CANARY_PLACEHOLDERS",
    "CORPUS_DIR",
    "CorpusEntry",
    "CorpusLoadError",
    "EXPECTED_FILES",
    "load_corpus",
]
