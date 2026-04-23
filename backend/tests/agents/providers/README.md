# Cross-Provider LLM Regression Matrix (Story 9.5c)

Exercises every LLM-backed agent path in the codebase against all three
providers (`anthropic`, `openai`, `bedrock`) to verify Stories 9.5a + 9.5b's
"bit-for-bit equivalent behavior" promise via real API calls.

## Scope

Three agent paths (as of 2026-04-23, verified by
`grep -rn "get_llm_client\|get_fallback_llm_client" backend/app/`):

- `app/agents/categorization/node.py` — transaction categorization
- `app/agents/education/node.py` — RAG-backed insight cards
- `app/services/schema_detection.py` — AI-assisted CSV schema detection

**Out of scope:** Epic 8 agents (`pattern_detection/`, `triage/`,
`pattern_detection/detectors/recurring.py`) contain zero LLM calls today — they
are pure statistical code. The epic description's "Epic 8 (pattern,
subscription, triage) agents" line is aspirational. If a future story wires an
LLM into one of those paths, extend the matrix then.

## Equivalence contract

Schema + label, not prose. See Story 9.5c AC #2.

- **Categorization:** `category` must be in the per-case allowlist;
  `transaction_kind` must match the gold value exactly.
- **Education:** cards validate against schema; `severity` is one of
  `{critical, warning, info}` (currently widened to also accept
  `{low, medium, high}` pending TD-088 prompt-tightening — Bedrock-Haiku emits
  the extended set); language matches the requested locale; body-bearing
  content is non-empty in either `why_it_matters` OR `deep_dive` (AC #2 asks
  for a single body field; gpt-4o-mini occasionally omits `why_it_matters`
  while filling `deep_dive`, also tracked under TD-088).
- **Schema detection:** `field_map` includes the required keys
  `{date, amount, description}`. Value strings are not asserted.

## Running locally

```bash
cd backend
export ANTHROPIC_API_KEY=...
export OPENAI_API_KEY=...
# AWS creds via AWS_PROFILE / AWS_ACCESS_KEY_ID / instance role
uv run pytest tests/agents/providers/ -v -m provider_matrix -s
```

To limit the provider sweep (e.g. no AWS locally):

```bash
LLM_PROVIDER_MATRIX_PROVIDERS=anthropic,openai \
  uv run pytest tests/agents/providers/ -v -m provider_matrix -s
```

The default sweep (`uv run pytest tests/ -q`) deselects this package via
`-m "not provider_matrix"`.

## CI

Manually triggered via [ci-backend-provider-matrix.yml](../../../../.github/workflows/ci-backend-provider-matrix.yml)
(`workflow_dispatch` only). Run-reports upload as the `provider-matrix-run-reports`
artifact (30-day retention).

## Cost estimate

~30 LLM calls per full matrix run. Approximate cost on 2026-04-23 pricing:

- Haiku 4.5: ~$0.05
- gpt-4o-mini: ~$0.02
- Bedrock Haiku 4.5 + Nova Micro: ~$0.05

Total: **~$0.12 per full matrix run**.

## Non-goals

- No automatic retries on flaky LLM responses — the first response is the
  signal. Retries hide cross-provider regressions.
- No mocking of `detect_schema`, `categorize_batch`, or `education_node`
  internals. The whole point is that the full agent path runs against each
  provider.
- No stand-alone assertion on prose equivalence — that's a semantic parity
  problem owned by TD-087, not this story.
