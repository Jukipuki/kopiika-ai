# Story 4.10: Profile aggregates respect `transaction_kind` (diversity / regularity / coverage fix)

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **user**,
I want my Category Diversity, Expense Regularity, and Income Coverage sub-scores to ignore savings and transfer transactions,
so that a single deposit top-up or between-account transfer doesn't wreck the rest of my Health Score.

## Acceptance Criteria

1. **Given** a user has transactions with `transaction_kind` in `('savings', 'transfer')` in the profile's period, **When** `build_or_update_profile` computes `total_expenses` and `category_totals`, **Then** those transactions are excluded from both aggregates — `total_expenses` reflects only `kind='spending'` outflows (as a non-positive integer, matching the existing sign convention), and `category_totals` contains only `kind='spending'` rows.

2. **Given** a user has transactions with `transaction_kind='income'` that happen to have a negative amount (data-correction edge case), **When** `build_or_update_profile` computes `total_income`, **Then** `total_income` is the sum of `abs(amount)` over `kind='income'` rows — it reads kind, not sign, matching Story 4.9's contract for Savings Ratio.

3. **Given** a user has one `kind='spending'` transaction per category (e.g. groceries, transport, utilities) and one large `kind='savings'` transaction, **When** the Health Score is computed, **Then** Category Diversity is computed over the spending categories only, Expense Regularity variance is computed over the spending-category totals only, and Income Coverage's `avg_monthly_expense` uses only the spending outflows — the savings transaction influences Savings Ratio (Story 4.9) and nothing else.

4. **Given** a user whose `total_income` (kind-based) exceeds their total `kind='spending'` outflows, **When** Income Coverage is computed, **Then** `net_savings = total_income - abs(total_expenses)` is positive and `months_covered = net_savings / avg_monthly_expense` yields a non-zero score, regardless of whether the user also has `kind='savings'` or `kind='transfer'` transactions in the period.

5. **Given** a legacy user whose transactions all default to `kind='spending'` (pre-Epic-11), **When** `build_or_update_profile` runs, **Then** `total_income = 0`, `total_expenses` equals the sum of all transaction amounts (all are spending), and `category_totals` contains every category — this is the accepted greenfield behavior (matching Story 4.9 AC #6). No migration or backfill is introduced by this story.

6. **Given** the existing `get_category_breakdown` endpoint ([profile_service.py:31-70](backend/app/services/profile_service.py#L31-L70)) reads `category_totals` from the profile, **When** that endpoint runs after this story lands, **Then** the returned breakdown contains only `kind='spending'` categories — savings/transfer rows no longer appear as spending categories in the UI (intended user-visible side effect).

7. **Given** a user has the same underlying transactions before and after this change with `transaction_kind` correctly populated, **When** `calculate_health_score` runs via the Celery pipeline, **Then** a new `FinancialHealthScore` row is persisted with Savings Ratio unchanged from Story 4.9 behavior, and Category Diversity / Expense Regularity / Income Coverage reflect only spending-kind activity (they may increase — that is the point).

8. **Given** `build_or_update_profile` persists the new aggregates, **When** the `Transaction` rows have any `transaction_kind` value outside `('spending', 'income', 'savings', 'transfer')` (defensive — CHECK constraint makes this unreachable in practice), **Then** such rows are excluded from all three aggregates rather than silently bucketed as spending. The implementation iterates by explicit kind, not by "everything that isn't X".

## Tasks / Subtasks

- [x] Task 1: Backend — rewrite `_upsert_profile` aggregates to partition by `transaction_kind` (AC: #1, #2, #5, #8)
  - [x] 1.1 In [backend/app/services/profile_service.py](backend/app/services/profile_service.py#L204-L240), replace the sign-based partition (lines 210-218) with kind-based partition:
    - `total_income = sum(abs(t.amount) for t in transactions if t.transaction_kind == 'income')` — AC #2, matches Story 4.9's `abs()` contract.
    - `total_expenses = sum(t.amount for t in transactions if t.transaction_kind == 'spending')` — preserves the existing non-positive sign convention on the column (consumers like [health_score_service.py:164](backend/app/services/health_score_service.py#L164) still do `profile.total_income + profile.total_expenses`; flipping the sign would cascade).
    - `category_totals` loop: replace the `if t.amount >= 0: continue` guard with `if t.transaction_kind != 'spending': continue`. The inner write stays the same (`category_totals[cat] = category_totals.get(cat, 0) + t.amount`).
  - [x] 1.2 Keep `period_start` / `period_end` computed over ALL transactions (every kind). Rationale: the period is a "range of data the user has uploaded" concept, not a "range of spending". Savings Ratio in `_compute_breakdown` scopes its kind query by `[period_start, period_end]` (see health_score_service.py:112-113) — shrinking the period to spending-only would silently exclude savings/income rows from that query.
  - [x] 1.3 Leave the function signature, return type, commit behavior, and `profile.updated_at` stamping unchanged. No new columns, no migration.
  - [x] 1.4 Add a short docstring note on `_upsert_profile` explaining that partitioning is by `transaction_kind` (the ground truth since Story 11.2), not by amount sign — and that this is what keeps Category Diversity / Expense Regularity / Income Coverage honest when a user has savings or transfer rows.

- [x] Task 2: Backend — verify `_compute_breakdown` consumers still read correctly (AC: #3, #4, #7)
  - [x] 2.1 Re-read [health_score_service.py:125-172](backend/app/services/health_score_service.py#L125-L172). `category_totals` (diversity + regularity) and `profile.total_income + profile.total_expenses` (income coverage `net_savings`) flow through automatically with the new kind-partitioned aggregates — no code change in `_compute_breakdown` is required. Document this in Completion Notes with a one-line trace.
  - [x] 2.2 Confirm `net_savings = profile.total_income + profile.total_expenses` still behaves correctly: `total_income` is now a positive integer (from `abs`), `total_expenses` stays non-positive (spending sign convention). Sum still yields the right net. This is the exact place AC #4 targets — a deposit top-up (kind='savings', amount=-50000) no longer contributes to `total_expenses`, so `net_savings` no longer collapses for users who saved money.
  - [x] 2.3 Do NOT touch `_compute_breakdown`'s savings-ratio block or the re-normalization logic — those are Story 4.9's contract and remain stable.

- [x] Task 3: Backend — check other `FinancialProfile` consumers for semantic regressions (AC: #1, #2)
  - [x] 3.1 [backend/app/agents/triage/node.py:40-46](backend/app/agents/triage/node.py#L40-L46) computes `monthly_income = profile.total_income / months`. With kind-based income, this now reflects actual salary-kind inflows rather than "every positive row" — which is the correct signal for "severity thresholds scaled to income". No code change needed, but add a single-line comment here pointing to Story 4.10 so future readers understand the semantic shift.
  - [x] 3.2 [backend/app/api/v1/profile.py:81-89](backend/app/api/v1/profile.py#L81-L89) (`GET /api/v1/profile`) passes through `total_income` / `total_expenses` / `category_totals` unchanged — no API response-shape change, only value semantics. Add a note in the endpoint docstring: "Values reflect kind-based aggregates (spending / income) since Story 4.10."
  - [x] 3.3 [backend/app/api/v1/data_summary.py:146-148](backend/app/api/v1/data_summary.py#L146-L148) — same pass-through story. No code change; just verify no test asserts on a pre-4.10 value.
  - [x] 3.4 [backend/app/services/profile_service.py:31-70](backend/app/services/profile_service.py#L31-L70) `get_category_breakdown` reads `category_totals` — once partitioned by kind, the endpoint returns spending-only categories (AC #6). No code change in this function.

- [x] Task 4: Backend tests — add `TestProfileAggregatesByKind` in `test_profile_service.py` (AC: #1, #2, #3, #5, #8)
  - [x] 4.1 Extend `_create_transaction_sync` (see [test_profile_service.py:85-104](backend/tests/test_profile_service.py#L85-L104)) with an optional `kind: str = "spending"` parameter that sets `transaction_kind` on the row. This matches the fixture pattern used by `_add_transaction` in [test_health_score_service.py:109-130](backend/tests/test_health_score_service.py#L109-L130) — consistency across test modules.
  - [x] 4.2 Test: `kind='savings'` outflow is excluded from `total_expenses` and `category_totals`. Fixture: one `(amount=50000, kind='income')`, one `(amount=-15000, kind='spending', category='food')`, one `(amount=-50000, kind='savings', category='savings-deposit')`. Assert `total_income == 50000`, `total_expenses == -15000`, `category_totals == {'food': -15000}`. (AC #1, #3)
  - [x] 4.3 Test: `kind='transfer'` rows are excluded from all three aggregates. Same fixture shape but replacing `savings` with `transfer`. (AC #1)
  - [x] 4.4 Test: `kind='income'` with a negative amount (edge case) → `total_income = abs(amount)`. Fixture: `(amount=-30000, kind='income')`. Assert `total_income == 30000`. (AC #2)
  - [x] 4.5 Test: legacy all-`spending` default → `total_income == 0`, `total_expenses == sum(amounts)`, `category_totals` populated over all rows. Fixture: the exact scenario of `test_creates_profile_from_transactions` ([test_profile_service.py:113-138](backend/tests/test_profile_service.py#L113-L138)) but WITHOUT setting kind (i.e. everything defaults to `'spending'`). Assert the new kind-aware values (AC #5). Note: this is a breaking change to that existing test — Task 5 migrates it.
  - [x] 4.6 Test: AC #8 defensive path — feed a transaction with an unexpected kind (bypass CHECK by constructing the row directly in Python; SQLite used in tests does not enforce CHECK, which makes this test possible). Assert it is excluded from all three aggregates rather than being treated as spending.
  - [x] 4.7 Test: period scoping unchanged — `period_start` / `period_end` cover the oldest and newest transactions across ALL kinds (Task 1.2). Fixture: savings on 2026-01-05, spending on 2026-02-15, income on 2026-03-20. Assert `period_start == 2026-01-05`, `period_end == 2026-03-20`.

- [x] Task 5: Backend tests — migrate existing `test_profile_service.py` fixtures to set `kind` explicitly (AC: #1, #2, #5)
  - [x] 5.1 `test_creates_profile_from_transactions`: set `kind='income'` on the salary row, `kind='spending'` on food/transport. Expected values (50000 income, -20000 expenses, food/transport categories) stay the same post-migration.
  - [x] 5.2 `test_updates_existing_profile`: set `kind='income'` on both salary rows, `kind='spending'` on food. Expected totals unchanged.
  - [x] 5.3 `test_mixed_categories`: set `kind='spending'` on the three expense rows, `kind='income'` on the salary row. Expected categories unchanged.
  - [x] 5.4 `test_uncategorized_transactions`: set `kind='spending'` on both (the semantic is "uncategorized spending"). Expected `category_totals == {'uncategorized': -8000}` unchanged.
  - [x] 5.5 `test_empty_transactions`: no change — still asserts zero state.
  - [x] 5.6 Verify the four `TestGetCategoryBreakdown` / `TestGetMonthlyComparison` tests that construct profiles by hand (e.g. [test_profile_service.py:311-313](backend/tests/test_profile_service.py#L311), `category_totals={...}`) are unaffected — they set `category_totals` directly rather than round-tripping through `_upsert_profile`.

- [x] Task 6: Backend tests — update `test_health_score_service.py` profile fixtures (AC: #3, #4, #7)
  - [x] 6.1 Current pattern (e.g. [test_health_score_service.py:145-161](backend/tests/test_health_score_service.py#L145-L161)) constructs a `FinancialProfile` directly via `_create_profile` and then adds transactions via `_add_transaction`. Since this bypasses `build_or_update_profile`, the profile's `total_income`/`total_expenses`/`category_totals` are already hand-set and do NOT depend on Story 4.10's partition change. No migration needed for these fixtures.
  - [x] 6.2 Add a new test `test_category_diversity_ignores_savings_kind`: build a profile via `build_or_update_profile` (NOT hand-constructed) with one `(income)`, three `(spending, distinct categories)`, and one huge `(savings)` row. Assert `category_totals` has three entries (not four), and `score.breakdown["category_diversity"]` reflects the three-spending-category distribution (should be non-zero — distinct from the single-category floor that a pre-4.10 run would produce). (AC #3)
  - [x] 6.3 Add `test_income_coverage_ignores_savings_kind`: profile via `build_or_update_profile` with `(income=60000)`, `(spending=-10000 food)`, `(spending=-10000 transport)`, `(savings=-40000)` over a ~90-day period. Assert `score.breakdown["income_coverage"] > 0` (post-4.10 behavior). Write a brief comment noting that pre-4.10 this would have been `0` because the `-40000` savings row inflated `total_expenses` to `-60000`, crushing `net_savings` to `0`. (AC #4)
  - [x] 6.4 Add `test_end_to_end_health_score_via_build_or_update_profile`: full pipeline — `_add_transaction` for every row, then `build_or_update_profile`, then `calculate_health_score`. Asserts Savings Ratio unchanged from Story 4.9, and the three other components reflect spending-only activity. (AC #7)

- [x] Task 7: Backend tests — verify `test_profile_api.py` and `test_data_summary_api.py` are not impacted (AC: #1, #2)
  - [x] 7.1 Both test modules construct `FinancialProfile` rows directly with `total_income`/`total_expenses`/`category_totals` set by hand (e.g. [test_profile_api.py:99-101](backend/tests/test_profile_api.py#L99-L101)). They do NOT round-trip through `build_or_update_profile`, so the aggregate-partition change has no effect. Run these suites as-is and document in Completion Notes.

- [x] Task 8: Backend tests — triage node impact (AC: #2)
  - [x] 8.1 Check any tests covering `_compute_monthly_income` / triage severity thresholds. If a test constructs a profile with `total_income` set by hand (not via `build_or_update_profile`), the value flows through unchanged — no migration needed. If a test round-trips through `build_or_update_profile` with mixed-kind transactions, verify the computed `total_income` matches kind-based semantics (salary only).

- [x] Task 9: Observability & tech-debt hygiene
  - [x] 9.1 Log a single structured DEBUG line in `_upsert_profile` when `total_income == 0 AND len(transactions) > 0` — candidate signal for "user has data but no kind='income' rows" (legacy or misclassified). Keep it DEBUG (not INFO) to avoid noise; operators who care can bump the level. Use the existing structured-logger pattern in the codebase (see Story 6.4 logging conventions).
  - [x] 9.2 If Story 4.9's TD-066 (observability on the `GROUP BY transaction_kind` query in `_compute_breakdown`) is still open, append a note to the TD-066 entry in [docs/tech-debt.md](docs/tech-debt.md) that this story does NOT add observability to `_upsert_profile`'s aggregation — same gap, same TD. Don't open a duplicate TD.

- [x] Task 10: End-to-end verification (AC: #7)
  - [x] 10.1 Activate `backend/.venv` and run `pytest backend/tests/` — zero regressions expected (existing tests migrated in Task 5/6, new tests added in Task 4/6).
  - [x] 10.2 Run `pytest backend/tests/test_profile_service.py backend/tests/test_health_score_service.py backend/tests/test_profile_api.py backend/tests/test_data_summary_api.py -v` in isolation for focused signal.
  - [x] 10.3 Document new test count delta in Completion Notes.
  - [x] 10.4 Frontend: no frontend changes in this story (the `FinancialProfile` fields are not consumed by the current Next.js app — verified via `grep` for `total_income|total_expenses|category_totals` in `frontend/src/`, zero matches). If `npm test --run` passes without changes, note that explicitly in Completion Notes.

## Dev Notes

### Scope summary

- **Backend-only, narrow.** Single file at the core: `backend/app/services/profile_service.py::_upsert_profile` switches from sign-based to kind-based aggregation. Everything downstream (`_compute_breakdown`, triage, API serializers) flows through without code changes.
- **No migrations, no new columns, no API-shape changes.** `transaction_kind` already exists on `transactions` (Story 11.2), and the `FinancialProfile` columns are just semantically reinterpreted.
- **No frontend changes.** `grep` for `total_income|total_expenses|category_totals` in `frontend/src/` returns zero matches — these aggregates are consumed only by backend services (health score, triage, profile/data-summary APIs that pass them through). The category breakdown endpoint (Story 4.8) is affected in output but not in contract.

### Architecture compliance

- **Database:** No schema changes. Relies on `transactions.transaction_kind` (VARCHAR(16), NOT NULL, default `'spending'`, CHECK constraint `IN ('spending','income','savings','transfer')`) landed by Story 11.2.
- **Backend patterns:** The change lives inside `_upsert_profile`, called from `build_or_update_profile(session, user_id)`, which runs inside the Celery sync pipeline via `processing_tasks.py`. Keep the function sync (SQLModel `Session`, not async) to match the worker.
- **Sign conventions:** `total_expenses` stays a non-positive integer (spending sign-preserved). `total_income` switches from "sum of positive amounts" to "sum of absolute values of kind='income' rows". This aligns `total_income` with the Story 4.9 `abs()` contract while leaving `total_expenses`' sign convention intact so that `net_savings = total_income + total_expenses` keeps working in health_score_service.py without a callsite change.
- **API response:** Unchanged shape. `ProfileResponse` ([profile.py:19-28](backend/app/api/v1/profile.py#L19-L28)) still serializes `total_income`, `total_expenses`, `category_totals` verbatim.
- **i18n / currency:** N/A — values are kopiykas integers, no user-facing string changes.

### Why partition in `_upsert_profile` (not in `_compute_breakdown`)?

Two alternative designs considered and rejected:

1. **Leave aggregates sign-based; fix each consumer to re-filter by kind.** Rejected — three separate consumers (diversity block, regularity block, coverage block in `_compute_breakdown`) would each need to issue their own kind-scoped query. That's premature duplication and keeps the profile row semantically wrong.
2. **Add a new `spending_category_totals` column next to `category_totals` for backward compatibility.** Rejected per CLAUDE.md's "no backwards-compat shims, no half-finished migrations" rule. The existing `category_totals` consumers (health_score diversity/regularity, `get_category_breakdown` endpoint) all want spending-only — no caller benefits from the old semantics.

Fixing the aggregate at its source (`_upsert_profile`) is the minimal coherent change: one write-site, many read-sites flow through.

### The `kind='income'` negative-amount edge case (AC #2)

The CHECK constraint allows a row like `(kind='income', amount=-30000)`. In practice this shouldn't happen — the categorization agent emits `kind='income'` for credits only. But Story 4.9's Savings Ratio used `sum(abs(amount) WHERE kind='income')`, and this story must match that contract on the profile side. A future data-correction story (manual override / admin edit) could create such a row; the `abs()` makes both Savings Ratio and `total_income` robust to that without an extra constraint.

### Period scoping — why compute over ALL kinds (AC implicit)

`period_start` and `period_end` remain computed over every transaction regardless of kind (Task 1.2). Story 4.9's `_compute_breakdown` scopes its kind query by `[period_start, period_end]` — if we shrank the period to spending-only, a user who saved money in January but didn't spend until February would see their January savings excluded from Savings Ratio. That would silently re-break the thing Story 4.9 just fixed. The period is a "data range" concept, not a "spending range" concept.

### Sign convention for `total_expenses` — why keep it negative?

Alternative: store `total_expenses` as `sum(abs(amount) WHERE kind='spending')` (positive). This would be more readable ("total spent: 15000") but requires touching every consumer:

- `health_score_service.py:164` `net_savings = profile.total_income + profile.total_expenses` → would break; needs `total_income - total_expenses`.
- `profile.py:84` API response → shape unchanged but clients expecting a negative value would break.
- `data_summary.py:147` same pass-through risk.

Keeping the non-positive convention preserves all call sites. The "awkward" sign is already baked into the schema. Future cleanup is a candidate tech-debt item but out of scope for this story.

### Legacy users (AC #5)

Pre-Epic-11 transactions default to `kind='spending'` (the CHECK constraint + default value in [transaction.py:31](backend/app/models/transaction.py#L31)). For such users:

- `total_income = 0` (no kind='income' rows).
- `total_expenses` sums every row (all spending).
- `category_totals` contains every category (same as today).

Consequences:
- Savings Ratio: `None` (Story 4.9 AC #6 — already handled).
- Category Diversity / Expense Regularity: behave as today (all rows counted).
- Income Coverage: `0` because `net_savings = 0 + total_expenses = negative`. Already the case today for legacy users since `total_income` was also `0` (no positive-amount rows for legacy imports with income mixed into one bucket, depending on bank format).
- Triage severity thresholds: `monthly_income` returns `None` (triage falls back to "absolute thresholds" per [triage/node.py:31-33](backend/app/agents/triage/node.py#L31-L33)) — same neutral behavior as today when income wasn't detected.

Net: legacy users see the same behavior they see today. No backfill needed.

### Previous Story Intelligence

**From Story 4.9 (Savings Ratio wired to `transaction_kind`, done 2026-04-22):**
- `_compute_breakdown` now takes `(session, user_id, profile)` and queries transactions directly — it does NOT read profile-level `total_income`/`total_expenses` for Savings Ratio. This story only affects the OTHER three components (diversity, regularity, coverage), which still read from the profile. So the two stories compose cleanly: 4.9 fixed savings; 4.10 fixes the rest.
- Savings Ratio uses `abs(amount)` grouped by kind. This story adopts the same `abs()` contract for `total_income` (AC #2).
- `_compute_breakdown` period-scopes by `profile.period_start` / `profile.period_end` — preserving those across ALL kinds (Task 1.2) keeps that query honest.
- The 4.9 PR added `TD-066` for observability on the `GROUP BY transaction_kind` query. This story inherits the same gap in `_upsert_profile`; Task 9.2 notes it on the same TD rather than opening a duplicate.

**From Story 11.2 (`transaction_kind` field, done):**
- Values: `'spending' | 'income' | 'savings' | 'transfer'` — CHECK constraint enforces it. Default `'spending'`.
- Kind/category compatibility validated at persistence (e.g. a row can't be `(kind='income', category='groceries')`). So filtering by kind in aggregates is safe — no re-validation needed.

**From Story 11.3 (enriched prompt, done):**
- LLM emits `transaction_kind` per row; the MCC pre-pass defaults to `'spending'`. Post-Epic-11 data has meaningful kind distributions; pre-Epic-11 data is all `'spending'` (see AC #5).

**From Story 4.5 (Health Score calculation, done):**
- `calculate_health_score(session, user_id)` is called from Celery sync worker inside `processing_tasks.py` wrapped in try/except. No change to that contract here — Task 1's change is inside `_upsert_profile`, upstream.

**From Story 4.8 (Category Spending Breakdown, done):**
- `get_category_breakdown` reads `category_totals` from the profile — intentionally expenses-only today. Post-4.10 it becomes spending-kind-only, which is a tighter semantic (AC #6). No code change in that function, but any test that happened to put a savings/transfer kind in `category_totals` by hand (none found) would need updating.

### Git Intelligence (Recent Commits)

- `a4f68b7` Story 4.9: Savings Ratio wired to `transaction_kind`
- `86a46c2` Bug fixes
- `676523e` Story 11.9: Observability Signals for Ingestion & Categorization
- `e2afaa2` Story 11.8: Low-Confidence Categorization Review Queue
- `565539f` Story 11.10: Counterparty-Aware Categorization for PE Account Statements

Pattern: Story 4.9 (the immediate predecessor) followed exactly this shape — narrow backend change inside a single service function, kind-partition semantic, `abs()` contract, fixture migration in one test module, no migrations. This story extends the same pattern to `_upsert_profile`.

### Project Structure Notes

- Backend modify: `backend/app/services/profile_service.py` (Task 1).
- Backend read-only-verify: `backend/app/services/health_score_service.py`, `backend/app/agents/triage/node.py`, `backend/app/api/v1/profile.py`, `backend/app/api/v1/data_summary.py` (Task 2, 3).
- Backend tests extend: `backend/tests/test_profile_service.py` (Tasks 4, 5), `backend/tests/test_health_score_service.py` (Task 6).
- Backend tests verify (no change): `backend/tests/test_profile_api.py`, `backend/tests/test_data_summary_api.py` (Task 7).
- Frontend: none.
- Python venv: `backend/.venv` (not project root).
- No new files. No migrations. No i18n.

### Testing standards

- Backend: `pytest` with SQLite in-memory fixtures. Extend the existing `_create_transaction_sync` helper in `test_profile_service.py` with a `kind` parameter (consistency with `_add_transaction` in `test_health_score_service.py`).
- **SQLite does not enforce CHECK constraints** — this is what makes Task 4.6 (AC #8 defensive path with an invalid kind) possible. Worth a one-line comment in the test itself so a future reader doesn't assume CHECK protects this path.
- Zero regressions: all existing backend tests must still pass after fixture migration (Task 5). Any test that asserted on `total_income` from a pre-4.10 sign-based partition must be updated to set `transaction_kind='income'` on fixture rows.
- Frontend: no tests needed; no frontend code touched.

### References

- [Source: backend/app/services/profile_service.py:204-240](backend/app/services/profile_service.py#L204-L240) — `_upsert_profile` — THE function to modify
- [Source: backend/app/services/profile_service.py:210-218](backend/app/services/profile_service.py#L210-L218) — exact lines for the sign → kind partition switch
- [Source: backend/app/services/health_score_service.py:125-172](backend/app/services/health_score_service.py#L125-L172) — three consumers that flow through unchanged (diversity, regularity, coverage)
- [Source: backend/app/services/health_score_service.py:164](backend/app/services/health_score_service.py#L164) — `net_savings = total_income + total_expenses` — the sign-convention lock-in
- [Source: backend/app/models/transaction.py:31](backend/app/models/transaction.py#L31) — `transaction_kind` field with default `'spending'`
- [Source: backend/app/models/financial_profile.py](backend/app/models/financial_profile.py) — `FinancialProfile` schema (unchanged)
- [Source: backend/app/agents/triage/node.py:30-46](backend/app/agents/triage/node.py#L30-L46) — `_compute_monthly_income` consumer (Task 3.1)
- [Source: backend/app/api/v1/profile.py:67-89](backend/app/api/v1/profile.py#L67-L89) — `GET /api/v1/profile` passthrough (Task 3.2)
- [Source: backend/app/api/v1/data_summary.py:146-148](backend/app/api/v1/data_summary.py#L146-L148) — data summary passthrough (Task 3.3)
- [Source: backend/tests/test_profile_service.py:85-214](backend/tests/test_profile_service.py#L85-L214) — fixture helper and existing tests needing migration (Tasks 4, 5)
- [Source: backend/tests/test_health_score_service.py:109-130](backend/tests/test_health_score_service.py#L109-L130) — reference `_add_transaction` helper pattern with `kind` parameter
- [Source: _bmad-output/planning-artifacts/epics.md:1280-1318](_bmad-output/planning-artifacts/epics.md#L1280-L1318) — original story requirements
- [Source: _bmad-output/implementation-artifacts/4-9-savings-ratio-wired-to-transaction-kind.md](_bmad-output/implementation-artifacts/4-9-savings-ratio-wired-to-transaction-kind.md) — Story 4.9 prior art (pattern to follow)
- [Source: _bmad-output/implementation-artifacts/11-2-transaction-kind-field-expanded-category-taxonomy.md](_bmad-output/implementation-artifacts/11-2-transaction-kind-field-expanded-category-taxonomy.md) — Story 11.2 prior art (kind field introduction)

### Resolved decisions

- **Sign convention for `total_expenses` — resolved 2026-04-22:** keep `total_expenses` non-positive (sign-preserving) rather than switching to `sum(abs(...))`. Rationale: `health_score_service.py:164` and any other callers that compute `total_income + total_expenses` as `net_savings` rely on this convention. Flipping the sign would cascade. Store the sign convention as invariant; flip it only in a dedicated cleanup story if ever needed.
- **Period scoping — resolved 2026-04-22:** compute `period_start` / `period_end` over ALL transaction kinds, not spending-only. Rationale: Story 4.9's Savings Ratio query is period-scoped; shrinking the period would silently exclude kind='savings' / kind='income' rows from that query. Period is a "data range" concept.
- **Aggregate at source vs re-filter in consumers — resolved 2026-04-22:** partition inside `_upsert_profile`, not in each consumer. Rationale: one write site, many read sites. No caller needs the old (sign-based) semantics. Keeping the profile row semantically correct beats threading kind filters through every consumer.
- **Defensive-path test for unexpected kind values (AC #8) — resolved 2026-04-22:** include it. SQLite doesn't enforce CHECK constraints in the test environment, so the test is cheap to write and documents the "iterate by explicit kind, not 'everything that isn't X'" invariant.

### Open questions

_None at story-creation time. If the dev finds during implementation that a consumer was missed, pause and update this section rather than widening scope silently._

## Dev Agent Record

### Agent Model Used

Claude Opus 4.7 (1M context)

### Debug Log References

### Completion Notes List

- **Task 1** — `_upsert_profile` now partitions by `transaction_kind`. `total_income = sum(abs(amount) where kind=='income')`, `total_expenses = sum(amount where kind=='spending')` (sign-preserving), `category_totals` accumulates only `kind=='spending'` rows. `period_start`/`period_end` span every kind (Task 1.2). Added docstring explaining the contract. Dependencies, function signature, commit behavior unchanged.
- **Task 2** — Verified `_compute_breakdown` consumers: `category_totals` flows into diversity + regularity; `profile.total_income + profile.total_expenses` still yields `net_savings` correctly since `total_expenses` kept its non-positive sign convention. No code change in `health_score_service.py`.
- **Task 3.1** — Added a docstring note in `triage/node.py::_estimate_monthly_income_kopiykas` pointing at Story 4.10's kind-based semantic.
- **Task 3.2** — Added a docstring note on `GET /api/v1/profile` about kind-based aggregates. `data_summary.py` passthrough unchanged (no docstring change needed — endpoint is a plain pass-through of the same fields).
- **Task 4** — Added 6 new tests in `TestProfileAggregatesByKind` covering savings exclusion, transfer exclusion, income-abs edge case, legacy default, defensive unexpected-kind path, and period scoping across kinds.
- **Task 5** — Migrated `test_creates_profile_from_transactions`, `test_updates_existing_profile`, `test_mixed_categories` to set `kind=` explicitly. `test_uncategorized_transactions` and `test_empty_transactions` needed no change (defaults match their semantics).
- **Task 6** — Added 3 end-to-end tests in `TestHealthScoreWithKindPartitionedProfile` exercising the real `build_or_update_profile → calculate_health_score` pipeline. Existing hand-constructed-profile tests untouched (they bypass `_upsert_profile`).
- **Task 7** — `test_profile_api.py` and `test_data_summary_api.py` construct profiles by hand; they passed unchanged (16/16).
- **Task 8** — No triage tests round-trip through `build_or_update_profile` with mixed-kind transactions; no migration needed.
- **Task 9.1** — Added a DEBUG structured log (`profile.aggregate.no_income_kind`) in `_upsert_profile` when the user has transactions but zero `kind='income'` rows. Uses `logging.getLogger(__name__)` (standard pattern in `app/services/`).
- **Task 9.2** — Appended a note to TD-066 in `docs/tech-debt.md` noting the analogous in-memory partition in `_upsert_profile` shares the same observability gap. No duplicate TD opened.
- **Task 10** — Full `backend/tests/` suite: **843 passed, 9 deselected**. (3 pre-existing `test_auth.py` teardown errors unrelated to this story — they pass cleanly when that module is run in isolation.) Focused suite (`test_profile_service.py` + `test_health_score_service.py` + `test_profile_api.py` + `test_data_summary_api.py`): **70 passed**. New test count delta: +6 in `test_profile_service.py`, +3 in `test_health_score_service.py`.
- **Frontend** — No changes. `grep` for `total_income|total_expenses|category_totals` in `frontend/src/` returns zero matches.

### File List

- backend/app/services/profile_service.py
- backend/app/agents/triage/node.py
- backend/app/api/v1/profile.py
- backend/tests/test_profile_service.py
- backend/tests/test_health_score_service.py
- docs/tech-debt.md
- VERSION

### Code Review (2026-04-22)

Adversarial review by Claude Opus 4.7. 8/8 ACs verified implemented; all [x] tasks verified against code and tests. File List matches git exactly. Findings + fixes:

- **[MEDIUM] M1 — Weak AC #4 assertion** — fixed: `test_income_coverage_ignores_savings_kind` now asserts `income_coverage >= 95` (deterministic expected ≈100) instead of `>0`. [test_health_score_service.py:636-647](backend/tests/test_health_score_service.py#L636-L647)
- **[MEDIUM] M2 — Stale docstring in `get_category_breakdown`** — fixed: docstring now reflects kind-based semantic; the remaining sign-filter annotated as a legacy-user guard. [profile_service.py:37-57](backend/app/services/profile_service.py#L37-L57)
- **[MEDIUM] M3 — `data_summary.py` missing Task 3.2-style docstring** — fixed: `get_data_summary` docstring now notes kind-based aggregate semantics since Story 4.10. [data_summary.py:100-106](backend/app/api/v1/data_summary.py#L100-L106)
- **[LOW] L1 — `health_score_service._compute_breakdown` sign filter looks dead** — fixed (bonus): added a comment explaining it is a legacy-user guard, preventing a well-meaning future cleanup from breaking `test_legacy_all_spending_default`. [health_score_service.py:127-131](backend/app/services/health_score_service.py#L127-L131)
- **[LOW] L2 — E2E test doesn't assert DB persistence of `FinancialHealthScore`** — kept story-local. AC #7 persistence clause is already covered by Story 4.5's own tests; re-asserting here is belt-and-suspenders with low upside. Not promoted to TD.

All 54 tests in `test_profile_service.py` + `test_health_score_service.py` pass post-fix.

### Change Log

- 2026-04-22 — Story 4.10 implementation. `_upsert_profile` now partitions aggregates by `transaction_kind` (spending / income), not by amount sign. `total_income` follows Story 4.9's `abs()` contract; `total_expenses` keeps its non-positive sign convention. `category_totals` contains only `kind='spending'` rows, so Category Diversity, Expense Regularity, and Income Coverage no longer collapse when the user has `kind='savings'` or `kind='transfer'` rows in the period. Added TestProfileAggregatesByKind (6 tests) and TestHealthScoreWithKindPartitionedProfile (3 end-to-end tests). Migrated existing fixtures to set `kind=` explicitly. Added a TD-066 update note (same observability gap applies to the new in-memory partition). Version bumped from 1.29.0 to 1.30.0 per story completion.
