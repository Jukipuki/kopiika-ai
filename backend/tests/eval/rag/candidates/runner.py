"""Story 9.3 candidate-embedding runner.

Responsibilities:

* Create / drop per-candidate ``document_embeddings_cand_<slug>`` sidecar
  tables (vector(<dims>) + HNSW cosine index mirroring the production migration
  parameters ``m=16, ef_construction=64``).
* Chunk the RAG corpus with the same H2-splitter that ``app.rag.seed`` uses;
  the chunker here is a deliberate copy, not a shared import, to keep
  production untouched.
* Embed + upsert corpus chunks into the sidecar table via an ``Embedder``.
* Retrieve top-k chunks from the sidecar with the same SQL shape as
  ``app.rag.retriever.retrieve_relevant_docs`` (language filter + cross-lingual
  fallback when < ``MIN_RESULTS``).
* Run the Story 9.1 harness loop (reusing ``metrics`` + ``judge`` modules
  verbatim), write a timestamped run report under
  ``tests/fixtures/rag_eval/runs/`` and promote it to
  ``tests/fixtures/rag_eval/baselines/<slug>.json`` together with a sibling
  ``<slug>.meta.json`` reproducibility envelope.

A crashed run leaves the sidecar table present; the next invocation's
``_ensure_sidecar_table`` does a ``DROP TABLE IF EXISTS`` before recreating,
so no manual cleanup is needed. Set ``KEEP_CAND_TABLES=1`` to retain the
table after a successful run for post-mortem inspection.

This module intentionally does not depend on ``app.rag.embeddings``,
``app.rag.retriever``, ``app.rag.seed``, or the production Alembic migration.
"""

from __future__ import annotations

import datetime
import json
import logging
import os
import re
import subprocess
import time
import uuid
from collections import defaultdict
from pathlib import Path
from statistics import median
from typing import Any

from sqlalchemy import text

from app.core.database import get_sync_session
from tests.eval.rag import judge as judge_module
from tests.eval.rag.candidates.embedders import Embedder
from tests.eval.rag.metrics import precision_at_k, reciprocal_rank, recall_at_k

logger = logging.getLogger(__name__)

_BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent
_FIXTURE_DIR = _BACKEND_ROOT / "tests" / "fixtures" / "rag_eval"
_EVAL_SET_PATH = _FIXTURE_DIR / "eval_set.jsonl"
_BASELINES_DIR = _FIXTURE_DIR / "baselines"
_RUNS_DIR = _FIXTURE_DIR / "runs"
_CORPUS_ROOT = _BACKEND_ROOT / "data" / "rag-corpus"
_VERSION_PATH = _BACKEND_ROOT.parent / "VERSION"

_TOP_K = 5
_MIN_RESULTS = 3
_EXPECTED_CONTENT_MAX_CHARS = 6000
_MAX_ERROR_FRACTION = 0.2

H2_PATTERN = re.compile(r"^## (.+)$", re.MULTILINE)


# ─── Corpus chunking (copy of app.rag.seed._chunk_document) ────────────────

def _chunk_document(content: str) -> list[tuple[str, str]]:
    matches = list(H2_PATTERN.finditer(content))
    if not matches:
        return [("full_document", content.strip())]

    chunks: list[tuple[str, str]] = []
    preamble = content[: matches[0].start()].strip()
    if preamble:
        chunks.append(("preamble", preamble))
    for i, match in enumerate(matches):
        header = match.group(1).strip()
        chunk_type = header.lower().replace(" ", "_")
        start = match.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
        chunk_content = content[start:end].strip()
        if chunk_content:
            chunks.append((chunk_type, chunk_content))
    return chunks


# ─── Sidecar table management ──────────────────────────────────────────────

# Slugs are interpolated into DDL/DML below (table names cannot be bound
# parameters in PostgreSQL). Restrict the alphabet so a future caller cannot
# smuggle SQL via the slug — we only ever expect ASCII identifiers + a small
# punctuation set that gets normalized.
_SAFE_SLUG_CHARS = re.compile(r"^[A-Za-z0-9_.:-]+$")


def _sidecar_table(slug: str) -> str:
    if not _SAFE_SLUG_CHARS.match(slug):
        raise ValueError(
            f"unsafe candidate slug for SQL identifier: {slug!r} "
            "(allowed: letters, digits, '_', '.', ':', '-')"
        )
    safe = slug.replace("-", "_").replace(".", "_").replace(":", "_")
    return f"document_embeddings_cand_{safe}"


def _vector_type_for_dims(dims: int) -> tuple[str, str]:
    """Return ``(column_type, hnsw_opclass)`` for a candidate's dim count.

    pgvector's HNSW index on the native ``vector`` type is capped at 2000 dims
    (hard limit in upstream). For candidates above that ceiling
    (``text-embedding-3-large`` @ 3072) we fall back to ``halfvec`` (2-byte
    floats, HNSW supported up to 4000 dims). Cosine distance ``<=>`` works on
    both types, so query-side SQL is identical once the query embedding is
    cast to the matching type. See Story 9.3 TD-079 — if 3-large becomes the
    winner, Story 9.6's production migration inherits this constraint.
    """
    if dims > 2000:
        return "halfvec", "halfvec_cosine_ops"
    return "vector", "vector_cosine_ops"


def _ensure_sidecar_table_named(table: str, dims: int) -> str:
    """Drop+recreate a sidecar table by explicit name. Used by diagnostics
    that need a non-canonical table name (e.g. ``rechunk_cohere``) without
    monkey-patching ``_sidecar_table``."""
    if not _SAFE_SLUG_CHARS.match(table.replace("_", "-")):
        raise ValueError(f"unsafe sidecar table name: {table!r}")
    col_type, opclass = _vector_type_for_dims(dims)
    with get_sync_session() as session:
        session.execute(text(f"DROP TABLE IF EXISTS {table} CASCADE"))
        session.execute(text(
            f"""
            CREATE TABLE {table} (
                id UUID PRIMARY KEY,
                doc_id VARCHAR NOT NULL,
                language VARCHAR NOT NULL,
                chunk_type VARCHAR NOT NULL,
                content TEXT NOT NULL,
                embedding {col_type}({dims}) NOT NULL,
                created_at TIMESTAMP NOT NULL,
                CONSTRAINT uq_{table}_doc_chunk UNIQUE (doc_id, chunk_type)
            )
            """
        ))
        session.execute(text(f"CREATE INDEX ix_{table}_doc_id ON {table} (doc_id)"))
        session.execute(text(f"CREATE INDEX ix_{table}_language ON {table} (language)"))
        session.execute(text(
            f"CREATE INDEX ix_{table}_hnsw ON {table} "
            f"USING hnsw (embedding {opclass}) WITH (m = 16, ef_construction = 64)"
        ))
        session.commit()
    return table


def _drop_sidecar_table_named(table: str) -> None:
    if os.getenv("KEEP_CAND_TABLES") == "1":
        logger.info("KEEP_CAND_TABLES=1 set — retaining sidecar table=%s", table)
        return
    if not _SAFE_SLUG_CHARS.match(table.replace("_", "-")):
        raise ValueError(f"unsafe sidecar table name: {table!r}")
    with get_sync_session() as session:
        session.execute(text(f"DROP TABLE IF EXISTS {table} CASCADE"))
        session.commit()


def _ensure_sidecar_table(slug: str, dims: int) -> str:
    return _ensure_sidecar_table_named(_sidecar_table(slug), dims)


def _drop_sidecar_table(slug: str) -> None:
    _drop_sidecar_table_named(_sidecar_table(slug))


# ─── Seeding ───────────────────────────────────────────────────────────────

def _seed_candidate(
    embedder: Embedder,
    table: str,
    *,
    chunker: "callable" = _chunk_document,  # noqa: UP037 — quote keeps Embedder Protocol untouched
) -> tuple[int, float]:
    """Embed corpus chunks + upsert into the sidecar table.

    ``chunker`` defaults to the production-equivalent H2 splitter; diagnostic
    callers (e.g. ``rechunk_cohere``) can pass an alternative chunker without
    monkey-patching module globals.

    Returns ``(total_chunks, elapsed_seconds)``.
    """
    total_chunks = 0
    t0 = time.perf_counter()
    col_type, _ = _vector_type_for_dims(embedder.dims)

    for lang in ("en", "uk"):
        lang_dir = _CORPUS_ROOT / lang
        if not lang_dir.exists():
            continue
        md_files = sorted(lang_dir.glob("*.md"))
        for md_file in md_files:
            content = md_file.read_text(encoding="utf-8")
            doc_id = f"{lang}/{md_file.stem}"
            chunks = chunker(content)
            if not chunks:
                continue
            chunk_texts = [cc for _, cc in chunks]
            embeddings = embedder.embed_documents(chunk_texts)
            assert len(embeddings) == len(chunks)

            with get_sync_session() as session:
                for (chunk_type, chunk_content), embedding in zip(chunks, embeddings):
                    emb_literal = "[" + ",".join(str(v) for v in embedding) + "]"
                    session.execute(
                        text(
                            f"""
                            INSERT INTO {table}
                                (id, doc_id, language, chunk_type, content, embedding, created_at)
                            VALUES
                                (:id, :doc_id, :language, :chunk_type, :content,
                                 CAST(:embedding AS {col_type}), NOW())
                            ON CONFLICT (doc_id, chunk_type) DO UPDATE SET
                                content = EXCLUDED.content,
                                embedding = EXCLUDED.embedding,
                                created_at = NOW()
                            """
                        ),
                        {
                            "id": str(uuid.uuid4()),
                            "doc_id": doc_id,
                            "language": lang,
                            "chunk_type": chunk_type,
                            "content": chunk_content,
                            "embedding": emb_literal,
                        },
                    )
                session.commit()
            total_chunks += len(chunks)

    return total_chunks, time.perf_counter() - t0


# ─── Retrieval ─────────────────────────────────────────────────────────────

def _retrieve_from_candidate(embedder: Embedder, table: str, query: str, language: str, top_k: int = _TOP_K) -> list[dict]:
    query_embedding = embedder.embed_query(query)
    embedding_literal = "[" + ",".join(str(v) for v in query_embedding) + "]"
    col_type, _ = _vector_type_for_dims(embedder.dims)

    with get_sync_session() as session:
        rows = session.execute(
            text(
                f"""
                SELECT doc_id, language, chunk_type, content,
                       1 - (embedding <=> CAST(:embedding AS {col_type})) AS similarity
                FROM {table}
                WHERE language = :language
                ORDER BY embedding <=> CAST(:embedding AS {col_type})
                LIMIT :top_k
                """
            ),
            {"embedding": embedding_literal, "language": language, "top_k": top_k},
        ).fetchall()

        results = [
            {
                "doc_id": r.doc_id,
                "language": r.language,
                "chunk_type": r.chunk_type,
                "content": r.content,
                "similarity": float(r.similarity),
            }
            for r in rows
        ]

        if len(results) < _MIN_RESULTS:
            remaining = top_k - len(results)
            existing_ids = {(r["doc_id"], r["chunk_type"]) for r in results}
            cross_rows = session.execute(
                text(
                    f"""
                    SELECT doc_id, language, chunk_type, content,
                           1 - (embedding <=> CAST(:embedding AS {col_type})) AS similarity
                    FROM {table}
                    WHERE language != :language
                    ORDER BY embedding <=> CAST(:embedding AS {col_type})
                    LIMIT :limit
                    """
                ),
                {"embedding": embedding_literal, "language": language, "limit": remaining + 5},
            ).fetchall()
            for r in cross_rows:
                if len(results) >= top_k:
                    break
                if (r.doc_id, r.chunk_type) not in existing_ids:
                    results.append(
                        {
                            "doc_id": r.doc_id,
                            "language": r.language,
                            "chunk_type": r.chunk_type,
                            "content": r.content,
                            "similarity": float(r.similarity),
                        }
                    )
    return results


# ─── Latency sampling ──────────────────────────────────────────────────────

def _measure_embed_latency_ms(latencies_ms: list[float]) -> dict[str, int]:
    """Compute p50 + p95 over recorded ``embed_query`` latencies (in ms)."""
    if not latencies_ms:
        return {"p50": 0, "p95": 0}
    sorted_vals = sorted(latencies_ms)
    p50 = median(sorted_vals)
    idx95 = max(0, min(len(sorted_vals) - 1, int(round(0.95 * (len(sorted_vals) - 1)))))
    p95 = sorted_vals[idx95]
    return {"p50": int(round(p50)), "p95": int(round(p95))}


# ─── Eval set / harness plumbing ───────────────────────────────────────────

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


def _aggregate(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _git_rev_parse_head() -> str:
    out = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=str(_BACKEND_ROOT))
    return out.decode().strip()


def _read_version() -> str:
    return _VERSION_PATH.read_text(encoding="utf-8").strip()


def _count_corpus_files(lang: str) -> int:
    return len(list((_CORPUS_ROOT / lang).glob("*.md")))


def _load_baseline_meta() -> dict:
    path = _BASELINES_DIR / "text-embedding-3-small.meta.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _load_baseline_report() -> dict:
    path = _BASELINES_DIR / "text-embedding-3-small.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _baseline_perfect_row_ids() -> list[str]:
    """Row IDs where the 9.2 baseline reports ``p@1 == p@3 == 1.0``.

    Per AC #7a, this "31 currently-perfect rows" set must retain ``p@1 == 1.0``
    on a candidate run; otherwise the candidate is disqualified for regression.
    """
    baseline = _load_baseline_report()
    rows = baseline.get("per_question", [])
    return [
        r["id"]
        for r in rows
        if float(r.get("metrics", {}).get("precision_at_1", 0)) == 1.0
        and float(r.get("metrics", {}).get("precision_at_3", 0)) == 1.0
    ]


# ─── Run orchestration ─────────────────────────────────────────────────────

def _bucket(rows: list[dict], metric_keys: tuple[str, ...], judge_keys: tuple[str, ...]) -> dict:
    return {
        "count": len(rows),
        "retrieval": {key: _aggregate([r["metrics"][key] for r in rows]) for key in metric_keys},
        "judge": {key: _aggregate([float(r["judge"].get(key, 0)) for r in rows]) for key in judge_keys},
    }


def _assert_llm_config_matches_baseline(baseline_meta: dict) -> None:
    """AC #4 enforcement: the candidate+judge LLM stack MUST match 9.2.

    The spike holds the LLM path constant across all four candidates to
    isolate the embedding variable from judge noise. The judge module also
    calls ``get_llm_client()`` (see ``tests/eval/rag/judge.py:112,166``), so
    a single client check suffices — but we verify the model matches BOTH
    pinned fields (``llm_candidate_model`` and ``llm_judge_model``) and that
    the 9.2 baseline itself agrees the two are identical, so a future split
    of candidate/judge clients would re-trigger this guard rather than pass
    silently. Any drift → fail loud.
    """
    from app.agents.llm import get_llm_client

    llm = get_llm_client()
    actual_model = getattr(llm, "model", None) or getattr(llm, "model_name", None)
    expected_cand = baseline_meta["llm_candidate_model"]
    expected_judge = baseline_meta["llm_judge_model"]

    if expected_cand != expected_judge:
        raise RuntimeError(
            f"AC #4 violation: Story 9.2 baseline pins llm_candidate_model="
            f"'{expected_cand}' but llm_judge_model='{expected_judge}'. The "
            "9.3 candidate runner assumes both share a single get_llm_client() "
            "invocation; split-stack baselines need an explicit judge-client "
            "verification path that does not yet exist here."
        )
    if actual_model != expected_cand:
        raise RuntimeError(
            f"AC #4 violation: llm.get_llm_client() returned model='{actual_model}' "
            f"but Story 9.2 baseline pinned llm_candidate_model/llm_judge_model="
            f"'{expected_cand}'. Re-align the LLM stack or re-run the baseline."
        )


def run_candidate(
    embedder: Embedder,
    *,
    bedrock_region: str | None = None,
    selection_notes: str = "",
) -> tuple[Path, Path]:
    """Run the harness against ``embedder`` and write its baseline + meta files.

    Returns ``(baseline_json_path, baseline_meta_path)``.
    """
    slug = embedder.name
    baseline_meta = _load_baseline_meta()
    _assert_llm_config_matches_baseline(baseline_meta)

    table = _ensure_sidecar_table(slug, embedder.dims)
    try:
        seed_chunks, seed_elapsed = _seed_candidate(embedder, table)

        rows = _load_eval_set()
        assert rows, "eval_set.jsonl is empty"
        metric_keys = ("precision_at_1", "precision_at_3", "precision_at_5", "recall_at_5", "mrr")
        judge_keys = ("groundedness", "relevance", "language_correctness", "overall")

        start = time.perf_counter()
        per_question: list[dict] = []
        total_llm_tokens = 0
        error_rows = 0
        print(f"[{slug}] seed_done chunks={seed_chunks} elapsed={seed_elapsed:.1f}s — starting {len(rows)}-row eval loop", flush=True)
        for i, row in enumerate(rows, start=1):
            t_row = time.perf_counter()
            retrieved = _retrieve_from_candidate(embedder, table, row["question"], row["language"], top_k=_TOP_K)
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
            score: dict[str, Any] = {
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
            except Exception as exc:  # noqa: BLE001 — mirror 9.1 behaviour
                logger.warning("rag_candidate_llm_call_failed id=%s error=%s", row["id"], exc)
                score = {
                    "groundedness": 0,
                    "relevance": 0,
                    "language_correctness": 0,
                    "overall": 0,
                    "rationale": f"llm-error: {exc}",
                }
                error_rows += 1

            total_llm_tokens += candidate_tokens + judge_tokens
            row_elapsed = time.perf_counter() - t_row
            print(
                f"[{slug}] {i:>2}/{len(rows)} id={row['id']} lang={row['language']} "
                f"p@5={metrics['precision_at_5']:.2f} judge={score.get('overall', 0)} "
                f"t={row_elapsed:.1f}s cand_tok={candidate_tokens} judge_tok={judge_tokens}",
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

        by_language: dict[str, list[dict]] = defaultdict(list)
        by_topic: dict[str, list[dict]] = defaultdict(list)
        by_qt: dict[str, list[dict]] = defaultdict(list)
        for item in per_question:
            by_language[item["language"]].append(item)
            by_topic[item["topic"]].append(item)
            by_qt[item["question_type"]].append(item)

        worst_10 = sorted(per_question, key=lambda r: (r["judge"].get("overall", 0), r["id"]))[:10]

        ts = datetime.datetime.now(datetime.UTC).strftime("%Y%m%dT%H%M%S%fZ")
        timestamp = datetime.datetime.now(datetime.UTC).isoformat()
        report = {
            "timestamp": timestamp,
            "story": "9.3",
            "candidate_slug": slug,
            "top_k": _TOP_K,
            "elapsed_seconds": elapsed_s,
            "total_tokens_used": total_llm_tokens,
            "total_questions": len(per_question),
            "total_rows": len(per_question),
            "error_rows": error_rows,
            "overall": _bucket(per_question, metric_keys, judge_keys),
            "per_language": {k: _bucket(v, metric_keys, judge_keys) for k, v in sorted(by_language.items())},
            "per_topic": {k: _bucket(v, metric_keys, judge_keys) for k, v in sorted(by_topic.items())},
            "per_question_type": {k: _bucket(v, metric_keys, judge_keys) for k, v in sorted(by_qt.items())},
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
        run_path = _RUNS_DIR / f"{ts}_cand_{slug}.json"
        run_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

        # Structural validity gate (same as harness).
        error_fraction = error_rows / max(1, len(per_question))
        if error_fraction > _MAX_ERROR_FRACTION:
            raise RuntimeError(
                f"too many LLM/parse errors: {error_rows}/{len(per_question)} "
                f"({error_fraction:.1%}) exceeds {_MAX_ERROR_FRACTION:.0%} budget"
            )

        # Promote to baseline (copy-not-move). Guard: refuse to clobber a
        # frozen baseline owned by an earlier story (e.g. 9.2's
        # text-embedding-3-small.{json,meta.json}); use a sibling slug like
        # "<slug>.9-3-rerun" or set OVERWRITE_FROZEN=1 to override.
        _BASELINES_DIR.mkdir(parents=True, exist_ok=True)
        baseline_path = _BASELINES_DIR / f"{slug}.json"
        existing_meta_path = _BASELINES_DIR / f"{slug}.meta.json"
        if existing_meta_path.exists() and os.getenv("OVERWRITE_FROZEN") != "1":
            existing_story = json.loads(existing_meta_path.read_text(encoding="utf-8")).get("baseline_story")
            if existing_story and existing_story != "9.3":
                raise RuntimeError(
                    f"refusing to overwrite frozen baseline {existing_meta_path.name} "
                    f"(baseline_story='{existing_story}'); pick a sibling slug "
                    f"(e.g. '{slug}.9-3-rerun') or set OVERWRITE_FROZEN=1 to override."
                )
        baseline_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

        # Shortlist + regression row diff (AC #7a).
        per_q_by_id = {r["id"]: r for r in per_question}
        shortlist_ids = ("rag-041", "rag-027")
        shortlist: dict[str, dict] = {}
        for sid in shortlist_ids:
            entry = per_q_by_id.get(sid)
            if entry is None:
                shortlist[sid] = {"gold_in_top5": False, "gold_rank": None, "note": "row missing"}
                continue
            retrieved_ids = entry["retrieved_doc_ids"]
            expected_ids = entry["expected_doc_ids"]
            gold_rank: int | None = None
            for idx, did in enumerate(retrieved_ids[:_TOP_K], start=1):
                if did in expected_ids:
                    gold_rank = idx
                    break
            shortlist[sid] = {
                "gold_in_top5": gold_rank is not None,
                "gold_rank": gold_rank,
                "retrieved_top5": retrieved_ids[:_TOP_K],
                "expected_doc_ids": expected_ids,
            }

        regression_rows: list[str] = []
        perfect_ids = _baseline_perfect_row_ids()
        for rid in perfect_ids:
            entry = per_q_by_id.get(rid)
            if entry is None:
                regression_rows.append(rid)
                continue
            if float(entry["metrics"].get("precision_at_1", 0)) < 1.0:
                regression_rows.append(rid)

        # Embed cost + latency
        query_latencies = list(embedder.usage.query_latencies_ms)
        embed_latency = _measure_embed_latency_ms(query_latencies)

        meta = {
            "embedding_model": embedder.model_id,
            "embedding_dims": embedder.dims,
            "embedding_provider": embedder.provider,
            "candidate_of": "9.3",
            "candidate_slug": slug,
            "llm_candidate_provider": baseline_meta["llm_candidate_provider"],
            "llm_candidate_model": baseline_meta["llm_candidate_model"],
            "llm_judge_provider": baseline_meta["llm_judge_provider"],
            "llm_judge_model": baseline_meta["llm_judge_model"],
            "llm_fallback_provider": baseline_meta["llm_fallback_provider"],
            "llm_fallback_model": baseline_meta["llm_fallback_model"],
            "corpus_git_sha": _git_rev_parse_head(),
            "corpus_file_count_en": _count_corpus_files("en"),
            "corpus_file_count_uk": _count_corpus_files("uk"),
            "document_embeddings_row_count": seed_chunks,
            "seed_elapsed_seconds": seed_elapsed,
            "embed_calls": embedder.usage.calls,
            "embed_input_tokens": embedder.usage.input_tokens,
            "embed_input_tokens_approximated": embedder.usage.input_tokens_approximated,
            "embed_latency_ms_p50": embed_latency["p50"],
            "embed_latency_ms_p95": embed_latency["p95"],
            "harness_version": _read_version(),
            "run_timestamp_utc": timestamp,
            "total_rows": len(per_question),
            "total_questions": len(per_question),
            "error_rows": error_rows,
            "total_tokens_used": total_llm_tokens,
            "elapsed_seconds": elapsed_s,
            "run_report_filename": run_path.name,
            "baseline_story": "9.3",
            "captured_by": "Story 9.3 — Embedding Model Comparison Spike",
            "selection_notes": selection_notes,
            "shortlist": shortlist,
            "regression_rows": regression_rows,
        }
        if bedrock_region is not None:
            meta["bedrock_region"] = bedrock_region

        meta_path = _BASELINES_DIR / f"{slug}.meta.json"
        meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")

        logger.info(
            "candidate=%s p@5=%.3f uk_p@5=%.3f en_p@5=%.3f judge_overall=%.3f regression_rows=%d shortlist=%s",
            slug,
            report["overall"]["retrieval"]["precision_at_5"],
            report["per_language"].get("uk", {}).get("retrieval", {}).get("precision_at_5", 0.0),
            report["per_language"].get("en", {}).get("retrieval", {}).get("precision_at_5", 0.0),
            report["overall"]["judge"]["overall"],
            len(regression_rows),
            {k: v.get("gold_rank") for k, v in shortlist.items()},
        )

        return baseline_path, meta_path
    finally:
        _drop_sidecar_table(slug)
