"""RAG evaluation harness (Story 9.1).

Exercises the live retriever + LLM stack against a labelled eval set and writes
a timestamped structured report. Story 9.1 installs the instrument; it does
not assert absolute pass/fail thresholds — Story 9.2 captures the baseline.

Run:
    cd backend && uv run pytest tests/eval/rag/ -v -m eval

Auto-skips if `document_embeddings` is empty or the DB is unreachable (AC #7).
"""

from __future__ import annotations

import datetime
import json
import logging
import time
from collections import defaultdict
from pathlib import Path

import pytest
from sqlalchemy import text

from app.core.database import get_sync_session
from app.rag.retriever import retrieve_relevant_docs
from tests.eval.rag import judge as judge_module
from tests.eval.rag.metrics import precision_at_k, reciprocal_rank, recall_at_k

logger = logging.getLogger(__name__)

_FIXTURE_DIR = Path(__file__).resolve().parent.parent.parent / "fixtures" / "rag_eval"
_EVAL_SET_PATH = _FIXTURE_DIR / "eval_set.jsonl"
_RUNS_DIR = _FIXTURE_DIR / "runs"
_CORPUS_ROOT = Path(__file__).resolve().parent.parent.parent.parent / "data" / "rag-corpus"

_TOP_K = 5
# Keep per-row gold content bounded — some corpus docs are multi-KB and we
# pay for every judge token. 6000 chars ≈ 1.5-2k tokens is enough context for
# the judge to assess relevance without blowing the per-run budget.
_EXPECTED_CONTENT_MAX_CHARS = 6000
# Fail the run if more than this fraction of rows produced an LLM/parse error.
# AC #6 says no absolute threshold on scores, but structural validity must
# include "the judge actually ran" — otherwise a fully-broken run passes.
_MAX_ERROR_FRACTION = 0.2


def _load_eval_set() -> list[dict]:
    rows: list[dict] = []
    for line in _EVAL_SET_PATH.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped:
            rows.append(json.loads(stripped))
    return rows


def _load_expected_content(expected_doc_ids: list[str]) -> str:
    parts: list[str] = []
    budget = _EXPECTED_CONTENT_MAX_CHARS
    for doc_id in expected_doc_ids:
        if budget <= 0:
            break
        lang, _, slug = doc_id.partition("/")
        path = _CORPUS_ROOT / lang / f"{slug}.md"
        if path.exists():
            body = path.read_text(encoding="utf-8")
            if len(body) > budget:
                body = body[:budget] + "\n… [truncated]"
            parts.append(f"[{doc_id}]\n{body}")
            budget -= len(body)
    return "\n\n".join(parts) if parts else "(expected content unavailable)"


def _check_corpus_seeded() -> tuple[bool, str]:
    try:
        with get_sync_session() as session:
            count = session.execute(
                text("SELECT COUNT(*) FROM document_embeddings")
            ).scalar_one()
    except Exception as exc:
        return False, f"database unreachable or document_embeddings missing: {exc}"
    if not count:
        return False, "document_embeddings is empty — run `python -m app.rag.seed` first"
    return True, f"document_embeddings rows={count}"


def _aggregate(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


@pytest.mark.integration
@pytest.mark.eval
def test_rag_eval_harness() -> None:
    seeded, reason = _check_corpus_seeded()
    if not seeded:
        pytest.skip(f"RAG corpus not seeded — {reason}")

    rows = _load_eval_set()
    assert rows, "eval_set.jsonl is empty"

    start = time.perf_counter()
    per_question: list[dict] = []
    total_tokens = 0
    error_rows = 0

    for row in rows:
        retrieved = retrieve_relevant_docs(
            query=row["question"],
            language=row["language"],
            top_k=_TOP_K,
        )
        retrieved_ids = [r["doc_id"] for r in retrieved]
        expected_ids = row["expected_doc_ids"]

        metrics = {
            "precision_at_1": precision_at_k(retrieved_ids, expected_ids, 1),
            "precision_at_3": precision_at_k(retrieved_ids, expected_ids, 3),
            "precision_at_5": precision_at_k(retrieved_ids, expected_ids, _TOP_K),
            "recall_at_5": recall_at_k(retrieved_ids, expected_ids, _TOP_K),
            "mrr": reciprocal_rank(retrieved_ids, expected_ids),
        }

        candidate_answer = ""
        candidate_tokens = 0
        judge_tokens = 0
        score = {
            "groundedness": 0,
            "relevance": 0,
            "language_correctness": 0,
            "overall": 0,
            "rationale": "not-scored",
        }
        try:
            candidate_answer, candidate_tokens = judge_module.build_candidate_answer(
                question=row["question"],
                retrieved_chunks=retrieved,
                language=row["language"],
            )
            expected_content = _load_expected_content(expected_ids)
            score, judge_tokens = judge_module.judge_answer(
                question=row["question"],
                candidate_answer=candidate_answer,
                retrieved_chunks=retrieved,
                expected_doc_content=expected_content,
                language=row["language"],
            )
            if str(score.get("rationale", "")).startswith("parse-error"):
                error_rows += 1
        except Exception as exc:
            logger.warning(
                "rag_harness_llm_call_failed",
                extra={"row_id": row["id"], "error": str(exc)},
            )
            score = {
                "groundedness": 0,
                "relevance": 0,
                "language_correctness": 0,
                "overall": 0,
                "rationale": f"llm-error: {exc}",
            }
            error_rows += 1

        total_tokens += candidate_tokens + judge_tokens

        per_question.append({
            "id": row["id"],
            "language": row["language"],
            "topic": row["topic"],
            "question_type": row["question_type"],
            "question": row["question"],
            "expected_doc_ids": expected_ids,
            "retrieved_doc_ids": retrieved_ids,
            "metrics": metrics,
            "candidate_answer": candidate_answer,
            "judge": score,
            "candidate_tokens": candidate_tokens,
            "judge_tokens": judge_tokens,
        })

    elapsed_s = time.perf_counter() - start

    # Aggregates
    metric_keys = ("precision_at_1", "precision_at_3", "precision_at_5", "recall_at_5", "mrr")
    judge_keys = ("groundedness", "relevance", "language_correctness", "overall")

    def _bucket(rows_: list[dict]) -> dict:
        return {
            "count": len(rows_),
            "retrieval": {
                key: _aggregate([r["metrics"][key] for r in rows_])
                for key in metric_keys
            },
            "judge": {
                key: _aggregate([float(r["judge"].get(key, 0)) for r in rows_])
                for key in judge_keys
            },
        }

    by_language: dict[str, list[dict]] = defaultdict(list)
    by_topic: dict[str, list[dict]] = defaultdict(list)
    by_question_type: dict[str, list[dict]] = defaultdict(list)
    for item in per_question:
        by_language[item["language"]].append(item)
        by_topic[item["topic"]].append(item)
        by_question_type[item["question_type"]].append(item)

    worst_10 = sorted(
        per_question,
        key=lambda r: (r["judge"].get("overall", 0), r["id"]),
    )[:10]

    report = {
        "timestamp": datetime.datetime.now(datetime.UTC).isoformat(),
        "story": "9.1",
        "top_k": _TOP_K,
        "elapsed_seconds": elapsed_s,
        "total_tokens_used": total_tokens,
        "total_questions": len(per_question),
        "error_rows": error_rows,
        "overall": _bucket(per_question),
        "per_language": {lang: _bucket(items) for lang, items in sorted(by_language.items())},
        "per_topic": {topic: _bucket(items) for topic, items in sorted(by_topic.items())},
        "per_question_type": {qt: _bucket(items) for qt, items in sorted(by_question_type.items())},
        "worst_10": [
            {
                "id": r["id"],
                "language": r["language"],
                "topic": r["topic"],
                "question": r["question"],
                "expected_doc_ids": r["expected_doc_ids"],
                "retrieved_doc_ids": r["retrieved_doc_ids"],
                "candidate_answer": r["candidate_answer"],
                "judge": r["judge"],
            }
            for r in worst_10
        ],
        "per_question": per_question,
    }

    _RUNS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.datetime.now(datetime.UTC).strftime("%Y%m%dT%H%M%S%fZ")
    report_path = _RUNS_DIR / f"{ts}.json"
    report_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(
        f"\nRAG eval harness: total={len(per_question)} "
        f"errors={error_rows} "
        f"p@1={report['overall']['retrieval']['precision_at_1']:.3f} "
        f"p@5={report['overall']['retrieval']['precision_at_5']:.3f} "
        f"mrr={report['overall']['retrieval']['mrr']:.3f} "
        f"judge_overall={report['overall']['judge']['overall']:.3f} "
        f"tokens={total_tokens} "
        f"elapsed={elapsed_s:.1f}s "
        f"report={report_path}"
    )

    # AC #6 / #5.8: assert structural validity only — no absolute thresholds.
    assert report_path.exists(), f"run report was not written to {report_path}"
    for required_key in (
        "timestamp",
        "total_questions",
        "overall",
        "per_language",
        "per_topic",
        "per_question_type",
        "worst_10",
        "total_tokens_used",
    ):
        assert required_key in report, f"run report missing aggregate key: {required_key}"
    assert len(per_question) == len(rows), "every eval question must produce a per-question entry"
    for item in per_question:
        assert "metrics" in item and set(metric_keys) <= item["metrics"].keys()
        assert "judge" in item and "overall" in item["judge"]
    # AC #6 forbids score thresholds — but we DO assert the judge actually ran.
    # A run where most LLM calls failed would otherwise pass silently.
    error_fraction = error_rows / len(per_question)
    assert error_fraction <= _MAX_ERROR_FRACTION, (
        f"too many LLM/parse errors: {error_rows}/{len(per_question)} "
        f"({error_fraction:.1%}) exceeds {_MAX_ERROR_FRACTION:.0%} budget — "
        "judge never scored most rows; see report for `llm-error:` / `parse-error:` rationales"
    )
