"""Re-run Cohere embed-multilingual-v3 with merged-H2 chunks.

Probes Hypothesis 3 from the 2026-04-23 Story 9.3 post-decision critique:
Cohere may underperform with H2-granularity chunks; it's documented to
prefer longer context per chunk. This runner overrides the chunker to
coalesce adjacent H2 sections (up to 1800 chars — Bedrock Cohere caps at
2048-char input, so whole-document was infeasible) and otherwise mirrors
the Story 9.3 runner end-to-end so the 46-question harness numbers are
comparable.

Artefacts land under ``tests/fixtures/rag_eval/diagnostics/`` with a
``-cohere-wholedoc`` suffix so the original Cohere baseline is preserved.
Does NOT update the committed baseline files or the sprint-status — this
is a diagnostic, not a decision reopen.
"""

from __future__ import annotations

import datetime
import json
import time
from collections import defaultdict
from pathlib import Path

from tests.eval.rag import judge as judge_module
from tests.eval.rag.candidates import runner as _runner_mod
from tests.eval.rag.candidates.embedders import build_embedder
from tests.eval.rag.metrics import precision_at_k, reciprocal_rank, recall_at_k


_DIAG_DIR = _runner_mod._FIXTURE_DIR / "diagnostics"
_COHERE_MAX_CHARS = 1800  # Bedrock Cohere caps per-text input at 2048 chars; leave headroom.
_RECHUNK_TABLE = "document_embeddings_cand_cohere_wholedoc"


def _merged_h2_chunker(content: str) -> list[tuple[str, str]]:
    """Coalesce adjacent H2 chunks until each merged chunk approaches 1800 chars.

    Tests "Cohere prefers more context per chunk" without overflowing the
    Bedrock 2048-char input limit that whole-document chunking would hit.
    Falls back to a single-chunk emit if no H2 headers exist.
    """
    pieces = _runner_mod._chunk_document(content)
    merged: list[tuple[str, str]] = []
    buf_type: str | None = None
    buf_text = ""
    for ct, ctext in pieces:
        ctext = ctext[:_COHERE_MAX_CHARS]
        if not buf_text:
            buf_type = ct
            buf_text = ctext
            continue
        if len(buf_text) + 2 + len(ctext) <= _COHERE_MAX_CHARS:
            buf_text = f"{buf_text}\n\n{ctext}"
        else:
            merged.append((buf_type or "merged", buf_text))
            buf_type = ct
            buf_text = ctext
    if buf_text:
        merged.append((buf_type or "merged", buf_text))
    return merged


def run_cohere_wholedoc() -> Path:
    slug = "cohere-embed-multilingual-v3"
    embedder = build_embedder(slug, region="eu-central-1")

    baseline_meta = _runner_mod._load_baseline_meta()
    _runner_mod._assert_llm_config_matches_baseline(baseline_meta)

    _runner_mod._ensure_sidecar_table_named(_RECHUNK_TABLE, embedder.dims)
    try:
        seed_chunks, seed_elapsed = _runner_mod._seed_candidate(
            embedder, _RECHUNK_TABLE, chunker=_merged_h2_chunker
        )
        print(f"[cohere-wholedoc] seed_done chunks={seed_chunks} elapsed={seed_elapsed:.1f}s", flush=True)

        rows = _runner_mod._load_eval_set()
        metric_keys = ("precision_at_1", "precision_at_3", "precision_at_5", "recall_at_5", "mrr")
        judge_keys = ("groundedness", "relevance", "language_correctness", "overall")

        start = time.perf_counter()
        per_question: list[dict] = []
        total_llm_tokens = 0
        error_rows = 0
        for i, row in enumerate(rows, start=1):
            t0 = time.perf_counter()
            retrieved = _runner_mod._retrieve_from_candidate(
                embedder, _RECHUNK_TABLE, row["question"], row["language"], top_k=_runner_mod._TOP_K
            )
            retrieved_ids = [r["doc_id"] for r in retrieved]
            expected_ids = row["expected_doc_ids"]
            metrics = {
                "precision_at_1": precision_at_k(retrieved_ids, expected_ids, 1),
                "precision_at_3": precision_at_k(retrieved_ids, expected_ids, 3),
                "precision_at_5": precision_at_k(retrieved_ids, expected_ids, _runner_mod._TOP_K),
                "recall_at_5": recall_at_k(retrieved_ids, expected_ids, _runner_mod._TOP_K),
                "mrr": reciprocal_rank(retrieved_ids, expected_ids),
            }
            candidate_answer = ""
            candidate_tokens = 0
            judge_tokens = 0
            score = {"groundedness": 0, "relevance": 0, "language_correctness": 0, "overall": 0, "rationale": "not-scored"}
            try:
                candidate_answer, candidate_tokens = judge_module.build_candidate_answer(
                    row["question"], retrieved, row["language"]
                )
                expected_content = _runner_mod._load_expected_content(expected_ids)
                score, judge_tokens = judge_module.judge_answer(
                    row["question"], candidate_answer, retrieved, expected_content, row["language"]
                )
                if str(score.get("rationale", "")).startswith("parse-error"):
                    error_rows += 1
            except Exception as exc:  # noqa: BLE001
                score = {"groundedness": 0, "relevance": 0, "language_correctness": 0, "overall": 0, "rationale": f"llm-error: {exc}"}
                error_rows += 1

            total_llm_tokens += candidate_tokens + judge_tokens
            elapsed = time.perf_counter() - t0
            print(
                f"[cohere-wholedoc] {i:>2}/{len(rows)} id={row['id']} lang={row['language']} "
                f"p@5={metrics['precision_at_5']:.2f} judge={score.get('overall', 0)} t={elapsed:.1f}s",
                flush=True,
            )
            per_question.append(
                {
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
                }
            )

        elapsed_s = time.perf_counter() - start

        def _agg(vs: list[float]) -> float:
            return sum(vs) / len(vs) if vs else 0.0

        def _bucket(items: list[dict]) -> dict:
            return {
                "count": len(items),
                "retrieval": {k: _agg([r["metrics"][k] for r in items]) for k in metric_keys},
                "judge": {k: _agg([float(r["judge"].get(k, 0)) for r in items]) for k in judge_keys},
            }

        by_lang: dict[str, list[dict]] = defaultdict(list)
        for it in per_question:
            by_lang[it["language"]].append(it)

        report = {
            "timestamp": datetime.datetime.now(datetime.UTC).isoformat(),
            "story": "9.3-diagnostic-rechunk",
            "candidate_slug": slug,
            "chunker": f"merged_h2_up_to_{_COHERE_MAX_CHARS}_chars",
            "top_k": _runner_mod._TOP_K,
            "elapsed_seconds": elapsed_s,
            "total_tokens_used": total_llm_tokens,
            "total_questions": len(per_question),
            "error_rows": error_rows,
            "overall": _bucket(per_question),
            "per_language": {k: _bucket(v) for k, v in sorted(by_lang.items())},
            "per_question": per_question,
        }

        _DIAG_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.datetime.now(datetime.UTC).strftime("%Y%m%dT%H%M%S%fZ")
        out_path = _DIAG_DIR / f"{ts}-cohere-wholedoc.json"
        out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

        o = report["overall"]
        en = report["per_language"].get("en", {}).get("retrieval", {})
        uk = report["per_language"].get("uk", {}).get("retrieval", {})
        print(
            f"\n[cohere-wholedoc] p@5={o['retrieval']['precision_at_5']:.3f} "
            f"mrr={o['retrieval']['mrr']:.3f} judge={o['judge']['overall']:.3f} | "
            f"en_p@5={en.get('precision_at_5', 0):.3f} uk_p@5={uk.get('precision_at_5', 0):.3f}"
        )
        print(f"Report: {out_path}")
        return out_path
    finally:
        _runner_mod._drop_sidecar_table_named(_RECHUNK_TABLE)
