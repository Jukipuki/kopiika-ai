# ADR-0001: Transaction Kind as a First-Class Field

- **Status:** Proposed
- **Date:** 2026-04-19
- **Deciders:** Oleh (product/eng), Winston (architecture)
- **Related:** Epic 11 (Ingestion & Categorization Hardening), Story 4.9 (Savings Ratio wiring), ADR-0002 (AI-assisted schema detection)

## Context

The categorization pipeline classifies every transaction with a single `category` field drawn from a flat taxonomy (`groceries`, `restaurants`, `finance`, `transfers`, `other`, …). Recent incident analysis (see [parsing-and-categorization-issues.md](../../_bmad-output/implementation-artifacts/parsing-and-categorization-issues.md)) identified two structural defects that trace back to a shared cause:

1. Transfers with MCC 4829 (self-transfers, capital movements to deposit/savings accounts, P2P payments) were semantically flattened into the `finance` category. A downstream `abs()` on every amount inflated "Finance" spending by treating income-side transfers as outflows, then flipped to hiding the category entirely when aggregated flows went net-positive.
2. The Savings Ratio component of the Financial Health Score renders `0/100` for every user because there is no reliable signal distinguishing capital retention (savings) from consumption (spending) — the category alone cannot carry that distinction without conflating merchant taxonomy with cash-flow semantics.

Both defects share a root cause: a single categorical axis is being asked to express two orthogonal concepts — *what was bought* and *what kind of money movement occurred*. Overloading one axis forces every consumer (health score, spending breakdowns, pattern detection, triage) to re-derive the missing axis with ad-hoc rules.

## Decision

Introduce `transaction_kind` as a first-class enum field on every transaction, orthogonal to `category`:

```
transaction_kind ∈ { spending, income, savings, transfer }
```

Semantics:

- **spending** — consumption outflow (groceries, restaurants, utilities, etc.)
- **income** — inflow from salary, reimbursement, refund, interest
- **savings** — outflow to a deposit, investment, or savings account (capital retention, not consumption)
- **transfer** — inter-account movement where the user is both counterparties and no net-worth change occurs (self-transfer between own current accounts, currency conversion)

P2P payments to named individuals remain classified as `spending` with `category = transfers_p2p`; they are real outflows from the user's net worth, not inter-account movements.

The categorization pipeline emits `(category, transaction_kind, confidence)` per transaction. The enriched LLM prompt (ADR-independent, tech-spec-defined) is given description, signed amount, MCC, and direction, and returns both axes.

All downstream consumers filter by `transaction_kind` first, then by `category`:

- Spending breakdown: `kind == spending`
- Savings Ratio (health score): `sum(savings outflows) / sum(income)` — no longer derivable only from category labels
- Pattern detection trends: `kind == spending` for month-over-month deltas; `kind == savings` for capital-retention trends
- Triage severity: income reference point computed from `kind == income`

## Consequences

### Positive

- **Fixes the Savings Ratio bug by construction.** The health score has a real signal to compute against; story 4.9 becomes a straightforward wiring job, not a re-architecture.
- **Eliminates a class of bugs.** Code that currently takes `abs(amount)` before aggregating becomes unnecessary; kind-filtered queries are sign-safe because they only aggregate within one flow direction.
- **Decouples merchant taxonomy from cash-flow semantics.** Future category additions (e.g., `crypto`, `insurance`) do not require re-debating how the health score should treat them — the kind field carries that.
- **Enables future insights without schema churn.** Income-stability analysis, savings-rate trends, and transfer-pattern detection all become simple kind-filtered aggregations.

### Negative

- **Adds a required field to categorization output.** Every LLM call, every MCC fallback, every rule-based pre-pass must emit both axes. Increases prompt length modestly (~5%) and forces discipline in fallback paths.
- **Two axes can disagree.** A transaction with `kind = savings` but `category = groceries` is nonsense. Validation must enforce consistency (see tech spec §2.3).
- **Requires a default/fallback.** When the LLM fails to emit `kind`, we default to `kind = spending` for outflows and `kind = income` for inflows based on amount sign. This is safe for the common case and errs toward the dominant consumption-analysis use case.

### Neutral

- **No migration required.** Greenfield — no production data exists. First real deployments will emit `kind` from day one.
- **Schema cost is trivial.** One enum column on `transactions`; no new tables.

## Alternatives Considered

### Alt 1: Keep single-axis taxonomy, expand categories further

Add `savings`, `self_transfer`, `transfer_p2p`, `income_salary`, `income_refund`, etc. to the flat category list.

Rejected: proliferates categories, forces every consumer to know which ones are "spending-like" vs "income-like" vs "neutral movements." Pushes the two-axis problem into consumer code instead of naming it at the source. Every new FR that cares about cash-flow semantics re-derives the same partition.

### Alt 2: Derive kind at read-time from category + amount sign

Keep the schema as-is; compute `kind` in a view or service layer by mapping `category → kind` and using sign.

Rejected: (a) introduces drift — any code path that bypasses the mapping re-creates the bug; (b) the mapping is not always deterministic from category alone (`category = transfers` can be either `savings` or `transfer` depending on destination account); (c) puts load-bearing semantics in a lookup table that isn't enforced by the database.

### Alt 3: Model kind as a separate `cash_flow_events` table

Decompose each transaction into one or more flow events (outflow-consumption, outflow-savings, etc.).

Rejected: premature normalization. The 1:1 mapping between transaction and kind handles every real case we have; the complexity of a second table earns nothing until we have a need for multi-leg decomposition (e.g., split transactions). Revisit if split-transaction support becomes a requirement.

## Compliance / How We Verify

- Schema migration adds `transaction_kind` as NOT NULL with a default fallback computed from amount sign at insert time, replaced by the categorization output on upsert.
- Golden-set evaluation harness (Story 11.1) measures accuracy on *both* axes; success criterion is ≥ 90% on each independently.
- Health-score computation (Story 4.9) reads `kind` directly; integration test asserts Savings Ratio is non-zero for a fixture with known deposit transactions.
- Validation rule: `(kind, category)` combinations are constrained by a compatibility matrix (tech spec §2.3); violations are rejected at the persistence boundary, not silently coerced.
