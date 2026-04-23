"""Tests for RAG retriever (Story 3.3)."""

import inspect
from unittest.mock import MagicMock, patch

from app.rag import retriever as retriever_module
from app.rag.retriever import retrieve_relevant_docs


def test_retriever_sql_casts_to_halfvec():
    """Story 9.6 invariant: retriever SQL must cast query embedding as halfvec,
    matching the document_embeddings.embedding column type. A regression to
    `AS vector` would be accepted by pgvector via implicit coercion on read but
    would silently diverge from the schema the Story 9.3 spike validated."""
    source = inspect.getsource(retriever_module)
    assert "CAST(:embedding AS halfvec)" in source
    assert "CAST(:embedding AS vector)" not in source


def _make_row(doc_id, language, chunk_type, content, similarity):
    """Create a mock row object matching SQLAlchemy result."""
    row = MagicMock()
    row.doc_id = doc_id
    row.language = language
    row.chunk_type = chunk_type
    row.content = content
    row.similarity = similarity
    return row


@patch("app.rag.retriever.embed_text")
@patch("app.rag.retriever.get_sync_session")
def test_retrieve_relevant_docs_basic(mock_session_ctx, mock_embed):
    """Basic retrieval returns language-matched results."""
    mock_embed.return_value = [0.1] * 3072

    rows = [
        _make_row("uk/budgeting-basics", "uk", "overview", "Бюджет...", 0.92),
        _make_row("uk/spending-categories", "uk", "key_concepts", "Категорії...", 0.88),
        _make_row("uk/savings-strategies", "uk", "overview", "Заощадження...", 0.85),
    ]

    mock_session = MagicMock()
    mock_session.execute.return_value.fetchall.return_value = rows
    mock_session_ctx.return_value.__enter__ = MagicMock(return_value=mock_session)
    mock_session_ctx.return_value.__exit__ = MagicMock(return_value=False)

    results = retrieve_relevant_docs("grocery spending", language="uk", top_k=5)

    assert len(results) == 3
    assert results[0]["doc_id"] == "uk/budgeting-basics"
    assert results[0]["language"] == "uk"
    assert results[0]["similarity"] == 0.92
    mock_embed.assert_called_once_with("grocery spending")


@patch("app.rag.retriever.embed_text")
@patch("app.rag.retriever.get_sync_session")
def test_retrieve_relevant_docs_language_filter(mock_session_ctx, mock_embed):
    """Retriever filters by language parameter."""
    mock_embed.return_value = [0.1] * 3072

    rows = [
        _make_row("en/budgeting-basics", "en", "overview", "Budget...", 0.90),
        _make_row("en/spending-categories", "en", "key_concepts", "Categories...", 0.85),
        _make_row("en/savings-strategies", "en", "overview", "Savings...", 0.80),
    ]

    mock_session = MagicMock()
    mock_session.execute.return_value.fetchall.return_value = rows
    mock_session_ctx.return_value.__enter__ = MagicMock(return_value=mock_session)
    mock_session_ctx.return_value.__exit__ = MagicMock(return_value=False)

    results = retrieve_relevant_docs("spending habits", language="en", top_k=5)

    assert len(results) == 3
    assert all(r["language"] == "en" for r in results)


@patch("app.rag.retriever.embed_text")
@patch("app.rag.retriever.get_sync_session")
def test_retrieve_relevant_docs_cross_lingual_fallback(mock_session_ctx, mock_embed):
    """When fewer than MIN_RESULTS in target language, cross-lingual results are added."""
    mock_embed.return_value = [0.1] * 3072

    # Only 2 results in target language (below MIN_RESULTS=3)
    language_rows = [
        _make_row("uk/budgeting-basics", "uk", "overview", "Бюджет...", 0.92),
        _make_row("uk/spending-categories", "uk", "key_concepts", "Категорії...", 0.88),
    ]
    cross_rows = [
        _make_row("en/budgeting-basics", "en", "overview", "Budget...", 0.85),
        _make_row("en/spending-categories", "en", "key_concepts", "Categories...", 0.80),
    ]

    mock_session = MagicMock()
    mock_session.execute.return_value.fetchall.side_effect = [language_rows, cross_rows]
    mock_session_ctx.return_value.__enter__ = MagicMock(return_value=mock_session)
    mock_session_ctx.return_value.__exit__ = MagicMock(return_value=False)

    results = retrieve_relevant_docs("grocery spending", language="uk", top_k=5)

    # Should have 2 UK + at least 1 EN (cross-lingual fallback)
    assert len(results) >= 3
    assert any(r["language"] == "en" for r in results)


@patch("app.rag.retriever.embed_text")
@patch("app.rag.retriever.get_sync_session")
def test_retrieve_relevant_docs_empty_results(mock_session_ctx, mock_embed):
    """When no results found, returns empty list (after cross-lingual attempt)."""
    mock_embed.return_value = [0.1] * 3072

    mock_session = MagicMock()
    mock_session.execute.return_value.fetchall.side_effect = [[], []]
    mock_session_ctx.return_value.__enter__ = MagicMock(return_value=mock_session)
    mock_session_ctx.return_value.__exit__ = MagicMock(return_value=False)

    results = retrieve_relevant_docs("unknown topic", language="uk", top_k=5)
    assert results == []
