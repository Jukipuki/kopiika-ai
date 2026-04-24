"""Tests for the ``search_financial_corpus`` tool (Story 10.4c AC #5 + #12)."""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

from app.agents.chat.tools.rag_corpus_tool import (
    SearchFinancialCorpusInput,
    SearchFinancialCorpusOutput,
    search_financial_corpus_handler,
)


def _doc(doc_id: str, content: str, similarity: float = 0.9) -> dict:
    return {
        "doc_id": doc_id,
        "language": "en",
        "chunk_type": "body",
        "content": content,
        "similarity": similarity,
    }


@pytest.mark.asyncio
async def test_returns_top_k_rows_from_retriever():
    canned = [_doc(f"doc-{i}", "short text") for i in range(5)]
    with patch(
        "app.agents.chat.tools.rag_corpus_tool.retrieve_relevant_docs",
        new=MagicMock(return_value=canned),
    ) as mock:
        out = await search_financial_corpus_handler(
            user_id=uuid.uuid4(), db=None, query="savings tips", top_k=5
        )
    assert out.row_count == 5
    assert all(r.source_id.startswith("doc-") for r in out.rows)
    args, kwargs = mock.call_args
    # user_id must NOT be passed to the retriever.
    assert uuid.UUID not in [type(a) for a in args]
    for value in (*args, *kwargs.values()):
        assert not isinstance(value, uuid.UUID)


@pytest.mark.asyncio
async def test_query_empty_fails_pydantic_validation():
    with pytest.raises(ValidationError):
        SearchFinancialCorpusInput.model_validate({"query": "", "top_k": 5})


@pytest.mark.asyncio
async def test_query_too_long_fails_pydantic_validation():
    with pytest.raises(ValidationError):
        SearchFinancialCorpusInput.model_validate({"query": "x" * 501, "top_k": 5})


@pytest.mark.asyncio
async def test_snippet_truncated_at_500_chars():
    long_body = "z" * 1200
    canned = [_doc("doc-long", long_body)]
    with patch(
        "app.agents.chat.tools.rag_corpus_tool.retrieve_relevant_docs",
        new=MagicMock(return_value=canned),
    ):
        out = await search_financial_corpus_handler(
            user_id=uuid.uuid4(), db=None, query="q", top_k=1
        )
    assert len(out.rows[0].snippet) == 500


@pytest.mark.asyncio
async def test_output_schema_round_trip():
    canned = [_doc("doc-1", "body")]
    with patch(
        "app.agents.chat.tools.rag_corpus_tool.retrieve_relevant_docs",
        new=MagicMock(return_value=canned),
    ):
        out = await search_financial_corpus_handler(
            user_id=uuid.uuid4(), db=None, query="q", top_k=1
        )
    SearchFinancialCorpusOutput.model_validate(out.model_dump())
