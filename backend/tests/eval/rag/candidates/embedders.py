"""Embedder implementations for Story 9.3 candidate matrix.

Four candidates are defined: OpenAI text-embedding-3-small (control),
text-embedding-3-large, Amazon Titan Text Embeddings V2, and Cohere
embed-multilingual-v3. Each implementation exposes the ``Embedder`` protocol
so the runner routes all four identically while isolating provider-specific
batch limits and request-body quirks in one place.

Cohere requires ``input_type="search_document"`` for corpus chunks and
``input_type="search_query"`` for runtime queries — mixing them silently
degrades retrieval by ~10%. The separate ``embed_documents`` / ``embed_query``
methods exist for that reason; collapsing to one method would lose the signal.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from typing import Protocol

import boto3


def _now_ms() -> float:
    return time.perf_counter() * 1000.0


@dataclass
class EmbedUsage:
    """Running totals captured per-embedder across a spike run."""

    input_tokens: int = 0
    calls: int = 0
    elapsed_ms: float = 0.0
    query_latencies_ms: list[float] = field(default_factory=list)
    # True if ``input_tokens`` is a client-side approximation (e.g. word-count
    # × 1.3) because the provider does not return a token count. Surfaced in
    # the candidate ``.meta.json`` so cost columns aren't compared apples to
    # oranges. See Story 9.3 Code Review M2.
    input_tokens_approximated: bool = False


class Embedder(Protocol):
    name: str
    provider: str
    model_id: str
    dims: int
    usage: EmbedUsage

    def embed_query(self, text: str) -> list[float]: ...

    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...


# ─── OpenAI ────────────────────────────────────────────────────────────────

class OpenAIEmbedder:
    provider = "OpenAI"

    def __init__(self, model_id: str, dims: int, *, slug: str):
        from openai import OpenAI

        from app.core.config import settings

        self.model_id = model_id
        self.dims = dims
        self.name = slug
        self.usage = EmbedUsage()
        self._client = OpenAI(api_key=settings.OPENAI_API_KEY)

    def _embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        t0 = _now_ms()
        resp = self._client.embeddings.create(model=self.model_id, input=texts)
        elapsed = _now_ms() - t0
        self.usage.calls += 1
        self.usage.elapsed_ms += elapsed
        self.usage.input_tokens += int(getattr(resp.usage, "total_tokens", 0) or 0)
        return [item.embedding for item in resp.data]

    def embed_query(self, text: str) -> list[float]:
        t0 = _now_ms()
        out = self._embed([text])[0]
        self.usage.query_latencies_ms.append(_now_ms() - t0)
        return out

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._embed(texts)


# ─── Bedrock base ──────────────────────────────────────────────────────────

def _bedrock_runtime_client(region: str):
    profile = os.getenv("AWS_PROFILE")
    session = boto3.Session(profile_name=profile, region_name=region) if profile else boto3.Session(region_name=region)
    return session.client("bedrock-runtime")


# ─── Amazon Titan Text Embeddings V2 ───────────────────────────────────────

class TitanV2Embedder:
    provider = "Amazon"
    model_id = "amazon.titan-embed-text-v2:0"

    def __init__(self, *, dims: int = 1024, normalize: bool = True, region: str = "eu-central-1"):
        self.dims = dims
        self.normalize = normalize
        self.region = region
        self.name = "titan-text-embeddings-v2"
        self.usage = EmbedUsage()
        self._client = _bedrock_runtime_client(region)

    def _invoke(self, text: str) -> list[float]:
        body = json.dumps({"inputText": text, "dimensions": self.dims, "normalize": self.normalize})
        t0 = _now_ms()
        resp = self._client.invoke_model(modelId=self.model_id, body=body)
        elapsed = _now_ms() - t0
        payload = json.loads(resp["body"].read())
        self.usage.calls += 1
        self.usage.elapsed_ms += elapsed
        self.usage.input_tokens += int(payload.get("inputTextTokenCount", 0) or 0)
        return payload["embedding"]

    def embed_query(self, text: str) -> list[float]:
        t0 = _now_ms()
        out = self._invoke(text)
        self.usage.query_latencies_ms.append(_now_ms() - t0)
        return out

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        # Titan V2 on Bedrock accepts single-input only per InvokeModel call.
        return [self._invoke(t) for t in texts]


# ─── Cohere embed-multilingual-v3 ──────────────────────────────────────────

class CohereMultilingualV3Embedder:
    provider = "Cohere"
    model_id = "cohere.embed-multilingual-v3"
    _BATCH_MAX = 96  # Cohere Bedrock contract: up to 96 texts per call.

    def __init__(self, *, region: str = "eu-central-1"):
        self.dims = 1024
        self.region = region
        self.name = "cohere-embed-multilingual-v3"
        self.usage = EmbedUsage()
        self._client = _bedrock_runtime_client(region)

    def _invoke(self, texts: list[str], input_type: str) -> list[list[float]]:
        body = json.dumps({"texts": texts, "input_type": input_type})
        t0 = _now_ms()
        resp = self._client.invoke_model(modelId=self.model_id, body=body)
        elapsed = _now_ms() - t0
        payload = json.loads(resp["body"].read())
        self.usage.calls += 1
        self.usage.elapsed_ms += elapsed
        # Cohere Bedrock does not return a token count; approximate by word count × 1.3
        approx_tokens = sum(int(len(t.split()) * 1.3) for t in texts)
        self.usage.input_tokens += approx_tokens
        self.usage.input_tokens_approximated = True
        return payload["embeddings"]

    def embed_query(self, text: str) -> list[float]:
        t0 = _now_ms()
        out = self._invoke([text], input_type="search_query")[0]
        self.usage.query_latencies_ms.append(_now_ms() - t0)
        return out

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        out: list[list[float]] = []
        for i in range(0, len(texts), self._BATCH_MAX):
            out.extend(self._invoke(texts[i : i + self._BATCH_MAX], input_type="search_document"))
        return out


# ─── Factory ───────────────────────────────────────────────────────────────

def build_embedder(slug: str, *, region: str = "eu-central-1") -> Embedder:
    if slug == "text-embedding-3-small":
        return OpenAIEmbedder("text-embedding-3-small", 1536, slug=slug)
    if slug == "text-embedding-3-large":
        return OpenAIEmbedder("text-embedding-3-large", 3072, slug=slug)
    if slug == "titan-text-embeddings-v2":
        return TitanV2Embedder(region=region)
    if slug == "cohere-embed-multilingual-v3":
        return CohereMultilingualV3Embedder(region=region)
    raise ValueError(f"unknown candidate slug: {slug}")
