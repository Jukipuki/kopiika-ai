# Testing

## Standard test sweep

```bash
cd backend && uv run pytest tests/ -v
```

Runs every test that is NOT marked `integration`. This includes unit tests,
fixture schema/coverage checks, and deterministic golden-set precondition
tests. This is what CI (`ci-backend.yml`) executes on every push and PR.

## Evaluation harnesses

Two harnesses gate LLM-driven behaviour before merge. They follow the same
"fixture + `runs/` + gitignored JSON reports" template but run on different
CI schedules because they have different cost/latency profiles.

| Harness | Fixture | Runner | CI workflow |
|---|---|---|---|
| Categorization golden set (Story 11.1) | [`backend/tests/fixtures/categorization_golden_set/`](../backend/tests/fixtures/categorization_golden_set/) | [`test_golden_set.py`](../backend/tests/agents/categorization/test_golden_set.py) | Not run by `ci-backend.yml` (the default sweep excludes `integration` via `pyproject.toml` `addopts`). Invoke on demand via `make eval-categorization`. |
| RAG evaluation (Story 9.1) | [`backend/tests/fixtures/rag_eval/`](../backend/tests/fixtures/rag_eval/) | [`test_rag_harness.py`](../backend/tests/eval/rag/test_rag_harness.py) | [`ci-backend-eval.yml`](../.github/workflows/ci-backend-eval.yml) — manual (`workflow_dispatch`) and optional nightly. Separate from the default sweep because it needs a seeded pgvector corpus and makes ~80 LLM calls per run. |

Run locally:

```bash
# Categorization
cd backend && make eval-categorization

# RAG
cd backend && uv run python -m app.rag.seed   # one-time corpus seed
cd backend && make eval-rag
```

Both harnesses write structured JSON reports under
`backend/tests/fixtures/<harness>/runs/<timestamp>.json` (gitignored). The RAG
harness also breaks results down per-language (en vs uk), per-topic, and
per-question-type, and includes a `worst_10` list of the lowest-scored answers
to drive fixture-expansion decisions.

## Adding a new harness

When adding a third harness (e.g. insight-quality under Epic 12), follow the
same template:

1. Fixture directory under `backend/tests/fixtures/<name>/` with
   `eval_set.jsonl` (or equivalent), `README.md`, and a gitignored `runs/`.
2. Pure-Python metric module + unit tests that run on the default sweep.
3. The expensive harness under `backend/tests/<area>/` marked
   `@pytest.mark.integration` (and optionally `@pytest.mark.eval`).
4. Separate CI workflow when the harness has a different cost profile than
   the default sweep.
