"""Pure retrieval-metric functions for the RAG eval harness (Story 9.1).

No dependencies on DB, LLM, or project modules — safe to unit-test on the
default pytest sweep.
"""


def precision_at_k(retrieved_ids: list[str], expected_ids: list[str], k: int) -> float:
    """Fraction of the top-k slots filled by an expected id.

    Denominator is `k` (standard IR convention), NOT the number of retrieved
    ids. When the retriever returns fewer than `k` results, the missing slots
    count as non-hits — otherwise precision@k would be inflated on sparse
    retrievals, biasing the baseline.
    """
    if k <= 0:
        return 0.0
    expected = set(expected_ids)
    hits = sum(1 for doc_id in retrieved_ids[:k] if doc_id in expected)
    return hits / k


def recall_at_k(retrieved_ids: list[str], expected_ids: list[str], k: int) -> float:
    """Fraction of expected_ids that appear in the top-k retrieved ids.

    If expected_ids is empty, returns 0.0.
    """
    if not expected_ids or k <= 0:
        return 0.0
    top_k = set(retrieved_ids[:k])
    hits = sum(1 for doc_id in expected_ids if doc_id in top_k)
    return hits / len(expected_ids)


def reciprocal_rank(retrieved_ids: list[str], expected_ids: list[str]) -> float:
    """1 / rank of the first retrieved id in expected_ids (1-indexed); 0.0 if no hit."""
    expected = set(expected_ids)
    for idx, doc_id in enumerate(retrieved_ids, start=1):
        if doc_id in expected:
            return 1.0 / idx
    return 0.0
