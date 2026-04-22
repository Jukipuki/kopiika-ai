"""Unit tests for the RAG-eval retrieval metrics (Story 9.1)."""

import math

from tests.eval.rag.metrics import precision_at_k, recall_at_k, reciprocal_rank


def test_precision_at_k_perfect() -> None:
    assert precision_at_k(["a", "b", "c"], ["a", "b", "c"], 3) == 1.0


def test_precision_at_k_partial() -> None:
    # two of the top-3 are gold
    assert math.isclose(precision_at_k(["a", "x", "b"], ["a", "b"], 3), 2 / 3)


def test_precision_at_k_k_larger_than_retrieved() -> None:
    # k=5 but only 2 retrieved — denominator stays k (standard IR convention),
    # missing slots count as non-hits so precision is NOT inflated.
    assert precision_at_k(["a", "b"], ["a"], 5) == 1 / 5


def test_precision_at_k_zero_k() -> None:
    assert precision_at_k(["a", "b"], ["a"], 0) == 0.0


def test_precision_at_k_no_retrieved() -> None:
    assert precision_at_k([], ["a"], 5) == 0.0


def test_recall_at_k_perfect() -> None:
    assert recall_at_k(["a", "b", "c"], ["a", "b"], 5) == 1.0


def test_recall_at_k_partial() -> None:
    assert recall_at_k(["a", "x", "y"], ["a", "b"], 5) == 0.5


def test_recall_at_k_truncated_top_k() -> None:
    # gold 'b' is at position 4, but k=3 so it's missed
    assert recall_at_k(["a", "x", "y", "b"], ["a", "b"], 3) == 0.5


def test_recall_at_k_empty_expected() -> None:
    assert recall_at_k(["a"], [], 5) == 0.0


def test_reciprocal_rank_first_position() -> None:
    assert reciprocal_rank(["a", "b"], ["a"]) == 1.0


def test_reciprocal_rank_third_position() -> None:
    assert math.isclose(reciprocal_rank(["x", "y", "a"], ["a"]), 1 / 3)


def test_reciprocal_rank_no_hit() -> None:
    assert reciprocal_rank(["x", "y"], ["a"]) == 0.0


def test_reciprocal_rank_multiple_gold_first_match_wins() -> None:
    # 'b' at position 2 is the first hit — even though 'a' also gold (position 4)
    assert reciprocal_rank(["x", "b", "y", "a"], ["a", "b"]) == 0.5
