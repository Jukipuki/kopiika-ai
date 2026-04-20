# ADR-0002: AI-Assisted Bank Statement Schema Detection

- **Status:** Proposed
- **Date:** 2026-04-19
- **Deciders:** Oleh (product/eng), Winston (architecture)
- **Related:** Epic 11 (Ingestion & Categorization Hardening), ADR-0001 (transaction kind first-class)

## Context

The ingestion pipeline supports three statement parsers:

- `backend/app/agents/ingestion/parsers/monobank.py` — hardcoded for Monobank's CSV
- `backend/app/agents/ingestion/parsers/privatbank.py` — hardcoded for PrivatBank
- `backend/app/agents/ingestion/parsers/generic.py` — best-effort fallback

All three detect columns by keyword-matching against fixed lists and recognize dates via fixed format sets. The consequences documented in [parsing-and-categorization-issues.md](../../_bmad-output/implementation-artifacts/parsing-and-categorization-issues.md):

- Any column rename, header translation, or reordering silently produces corrupt output (wrong amounts, wrong dates, missed columns) — no runtime error.
- Every new bank format is a code change: developer writes a parser, ships it, ops team tests it. No self-service path.
- The `generic.py` fallback is pattern-matched heuristics that work until they don't. Its behavior on an unknown format is "silently produce best-guess output" rather than "flag the uncertainty."

Ukraine has ~15 active retail banks, diaspora users bring statements from 10+ more, and banks periodically rename columns or localize headers. A per-bank hardcoded parser does not scale with the product's reach.

## Decision

Introduce an AI-assisted schema-detection path for statements from unknown formats. The LLM is given the header row plus a small number of sample rows and asked to produce a **structural mapping** (which column is the date, which is the amount, which is the description, etc.). The mapping is then applied deterministically to parse every row.

Flow:

```
upload → fingerprint(header_row) → bank_format_registry lookup
                                   ├── hit  → apply cached mapping deterministically
                                   └── miss → LLM schema-detection → persist mapping → apply
```

- **Fingerprint** = SHA-256 of the normalized header row (lowercase, whitespace-collapsed, Unicode-normalized). Identical headers from repeat uploads skip the LLM entirely.
- **LLM is asked to reason about structure, not values.** The output is a JSON config (`{date_column: "Дата операції", amount_column: "Сума", description_column: "Опис", ...}`), not parsed transactions. Hallucination surface is narrow: the LLM either picks the right column or it doesn't, and misdetection is caught by the post-parse validation layer.
- **Known banks retain their deterministic parsers.** Monobank and PrivatBank happy-path uploads never touch the LLM. The AI path is (a) the fallback for unknown formats, and (b) the escape hatch when a known-bank parser fails validation.
- **Detected schemas are persisted** in a new `bank_format_registry` table with an operator-editable `override_mapping` column. Misdetections can be corrected once and the corrected mapping is reused for every subsequent upload with the same fingerprint.

## Consequences

### Positive

- **Self-service for new banks.** New formats (domestic banks we haven't seen, diaspora-user banks, brokerage statements) work on first upload without code changes.
- **Cost is bounded and small.** One LLM call per *new* header fingerprint across all users, ever. Once a schema is cached, every future upload with that header is free.
- **Narrow hallucination surface.** The LLM produces a column mapping, not transaction values. Misdetection manifests as systematic parse errors (wrong column → wrong dates, wrong amounts) that the validation layer (tech spec §5) catches and surfaces as partial-import warnings.
- **Audit trail.** `bank_format_registry` becomes the record of what the system believes about every bank format it has encountered. Operators can inspect, correct, and version mappings.
- **Decouples parser correctness from code deploys.** A bank changes its header format → new fingerprint → new detection; no hotfix required.

### Negative

- **LLM availability in the ingestion hot path.** The first upload of a new format now depends on the LLM client being reachable. Acceptable: upload is already async (Celery), and LLM failure falls back to `generic.py` with a warning surfaced to the user.
- **Operator burden for misdetections.** Someone has to review low-confidence mappings and apply overrides. Mitigation: detection confidence is persisted, and only below-threshold detections are queued for review; the majority of formats (standard CSV exports) detect cleanly.
- **New table and migration.** `bank_format_registry` adds a table and an Alembic migration; trivial but non-zero cost.

### Neutral

- **Known-bank parsers remain the happy path.** No reliability regression for Monobank/PrivatBank users — they never hit the AI path unless their parser fails validation, which is a strictly better error signal than silently-corrupt output.
- **`generic.py` is phased out, not deleted.** It remains as the secondary fallback (AI detection fails → generic heuristics → last-resort partial import with prominent warning). After ≥ 2 quarters of clean AI-detection metrics, consider deprecation.

## Alternatives Considered

### Alt 1: Continue writing per-bank deterministic parsers

Accept the maintenance cost; hire/assign a developer per bank format.

Rejected: does not scale with the product's reach; the existing parsers already drift when banks rename headers; every new parser is 1-2 engineer-days that compounds.

### Alt 2: LLM-parses-transactions (end-to-end)

Feed the whole CSV to the LLM and ask for structured transactions out.

Rejected: (a) cost scales with transaction count (O(N) LLM calls per upload instead of O(1) per *new* format); (b) hallucination surface is every value, not just structure — a hallucinated amount is financial corruption; (c) no determinism or reproducibility; (d) no way to cache.

### Alt 3: Schema detection via regex/heuristic rule engine

Write a more elaborate heuristic detector that considers column-name synonyms, position hints, value-pattern analysis.

Rejected: this is `generic.py` on steroids. The failure mode is the same: when a heuristic rule doesn't match, output is silently wrong. Rules require ongoing maintenance; LLM-as-structure-detector offloads that maintenance to a model that already has broad knowledge of tabular financial data formats.

### Alt 4: User-driven column mapping UI

Show users the uploaded CSV and ask them to point at the date column, the amount column, etc.

Rejected as primary solution: degrades UX badly for the common case (standard bank export). Retained as an operator-side fallback for formats the AI cannot detect confidently.

## Compliance / How We Verify

- Integration test: upload a synthetic CSV with a novel header; assert `bank_format_registry` gains a row, parsed output matches expected transactions, and a second upload with identical headers does not trigger an LLM call.
- Validation layer (tech spec §5) catches and reports schema-detection failures as partial-import warnings rather than silent corruption.
- Observability: detection success rate, detection latency, fingerprint-cache hit rate, operator override rate — all tracked as dashboard metrics (tech spec §9).
- Fallback chain tested: known-bank parser fails → AI detection triggers → AI detection fails → `generic.py` triggers → validation layer flags partial import. Each transition emits a structured log event.
