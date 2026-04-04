"""Tests for embeddings service (Story 3.3)."""

from unittest.mock import MagicMock, patch

from app.rag.embeddings import embed_batch, embed_text


@patch("app.rag.embeddings._get_client")
def test_embed_text_returns_1536_floats(mock_get_client):
    """embed_text returns a list of 1536 floats."""
    mock_embedding = [0.01 * i for i in range(1536)]
    mock_response = MagicMock()
    mock_response.data = [MagicMock(embedding=mock_embedding)]
    mock_get_client.return_value.embeddings.create.return_value = mock_response

    result = embed_text("test text")

    assert isinstance(result, list)
    assert len(result) == 1536
    assert all(isinstance(v, float) for v in result)
    mock_get_client.return_value.embeddings.create.assert_called_once_with(
        model="text-embedding-3-small",
        input="test text",
    )


@patch("app.rag.embeddings._get_client")
def test_embed_batch_returns_multiple_embeddings(mock_get_client):
    """embed_batch returns a list of embeddings for each input text."""
    mock_emb1 = [0.1] * 1536
    mock_emb2 = [0.2] * 1536
    mock_response = MagicMock()
    mock_response.data = [
        MagicMock(embedding=mock_emb1),
        MagicMock(embedding=mock_emb2),
    ]
    mock_get_client.return_value.embeddings.create.return_value = mock_response

    result = embed_batch(["text one", "text two"])

    assert len(result) == 2
    assert len(result[0]) == 1536
    assert len(result[1]) == 1536
    mock_get_client.return_value.embeddings.create.assert_called_once_with(
        model="text-embedding-3-small",
        input=["text one", "text two"],
    )


@patch("app.rag.embeddings._get_client")
def test_embed_text_calls_openai_api(mock_get_client):
    """Verifies the OpenAI API is called with correct model parameter."""
    mock_response = MagicMock()
    mock_response.data = [MagicMock(embedding=[0.0] * 1536)]
    mock_get_client.return_value.embeddings.create.return_value = mock_response

    embed_text("hello world")

    call_kwargs = mock_get_client.return_value.embeddings.create.call_args
    assert call_kwargs.kwargs["model"] == "text-embedding-3-small"
