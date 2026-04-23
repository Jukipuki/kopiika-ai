"""Cross-provider regression matrix for categorization (Story 9.5c).

Exercises the categorization agent's LLM path end-to-end against the
three providers (`anthropic`, `openai`, `bedrock`). Equivalence contract:
per-case `category in acceptable_categories` AND `transaction_kind == gold`.

WRONG shortcut to avoid: returning hand-crafted JSON from a test stub and
asserting the parser survives. That proves parsing, not cross-provider
equivalence. The whole point is the *prompt → real LLM → parsed result*
chain runs against each provider.
"""

from __future__ import annotations

import time
import uuid
from typing import Any

import pytest

from app.agents import llm as llm_module
from app.agents.categorization import node as cat_node
from app.agents.state import FinancialPipelineState

from .conftest import PROVIDERS, load_fixture, write_run_report

pytestmark = [
    pytest.mark.provider_matrix,
    pytest.mark.parametrize("provider", PROVIDERS),
]


def _build_state(cases: list[dict]) -> FinancialPipelineState:
    """Build a minimal FinancialPipelineState with unmapped-MCC txns.

    The fixtures are MCC 4829 (which has no fixed mapping), so Pass 1
    defers every case to the LLM — the code-path we want to exercise.
    """
    transactions = [
        {
            "id": c["id"],
            "description": c["description"],
            "amount": c["amount_kopiykas"],
            "mcc": c["mcc"],
        }
        for c in cases
    ]
    return {
        "job_id": f"test-job-{uuid.uuid4()}",
        "user_id": f"test-user-{uuid.uuid4()}",
        "upload_id": f"test-upload-{uuid.uuid4()}",
        "transactions": transactions,
        "categorized_transactions": [],
        "errors": [],
        "step": "",
        "total_tokens_used": 0,
        "locale": "uk",
        "insight_cards": [],
        "literacy_level": "beginner",
        "completed_nodes": [],
        "failed_node": None,
        "pattern_findings": [],
        "detected_subscriptions": [],
        "triage_category_severity_map": {},
    }


@pytest.mark.parametrize("use_fallback", [False, True])
def test_categorization_matches_golden_set(
    provider: str,
    use_fallback: bool,
    _provider_setup: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Matrix: 3 providers × 2 (primary, fallback) = 6 parametrized items.

    The fallback branch is only meaningful for `provider == "bedrock"`, where
    it exercises the Nova Micro fallback role (TD-085 empirical exposure).
    For anthropic/openai the fallback is the opposite primary — already
    covered by the direct provider param — so those items skip.
    """
    if use_fallback and provider != "bedrock":
        pytest.skip("use_fallback=True only meaningful for bedrock primary (TD-085 probe)")

    cases = load_fixture("categorization_cases.json")
    state = _build_state(cases)

    # Resolve the model ID the categorization call will actually route to —
    # recorded in the run-report so TD-085's "Nova Micro probe" empirical
    # claim is durable (i.e. the report proves fallback actually landed on the
    # agent_fallback role, not the primary).
    if use_fallback:
        resolved_role = "agent_fallback"
        resolved_provider = llm_module._FALLBACK_MAP[provider]
    else:
        resolved_role = "agent_default"
        resolved_provider = provider
    resolved_model_id = llm_module._resolve_model_id(resolved_role, resolved_provider)

    if use_fallback:
        # Force the primary to raise so the `except ValueError` branch at
        # categorization/node.py:510 falls through to get_fallback_llm_client().
        # The branch selector in node.py is specifically ValueError (primary
        # "not available", e.g. missing API key); a bare Exception propagates.
        def _raise_primary() -> Any:
            raise ValueError("simulated primary failure (matrix fallback probe)")

        monkeypatch.setattr(cat_node, "get_llm_client", _raise_primary)

    t0 = time.monotonic()
    result_state = cat_node.categorization_node(state)
    latency_ms = int((time.monotonic() - t0) * 1000)

    categorized = {
        row["transaction_id"]: row for row in result_state["categorized_transactions"]
    }

    results: list[dict] = []
    failures: list[str] = []
    for case in cases:
        got = categorized.get(case["id"])
        if got is None:
            failures.append(f"case {case['id']}: no categorized row returned")
            results.append({
                "case_id": case["id"],
                "description": case["description"],
                "provider": provider,
                "use_fallback": use_fallback,
                "passed": False,
                "error": "no row returned",
                "latency_ms_batch_total": latency_ms,
                "case_count": len(cases),
                "resolved_model_id": resolved_model_id,
                "resolved_role": resolved_role,
                "note": "latency is batch-total, not per-case — categorization_node is a single batched LLM call",
            })
            continue

        category = got.get("category")
        kind = got.get("transaction_kind")
        allowed = set(case["acceptable_categories"])
        gold_kind = case["expected_kind"]

        category_ok = category in allowed
        kind_ok = kind == gold_kind
        passed = category_ok and kind_ok

        record = {
            "case_id": case["id"],
            "description": case["description"],
            "provider": provider,
            "use_fallback": use_fallback,
            "got_category": category,
            "got_kind": kind,
            "acceptable_categories": sorted(allowed),
            "expected_kind": gold_kind,
            "confidence_score": got.get("confidence_score"),
            "passed": passed,
            "latency_ms_batch_total": latency_ms,
            "case_count": len(cases),
            "resolved_model_id": resolved_model_id,
            "resolved_role": resolved_role,
        }
        results.append(record)

        if not passed:
            failures.append(
                f"case {case['id']!r} ({case['description']!r}) on provider={provider} "
                f"use_fallback={use_fallback}: got category={category!r}, kind={kind!r}; "
                f"expected category in {sorted(allowed)}, kind={gold_kind!r}"
            )

    agent_slug = "categorization-fallback" if use_fallback else "categorization"
    report_path = write_run_report(agent_slug, provider, results, _provider_setup)
    print(f"[provider-matrix] wrote run-report: {report_path}")

    if failures:
        pytest.fail("\n".join(failures))
