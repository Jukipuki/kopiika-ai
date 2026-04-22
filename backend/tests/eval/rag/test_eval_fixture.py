"""Cheap, non-LLM, non-DB tests for the RAG eval fixture (Story 9.1).

Run on every default pytest sweep. Catches fixture regressions (missing
fields, bad language codes, stale topic coverage) without hitting any
external service.
"""

import json
from pathlib import Path

FIXTURE_PATH = Path(__file__).resolve().parent.parent.parent / "fixtures" / "rag_eval" / "eval_set.jsonl"
CORPUS_ROOT = Path(__file__).resolve().parent.parent.parent.parent / "data" / "rag-corpus"

REQUIRED_FIELDS = {
    "id",
    "language",
    "question",
    "expected_doc_ids",
    "topic",
    "question_type",
    "notes",
}
VALID_LANGUAGES = {"en", "uk"}
VALID_QUESTION_TYPES = {"factual", "applied", "definitional"}


def _load_eval_set() -> list[dict]:
    rows: list[dict] = []
    for i, line in enumerate(FIXTURE_PATH.read_text(encoding="utf-8").splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            rows.append(json.loads(stripped))
        except json.JSONDecodeError as exc:
            raise AssertionError(f"eval_set.jsonl line {i} failed to parse: {exc.msg}") from exc
    return rows


def test_eval_set_schema() -> None:
    rows = _load_eval_set()
    assert len(rows) >= 40, f"eval_set.jsonl must contain ≥40 rows, found {len(rows)}"

    seen_ids: set[str] = set()
    for row in rows:
        missing = REQUIRED_FIELDS - row.keys()
        assert not missing, f"row {row.get('id')!r} missing required fields: {missing}"
        assert isinstance(row["id"], str) and row["id"], f"row id must be non-empty string: {row!r}"
        assert row["id"] not in seen_ids, f"duplicate id {row['id']!r}"
        seen_ids.add(row["id"])
        assert row["language"] in VALID_LANGUAGES, (
            f"row {row['id']}: language must be one of {VALID_LANGUAGES}, got {row['language']!r}"
        )
        assert isinstance(row["question"], str) and row["question"].strip(), (
            f"row {row['id']}: question must be non-empty string"
        )
        assert isinstance(row["expected_doc_ids"], list) and row["expected_doc_ids"], (
            f"row {row['id']}: expected_doc_ids must be a non-empty list"
        )
        for doc_id in row["expected_doc_ids"]:
            assert isinstance(doc_id, str) and "/" in doc_id, (
                f"row {row['id']}: expected_doc_ids entries must be '{{lang}}/{{slug}}' strings, got {doc_id!r}"
            )
            lang, _, slug = doc_id.partition("/")
            assert lang in VALID_LANGUAGES, f"row {row['id']}: bad language prefix in {doc_id!r}"
            assert slug, f"row {row['id']}: empty slug in {doc_id!r}"
        assert isinstance(row["topic"], str) and row["topic"], f"row {row['id']}: topic required"
        assert row["question_type"] in VALID_QUESTION_TYPES, (
            f"row {row['id']}: question_type must be one of {VALID_QUESTION_TYPES}, got {row['question_type']!r}"
        )
        assert isinstance(row["notes"], str), f"row {row['id']}: notes must be a string"


def test_topic_coverage() -> None:
    """Every corpus topic (EN + UA) must have ≥1 question per language."""
    en_topics = {p.stem for p in CORPUS_ROOT.glob("en/*.md")}
    uk_topics = {p.stem for p in CORPUS_ROOT.glob("uk/*.md")}
    assert en_topics, f"No EN corpus files found under {CORPUS_ROOT / 'en'}"
    assert uk_topics, f"No UK corpus files found under {CORPUS_ROOT / 'uk'}"

    rows = _load_eval_set()
    en_covered = {row["topic"] for row in rows if row["language"] == "en"}
    uk_covered = {row["topic"] for row in rows if row["language"] == "uk"}

    missing_en = en_topics - en_covered
    missing_uk = uk_topics - uk_covered
    assert not missing_en, f"EN topics without any eval question: {sorted(missing_en)}"
    assert not missing_uk, f"UK topics without any eval question: {sorted(missing_uk)}"


def test_expected_doc_ids_reference_real_corpus_files() -> None:
    """Every gold doc id must map to an actual corpus markdown file."""
    rows = _load_eval_set()
    for row in rows:
        for doc_id in row["expected_doc_ids"]:
            lang, _, slug = doc_id.partition("/")
            path = CORPUS_ROOT / lang / f"{slug}.md"
            assert path.exists(), (
                f"row {row['id']}: expected_doc_ids references {doc_id!r} but "
                f"{path} does not exist"
            )
