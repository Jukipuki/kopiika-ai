# Read-only — MUST NOT mutate. Any INSERT/UPDATE/DELETE introduction breaks the Epic 10 no-write-tools invariant.
"""``search_financial_corpus`` — RAG lookup against the shared corpus.

Story 10.4c. The financial-literacy corpus is shared across users; this
tool is safe to scope-widen because it exposes NO user data. The
``user_id`` parameter is still threaded through the handler signature so
the dispatcher contract is uniform, but it is NOT passed to
``retrieve_relevant_docs``. Do NOT relax the pattern for any other tool.
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Optional

from pydantic import BaseModel, Field
from sqlmodel.ext.asyncio.session import AsyncSession as SQLModelAsyncSession

from app.rag.retriever import retrieve_relevant_docs

_DEFAULT_LANGUAGE = (
    "en"  # Chat is English-first; UA cards still retrieve via cross-lingual fallback.
)
_SNIPPET_MAX_CHARS = 500


class SearchFinancialCorpusInput(BaseModel):
    query: str = Field(min_length=1, max_length=500)
    top_k: int = Field(default=5, ge=1, le=10)


class CorpusDocRow(BaseModel):
    source_id: str
    snippet: str
    similarity: float
    # Intentionally no ``title`` — the retriever's global corpus carries
    # only ``doc_id``; duplicating doc_id as ``title`` was misleading and
    # gave the model nothing to cite with. Story 10.6b's citation assembler
    # should surface ``source_id`` directly (or join to a doc-title index
    # if/when one exists).


class SearchFinancialCorpusOutput(BaseModel):
    rows: list[CorpusDocRow]
    row_count: int


async def search_financial_corpus_handler(
    *,
    user_id: uuid.UUID,  # noqa: ARG001 — uniform handler contract; corpus is cross-user
    db: Optional[SQLModelAsyncSession] = None,  # noqa: ARG001 — retriever uses its own sync session
    query: str = "",
    top_k: int = 5,
) -> SearchFinancialCorpusOutput:
    # retrieve_relevant_docs is sync + holds a sync DB session internally;
    # run it in a thread to avoid blocking the event loop during chat turns.
    raw = await asyncio.to_thread(
        retrieve_relevant_docs, query, _DEFAULT_LANGUAGE, top_k
    )

    rows = [
        CorpusDocRow(
            # doc_id is stable across ingestion runs — the corpus version is
            # tracked separately at ingestion time.
            source_id=str(item["doc_id"]),
            snippet=str(item["content"])[:_SNIPPET_MAX_CHARS],
            similarity=float(item["similarity"]),
        )
        for item in raw
    ]

    return SearchFinancialCorpusOutput(rows=rows, row_count=len(rows))
