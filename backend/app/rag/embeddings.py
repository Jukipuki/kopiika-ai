"""Thin wrapper around OpenAI text-embedding-3-large API."""

from openai import OpenAI

from app.core.config import settings

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=settings.OPENAI_API_KEY)
    return _client


def embed_text(text: str) -> list[float]:
    """Embed a single text string, returning a 3072-dim vector."""
    response = _get_client().embeddings.create(
        model="text-embedding-3-large",
        input=text,
    )
    return response.data[0].embedding


def embed_batch(texts: list[str]) -> list[list[float]]:
    """Embed multiple texts in a single API call."""
    if not texts:
        return []
    response = _get_client().embeddings.create(
        model="text-embedding-3-large",
        input=texts,
    )
    return [item.embedding for item in response.data]
