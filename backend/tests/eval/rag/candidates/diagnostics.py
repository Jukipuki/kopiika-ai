"""Story 9.3 post-decision diagnostics (2026-04-23 follow-up).

Two checks to pressure-test the "stay on 3-small" verdict:

* ``run_separation_ratio`` — for each candidate, embed every corpus chunk
  and compute mean intra-topic vs inter-topic cosine similarity, per
  language and overall. Higher ratio = better topic discrimination in the
  embedding space, independent of eval-set phrasing. If 3-large's ratio is
  materially higher than 3-small's, that's evidence the retrieval gain is a
  real quality win, not an eval-set artefact.

* ``run_rechunk_cohere`` — re-embed + re-harness Cohere with whole-document
  chunks instead of H2 chunks, to probe Hypothesis 3 (Cohere underperforms
  with our current chunk size). Writes a second-report artefact suffixed
  ``-wholedoc`` so the original baseline is preserved.

Invoked directly (not via pytest); writes JSON artefacts under
``backend/tests/fixtures/rag_eval/diagnostics/``.
"""

from __future__ import annotations

import datetime
import json
import logging
import math
import time
from pathlib import Path
from statistics import mean

from tests.eval.rag.candidates.embedders import Embedder, build_embedder
from tests.eval.rag.candidates.runner import (
    _CORPUS_ROOT,
    _chunk_document,
)

logger = logging.getLogger(__name__)

_FIXTURE_DIR = Path(__file__).resolve().parent.parent.parent.parent / "fixtures" / "rag_eval"
_DIAG_DIR = _FIXTURE_DIR / "diagnostics"


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


def _collect_corpus_chunks() -> list[tuple[str, str, str]]:
    """Return ``[(doc_id, lang, chunk_text), ...]`` for the whole corpus."""
    out: list[tuple[str, str, str]] = []
    for lang in ("en", "uk"):
        for md in sorted((_CORPUS_ROOT / lang).glob("*.md")):
            doc_id = f"{lang}/{md.stem}"
            content = md.read_text(encoding="utf-8")
            for _chunk_type, chunk_text in _chunk_document(content):
                out.append((doc_id, lang, chunk_text))
    return out


def _separation_ratio_for_embedder(embedder: Embedder) -> dict:
    """Embed every corpus chunk once and compute intra/inter topic cos-sim.

    Intra-topic pairs: chunks sharing the same ``doc_id`` (same gold doc).
    Inter-topic pairs: chunks from different ``doc_id``s **within the same
    language** (cross-language cos-sim is excluded — it's not what production
    retrieval does and it would mask the per-language discrimination we care
    about).
    """
    chunks = _collect_corpus_chunks()
    logger.info("separation_ratio slug=%s chunks=%d", embedder.name, len(chunks))
    texts = [c[2] for c in chunks]

    t0 = time.perf_counter()
    vectors = embedder.embed_documents(texts)
    embed_elapsed = time.perf_counter() - t0

    per_lang: dict[str, dict] = {}
    for target_lang in ("en", "uk"):
        intra: list[float] = []
        inter: list[float] = []
        # Only pairs within `target_lang`, unordered (i < j).
        lang_indices = [i for i, c in enumerate(chunks) if c[1] == target_lang]
        for a_pos, i in enumerate(lang_indices):
            doc_i = chunks[i][0]
            for j in lang_indices[a_pos + 1 :]:
                doc_j = chunks[j][0]
                sim = _cosine(vectors[i], vectors[j])
                (intra if doc_i == doc_j else inter).append(sim)
        intra_mean = mean(intra) if intra else 0.0
        inter_mean = mean(inter) if inter else 0.0
        ratio = intra_mean / inter_mean if inter_mean else 0.0
        per_lang[target_lang] = {
            "intra_pairs": len(intra),
            "inter_pairs": len(inter),
            "intra_mean_cos": round(intra_mean, 4),
            "inter_mean_cos": round(inter_mean, 4),
            "separation_ratio": round(ratio, 4),
        }

    # Pooled across languages but only within-language pairs counted (retrieval
    # is language-filtered in production, so cross-lingual pairs don't matter).
    intra_g_pairs: list[float] = []
    inter_g_pairs: list[float] = []
    for target_lang in ("en", "uk"):
        lang_indices = [i for i, c in enumerate(chunks) if c[1] == target_lang]
        for a_pos, i in enumerate(lang_indices):
            doc_i = chunks[i][0]
            for j in lang_indices[a_pos + 1 :]:
                doc_j = chunks[j][0]
                sim = _cosine(vectors[i], vectors[j])
                (intra_g_pairs if doc_i == doc_j else inter_g_pairs).append(sim)

    overall = {
        "intra_pairs": len(intra_g_pairs),
        "inter_pairs": len(inter_g_pairs),
        "intra_mean_cos": round(mean(intra_g_pairs) if intra_g_pairs else 0.0, 4),
        "inter_mean_cos": round(mean(inter_g_pairs) if inter_g_pairs else 0.0, 4),
        "separation_ratio": round(
            (mean(intra_g_pairs) / mean(inter_g_pairs)) if (intra_g_pairs and inter_g_pairs and mean(inter_g_pairs)) else 0.0, 4
        ),
    }

    return {
        "slug": embedder.name,
        "provider": embedder.provider,
        "model_id": embedder.model_id,
        "dims": embedder.dims,
        "chunks": len(chunks),
        "embed_elapsed_seconds": round(embed_elapsed, 2),
        "per_language": per_lang,
        "overall_per_language_pooled": overall,
    }


def run_separation_ratio_all() -> Path:
    """Run separation-ratio diagnostic for all four candidates and write a report."""
    slugs = [
        "text-embedding-3-small",
        "text-embedding-3-large",
        "titan-text-embeddings-v2",
        "cohere-embed-multilingual-v3",
    ]
    results = []
    for slug in slugs:
        embedder = build_embedder(slug)
        results.append(_separation_ratio_for_embedder(embedder))

    _DIAG_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.datetime.now(datetime.UTC).strftime("%Y%m%dT%H%M%S%fZ")
    path = _DIAG_DIR / f"{ts}-separation-ratio.json"
    path.write_text(
        json.dumps(
            {
                "timestamp": datetime.datetime.now(datetime.UTC).isoformat(),
                "story": "9.3-diagnostic",
                "purpose": (
                    "Topic-discrimination sanity check — intra/inter topic cosine "
                    "similarity per language. Independent of eval_set phrasing."
                ),
                "methodology": (
                    "For each candidate, embed every corpus chunk once. Intra-topic = "
                    "pairs with matching doc_id. Inter-topic = pairs with different "
                    "doc_id, same language. separation_ratio = intra_mean / inter_mean. "
                    "Higher = better topic cluster separation."
                ),
                "candidates": results,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    # Terminal summary
    print("\nSeparation ratio (higher = better topic cluster separation):")
    print(f"{'candidate':<38} {'en intra':>9} {'en inter':>9} {'en_ratio':>9} {'uk intra':>9} {'uk inter':>9} {'uk_ratio':>9}")
    for r in results:
        en, uk = r["per_language"]["en"], r["per_language"]["uk"]
        print(
            f"{r['slug']:<38} "
            f"{en['intra_mean_cos']:>9.4f} {en['inter_mean_cos']:>9.4f} {en['separation_ratio']:>9.4f} "
            f"{uk['intra_mean_cos']:>9.4f} {uk['inter_mean_cos']:>9.4f} {uk['separation_ratio']:>9.4f}"
        )

    print(f"\nReport: {path}")
    return path
