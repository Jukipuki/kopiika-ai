"""Story 9.3 candidate-harness pytest entry point.

Marker-gated behind ``@pytest.mark.eval`` (plus ``integration``) so the
default sweep never collects these tests. Invoke explicitly:

    cd backend
    uv run pytest tests/eval/rag/candidates/ -v -m eval

The candidate slug is passed via ``CANDIDATE_SLUG`` env var (one at a time —
each run is expensive and the matrix is orchestrated manually). Optional
``BEDROCK_REGION`` override (default ``eu-central-1``).
"""

from __future__ import annotations

import os

import pytest
from sqlalchemy import text

from app.core.database import get_sync_session
from tests.eval.rag.candidates.embedders import build_embedder
from tests.eval.rag.candidates.runner import run_candidate


def _check_corpus_seeded() -> tuple[bool, str]:
    try:
        with get_sync_session() as session:
            count = session.execute(
                text("SELECT COUNT(*) FROM document_embeddings")
            ).scalar_one()
    except Exception as exc:  # noqa: BLE001
        return False, f"database unreachable: {exc}"
    if not count:
        return False, "document_embeddings empty — production seed required"
    return True, f"rows={count}"


@pytest.mark.integration
@pytest.mark.eval
def test_run_candidate_from_env() -> None:
    slug = os.getenv("CANDIDATE_SLUG")
    if not slug:
        pytest.skip("CANDIDATE_SLUG env var not set")

    seeded, reason = _check_corpus_seeded()
    if not seeded:
        pytest.skip(f"precondition not met — {reason}")

    region = os.getenv("BEDROCK_REGION", "eu-central-1")
    notes = os.getenv("CANDIDATE_SELECTION_NOTES", "")

    embedder = build_embedder(slug, region=region)
    is_bedrock = embedder.provider in ("Amazon", "Cohere")
    baseline_path, meta_path = run_candidate(
        embedder,
        bedrock_region=region if is_bedrock else None,
        selection_notes=notes,
    )

    assert baseline_path.exists()
    assert meta_path.exists()
