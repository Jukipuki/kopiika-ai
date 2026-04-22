# Story 4.9: Savings Ratio wired to `transaction_kind`

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **user**,
I want my Financial Health Score's Savings Ratio component to reflect what I actually save each month,
so that the score becomes a trustworthy signal of my financial health rather than a constant zero.

## Acceptance Criteria

1. **Given** a user has categorized transactions for a period with at least one `transaction_kind = 'savings'` entry and at least one `transaction_kind = 'income'` entry, **When** the Savings Ratio is computed for that period, **Then** the ratio equals `sum(abs(amount) WHERE kind='savings') / sum(abs(amount) WHERE kind='income')`, clamped to `[0.0, 1.0]`, and rendered as a 0–100 integer in the Health Score breakdown panel.

2. **Given** a user has no `transaction_kind = 'income'` entries in the period, **When** the Savings Ratio is computed, **Then** the Savings Ratio sub-score is `null` in the persisted breakdown and the UI displays "Not enough data yet" rather than `0/100`.

3. **Given** a user has `transaction_kind = 'income'` entries but no `transaction_kind = 'savings'` entries, **When** the Savings Ratio is computed, **Then** the sub-score is the integer `0` and the UI indicates this is a real zero (not a "no data" state).

4. **Given** Story 11.2 has landed and transactions have `transaction_kind` populated, **When** the Savings Ratio calculator runs, **Then** it reads `transaction_kind` directly from transactions; it does NOT infer kind from category labels, amount signs, or MCC codes.

5. **Given** a Health Score integration-test fixture containing a deposit top-up (`transaction_kind='savings'`) and a salary inflow (`transaction_kind='income'`), **When** the Health Score is computed, **Then** Savings Ratio reports a non-zero value that matches the expected `abs(savings)/abs(income)` ratio to within 1% (tolerance accounts for integer rounding).

6. **Given** a user who was onboarded before Epic 11 and has no categorized data with `transaction_kind` populated (legacy rows default to `'spending'`), **When** they view the Health Score, **Then** the Savings Ratio sub-score displays "Not enough data yet" — greenfield assumption applies (no backfill scope in this story).

7. **Given** the persisted breakdown has `savings_ratio = null`, **When** the Health Score ring renders, **Then** the final numeric score (computed via re-normalization over the remaining components) is accompanied by a visible "partial" marker (e.g. an asterisk or small icon next to the number, with a tooltip/helper text "Partial score — savings data not yet available"); and **Given** all four components are non-null, **When** the ring renders, **Then** no partial marker is shown.

## Tasks / Subtasks

- [x] Task 1: Backend — rewrite Savings Ratio computation to read `transaction_kind` (AC: #1, #3, #4, #6)
  - [x] 1.1 In [backend/app/services/health_score_service.py](backend/app/services/health_score_service.py), change `_compute_breakdown(profile)` signature to `_compute_breakdown(session: Session, user_id: UUID, profile: FinancialProfile)` — the function needs access to transactions, not just the aggregated profile, because `transaction_kind` sums are not materialized on the profile row (see Dev Notes: "Why not cache on profile")
  - [x] 1.2 Replace the current savings-ratio block (lines 77–85) with a query that sums `abs(amount)` grouped by `transaction_kind` for the user across the profile's `[period_start, period_end]` window: `SELECT transaction_kind, SUM(ABS(amount)) FROM transactions WHERE user_id=:uid AND date BETWEEN :start AND :end GROUP BY transaction_kind`. Store the result as a dict `kind_totals: dict[str, int]`.
  - [x] 1.3 Compute `savings_score` per AC #1/#2/#3:
    - **Short-circuit first:** if `profile.period_start is None` or `profile.period_end is None` (no transactions yet — defensive; shouldn't happen if this runs after `build_or_update_profile`), skip the query entirely and set `savings_score = None`. This aligns with the other components' "neutral on empty profile" behavior and avoids a pointless DB round-trip.
    - Otherwise run the `GROUP BY transaction_kind` query: `income_total = kind_totals.get("income", 0)`; `savings_total = kind_totals.get("savings", 0)`
    - If `income_total == 0` → `savings_score = None` (AC #2; sentinel for "no data")
    - Else → `raw_ratio = min(1.0, max(0.0, savings_total / income_total))`; `savings_score = int(round(raw_ratio * 100))` (AC #1). When `savings_total == 0` this naturally yields `0` (AC #3).
  - [x] 1.4 Update the return dict type hint from `dict[str, Any]` to reflect `savings_ratio: int | None`. Keep the other three components unchanged for this story.

- [x] Task 2: Backend — rework the weighted-average final score to tolerate a null savings_ratio (AC: #2, #7)
  - [x] 2.1 In `calculate_health_score()` (lines 25–31), when `breakdown["savings_ratio"] is None`, re-normalize the weighted sum across the remaining three components so their weights (0.2 + 0.2 + 0.2 = 0.6) sum to 1.0. Implementation: collect `(score, weight)` pairs, drop pairs with `score is None`, then `final = sum(s * w for s, w in pairs) / sum(w for _, w in pairs)`. If all four components are null (defensive — shouldn't happen post-Epic-11), default `final_score = 0`.
  - [x] 2.2 Persist `breakdown["savings_ratio"]` as literal `None` (JSONB stores SQL `null`) — do NOT coerce to `0` for legacy callers. Add a docstring note that `null` means "insufficient data" and that the UI renders the final score as "partial" in that case (see AC #7).

- [x] Task 3: Backend — pass `session` to `_compute_breakdown` (AC: #1)
  - [x] 3.1 Update the sole caller `calculate_health_score(session, user_id)` to pass `session, user_id, profile` into `_compute_breakdown`. No API-layer change needed — the pipeline task in `processing_tasks.py` already calls `calculate_health_score(session, user_id)` inside the Celery sync session (see Story 4.5 Task 3.1).

- [x] Task 4: Backend tests — extend `test_health_score_service.py` with `transaction_kind` fixtures (AC: #1, #2, #3, #5, #6)
  - [x] 4.1 Add a helper to insert transactions with specific `transaction_kind` values (the existing fixtures only set amount signs; they now need explicit kind).
  - [x] 4.2 Test: profile with salary income (+50000, kind='income') + deposit top-up (-10000, kind='savings') + groceries (-3000, kind='spending') → savings_ratio = 20 (10000/50000 = 0.2 → 20). (AC #1, #5)
  - [x] 4.3 Test: profile with only spending transactions (no income kind) → savings_ratio is `None`, final_score re-normalizes over diversity+regularity+coverage only. (AC #2)
  - [x] 4.4 Test: profile with income but no savings kind → savings_ratio = 0 (int, not None). (AC #3)
  - [x] 4.5 Test: profile where savings > income → raw_ratio clamps to 1.0 → savings_ratio = 100. (AC #1 "clamped to [0.0, 1.0]")
  - [x] 4.6 Test: legacy user with all transactions defaulted to `kind='spending'` → savings_ratio is `None`. (AC #6)
  - [x] 4.7 Test: verify the implementation does NOT read `profile.total_income`, `profile.total_expenses`, category labels, amount signs, or MCC — use a fixture where amount signs and kinds disagree (e.g. a negative amount tagged `kind='income'`, which shouldn't occur in practice but proves the code path reads kind, not sign). (AC #4)
  - [x] 4.8 Test: empty profile (`period_start=None`, `period_end=None`, no transactions) → savings_ratio is `None` and the DB query is not issued (assert via query spy / count, or simply assert the returned breakdown without needing transaction fixtures). (Resolved decision — period-scoping short-circuit)
  - [x] 4.9 Update any existing health-score test fixtures that relied on the old income/expense math — those tests should now set `transaction_kind` explicitly on inserted rows, since the default `'spending'` will make savings_ratio `None` and change the final score.

- [x] Task 5: Backend API tests — verify null serialization (AC: #2)
  - [x] 5.1 In `backend/tests/test_health_score_api.py`, add a test asserting that when `savings_ratio is None` in the stored breakdown, the `GET /api/v1/health-score` response JSON serializes `"savings_ratio": null` (JSON null, not the string `"null"` and not missing the key). The `breakdown` field is a pass-through JSONB opaque dict — no Pydantic aliasing on its keys (types.ts confirms snake_case is preserved).

- [x] Task 6: Frontend types — allow nullable `savings_ratio` (AC: #2)
  - [x] 6.1 In [frontend/src/features/profile/types.ts](frontend/src/features/profile/types.ts), change `savings_ratio: number;` to `savings_ratio: number | null;`. Leave the other three breakdown fields as `number` — this story only introduces the null sentinel for savings.

- [x] Task 7: Frontend — render "Not enough data yet" for null savings_ratio in breakdown panel (AC: #2, #3)
  - [x] 7.1 In [frontend/src/features/profile/components/HealthScoreRing.tsx](frontend/src/features/profile/components/HealthScoreRing.tsx) (the breakdown toggle renders `{breakdown[key]}/100`), branch on `breakdown.savings_ratio === null` and render a localized "Not enough data yet" string instead of `null/100`. A real `0` must still render `0/100` (AC #3) — do NOT treat `0` as missing data.
  - [x] 7.2 Keep the three other components rendering unchanged.

- [x] Task 8: Frontend — render partial-score marker on the ring when savings_ratio is null (AC: #7)
  - [x] 8.1 In `HealthScoreRing.tsx`, compute `const isPartial = breakdown.savings_ratio === null;`.
  - [x] 8.2 When `isPartial`, render a small asterisk (`*`) immediately adjacent to the centered score number inside the SVG. Use a smaller font size (≈0.9rem) and position it as a superscript — add a new `<text>` element offset to the top-right of the score text, inheriting `fill-foreground` but with reduced opacity (e.g. `opacity-60`) so it reads as secondary information. Do not render the asterisk when `isPartial` is false.
  - [x] 8.3 Add an accessible tooltip/helper: below the ring (between the ring and the "Show breakdown" button), when `isPartial`, render a muted helper line with the localized string "Partial score — savings data not yet available" (small text, `text-muted-foreground`, `text-xs`). This provides the explanation for sighted users; screen readers get it via the updated `aria-label` (Task 8.4).
  - [x] 8.4 Update the SVG `aria-label` (currently `t("ariaLabel", { score })`) to include a "partial" qualifier when `isPartial` — either extend the existing `ariaLabel` message with a `{partial}` ICU placeholder, or introduce a separate `ariaLabelPartial` key. Pick whichever keeps `en.json`/`uk.json` cleaner; document the choice in Completion Notes.
  - [x] 8.5 Do NOT modify the ring's arc geometry, color, or zone logic — the final score value already reflects re-normalization (Task 2.1), so the ring is a truthful visual of the computed number. Only the marker + helper text signal the partial nature.

- [x] Task 9: i18n — add the new strings (AC: #2, #7)
  - [x] 9.1 Add `profile.healthScore.breakdown.savingsRatioNoData` to both [frontend/messages/en.json](frontend/messages/en.json) and [frontend/messages/uk.json](frontend/messages/uk.json). English: "Not enough data yet". Ukrainian: translate in tone with the existing strings (consult the existing `profile.healthScore.*` keys for voice — warm, not clinical).
  - [x] 9.2 Add `profile.healthScore.partialScoreHelper` (English: "Partial score — savings data not yet available") and, if the approach from Task 8.4 requires it, `profile.healthScore.ariaLabelPartial`. Add matching Ukrainian translations. Keep the voice consistent with the existing healthScore strings.

- [x] Task 10: Frontend tests (AC: #2, #3, #7)
  - [x] 10.1 Update [frontend/src/features/profile/__tests__/HealthScoreRing.test.tsx](frontend/src/features/profile/__tests__/HealthScoreRing.test.tsx): add a test that renders with `savings_ratio: null` and asserts the "Not enough data yet" string appears in the breakdown panel (use the i18n key, consistent with how other next-intl tests assert translated strings in this repo).
  - [x] 10.2 Add a test that `savings_ratio: 0` still renders `0/100` in the breakdown and does NOT render the partial marker or helper text (distinguishes AC #3 from AC #2/#7).
  - [x] 10.3 Add a test that when `savings_ratio: null`, the ring renders the asterisk marker next to the score number, the "Partial score..." helper line is visible, and the SVG `aria-label` includes the partial qualifier.
  - [x] 10.4 Add a test that when all four breakdown components are non-null, the asterisk, helper line, and partial aria-label qualifier are all absent.
  - [x] 10.5 Verify existing ProfilePage tests still pass — the fixtures in `ProfilePage.test.tsx` use numeric `savings_ratio: 80` and `50`, which remain valid under the nullable type and should trigger the non-partial code path.

- [x] Task 11: End-to-end sanity (AC: #5)
  - [x] 11.1 Run the full backend test suite (`pytest`) and full frontend test suite (`npm test --run`) — confirm zero regressions. Document the new test count delta in Completion Notes.

### Review Follow-ups (AI)

- [ ] [AI-Review][LOW] i18n key `savingsRatioNoData` is used as a generic null-cell label inside `BREAKDOWN_KEYS.map` — safe today because only `savings_ratio` is nullable, but couples a generic fallback to a savings-specific key. Consider renaming to `breakdown.noData` or branching per-key if more components become nullable. [frontend/src/features/profile/components/HealthScoreRing.tsx:158-161]
- [ ] [AI-Review][LOW] `HealthScoreRing.test.tsx` partial-aria-label assertion uses a lowercase substring (`.toContain("partial")`). If en.json ever capitalizes the word, the test silently diverges. Prefer asserting the full translated string or a stable sentinel. [frontend/src/features/profile/__tests__/HealthScoreRing.test.tsx:164, :175]
- [~] [AI-Review][LOW] Asterisk marker uses `dominantBaseline="central"` where superscript convention would be `"hanging"` — withdrawn on review: visually indistinguishable at the chosen font sizes, not worth a code change. [frontend/src/features/profile/components/HealthScoreRing.tsx:110]

## Dev Notes

### Scope summary

- Full-stack, narrow: backend savings-ratio calculator swap + frontend null-state rendering.
- **No new migrations.** `transaction_kind` already exists on `transactions` (Story 11.2 shipped — see `backend/alembic/versions/w9x0y1z2a3b4_add_transaction_kind_to_transactions.py`), and the `breakdown` JSONB column on `financial_health_scores` accepts null values without schema change.
- **No new backend endpoint.** The existing `GET /api/v1/health-score` returns the stored breakdown dict as-is; null values flow through automatically.
- **No new profile aggregates.** We query transactions inside `_compute_breakdown` rather than adding a `kind_totals` column to `FinancialProfile` — see "Why not cache on profile" below.

### Architecture compliance

- **Database:** No schema changes. Relies on `transactions.transaction_kind` (VARCHAR(16), NOT NULL, default `'spending'`, CHECK constraint `IN ('spending','income','savings','transfer')`) landed by Story 11.2.
- **Backend patterns:** Calculation runs inside the Celery sync pipeline via `calculate_health_score(session, user_id)` called from `processing_tasks.py` (Story 4.5 Task 3). This story extends `_compute_breakdown` to accept `session, user_id` and issue a single `GROUP BY transaction_kind` query scoped to the profile's `[period_start, period_end]` window. Keep the function sync (SQLAlchemy `Session.exec`, not async) — the Celery worker is sync.
- **API response:** Untouched. The `breakdown` field is an opaque JSONB dict returned as-is; snake_case keys are preserved (confirmed by [types.ts:13](frontend/src/features/profile/types.ts#L13) matching backend keys directly). `null` serializes to JSON `null`.
- **Frontend patterns:** TanStack Query (`use-health-score.ts`) is untouched — it just passes through the nullable field. Component change is surgical: one branch in `HealthScoreRing.tsx`'s breakdown rendering.
- **i18n:** next-intl, nested keys under `profile.healthScore.breakdown.*`.
- **Currency:** N/A — savings ratio is a unitless ratio, rendered as integer 0–100.

### Why not cache `kind_totals` on the profile?

Tempting alternative: add a `kind_totals: dict[str, int]` JSONB column to `FinancialProfile` and populate it in `build_or_update_profile()` alongside `category_totals`. Rejected for this story because:

1. `_compute_breakdown` already has the `Session` handle (via `calculate_health_score`). One extra `GROUP BY` query is cheap and keeps the profile schema small.
2. Adding a profile column would require a migration and a backfill strategy — out of scope per AC #6 (greenfield assumption).
3. If a future story needs `kind_totals` client-side (e.g. a savings trendline in a later epic), **then** materialize it. Premature materialization now would be abstraction-for-its-own-sake — the kind of thing CLAUDE.md explicitly warns against.

If the dev finds a measurable performance issue with the per-call `GROUP BY` (unlikely — the query is indexed by `user_id` and scoped by date range), open a TD item rather than expand the scope of this story.

### Re-weighting when savings_ratio is null (AC #2, #7)

Current final-score formula:
```
final = 0.4 * savings + 0.2 * diversity + 0.2 * regularity + 0.2 * coverage
```
When `savings is None`, re-normalize over the remaining weights so the final score stays on a 0–100 scale:
```
final = (0.2 * diversity + 0.2 * regularity + 0.2 * coverage) / 0.6
```
This is equivalent to averaging the three non-null components. Implement via a generic `(score, weight)` list with a null filter so the logic extends cleanly if future stories null out other components. Do NOT treat `None` as `0` when summing — that would punish users for "no data" instead of being neutral about it.

**Important honesty constraint:** re-normalization hides the gap at the number level — a 72 computed from 3 components looks identical to a 72 from 4. To preserve user trust, AC #7 mandates a visible "partial" marker on the ring (asterisk + helper line) whenever `savings_ratio is null`. This is a UI-only signal — the persisted score is still a regular integer. The marker disappears automatically once the user has any `kind='income'` data in their period.

### Null vs. zero: the semantic distinction (AC #2 vs AC #3)

| Scenario | income_total | savings_total | savings_ratio | UI rendering |
|---|---|---|---|---|
| No income tagged | 0 | any | `None` | "Not enough data yet" |
| Income, no savings | >0 | 0 | `0` | "0/100" |
| Income > savings | >0 | >0, < income | int ∈ [1, 99] | "N/100" |
| Savings ≥ income (clamped) | >0 | ≥ income | `100` | "100/100" |

Do not collapse row 1 and row 2 into a single "empty" state — that loses information and misrepresents a user who has income but is spending everything.

### Previous Story Intelligence

**From Story 4.8 (Category Breakdown, done 2026-04-09):**
- Frontend pattern: new hooks go in `features/profile/hooks/use-*.ts`; new components in `features/profile/components/`; tests in `features/profile/__tests__/`. This story doesn't add a component or hook — only modifies `HealthScoreRing.tsx` and `types.ts`.
- i18n pattern: nested keys under `profile.*.breakdown` with matching uk.json translations. Always add both locales — the 4.8 review caught a missed Ukrainian string (raw English "uncategorized" leaked into uk UI).
- `formatCurrency()` in `features/profile/format.ts` exists but isn't needed here (ratio is unitless).

**From Story 4.5 (Health Score calculation, done):**
- `calculate_health_score(session, user_id)` is called from Celery sync worker inside `processing_tasks.py` at ~92% progress, wrapped in try/except so a failure doesn't fail the pipeline. Keep that contract intact — any exception from the new `GROUP BY` query must propagate up to the existing try/except, not be swallowed inside `_compute_breakdown`.
- The `breakdown` JSONB column stores arbitrary dict — snake_case keys, no Pydantic aliasing (confirmed by [types.ts:12](frontend/src/features/profile/types.ts#L12) comment "opaque dict, not aliased by Pydantic"). That means `null` values pass through transparently.
- `HealthScoreRing.tsx` uses `BREAKDOWN_KEYS` iteration to render all four components uniformly. The null branch will break uniformity — either special-case inside the `.map` or pull savings_ratio out and render separately.

**From Story 11.2 (transaction_kind field, done):**
- `transaction_kind` values: `'spending' | 'income' | 'savings' | 'transfer'` — CHECK constraint enforces it.
- Default value is `'spending'` — legacy rows and any uncategorized-at-ingestion rows will have this default. That's why AC #6 says "legacy users see Not enough data yet" — their rows say `'spending'` even for what was really salary, so `income_total = 0` → null savings_ratio. Correct behavior.
- Kind/category compatibility is validated at persistence — e.g. a row can't be `(kind='income', category='groceries')`. So the `GROUP BY kind` result reflects what was actually persisted, no re-validation needed here.

**From Story 11.3 (enriched prompt, done):**
- The LLM now emits `transaction_kind` per row; the MCC pass defaults to `'spending'`. So post-Epic-11 data will have meaningful kind distributions. Pre-Epic-11 data has all `'spending'` defaults.

### Git Intelligence (Recent Commits)

Recent commits (Epic 11 finale + Epic 4 mid-stream):
- `86a46c2` Bug fixes
- `676523e` Story 11.9: Observability Signals for Ingestion & Categorization
- `e2afaa2` Story 11.8: Low-Confidence Categorization Review Queue
- `565539f` Story 11.10: Counterparty-Aware Categorization for PE Account Statements
- `ad9e17b` Story 11.7: AI-Assisted Schema Detection

Pattern: Epic 11 has been the active focus. This story is the promised downstream wiring noted in epics.md:378 and 2131. No new dependencies added recently; stick to the existing stack (SQLModel, Pydantic, next-intl).

### Project Structure Notes

- Backend: `backend/app/services/health_score_service.py` (modify), `backend/tests/test_health_score_service.py` (extend), `backend/tests/test_health_score_api.py` (extend).
- Frontend: `frontend/src/features/profile/types.ts` (modify), `frontend/src/features/profile/components/HealthScoreRing.tsx` (modify), `frontend/src/features/profile/__tests__/HealthScoreRing.test.tsx` (extend), `frontend/messages/{en,uk}.json` (extend).
- Celery worker uses sync SQLAlchemy `Session`; keep `_compute_breakdown` sync.
- Python venv is at `backend/.venv` (not project root) — activate before running pytest locally.
- Frontend stack note from [frontend/AGENTS.md](frontend/AGENTS.md): **Next.js 16.1 has breaking changes from training-data Next.js**. Before touching any client component code, read the relevant doc in `node_modules/next/dist/docs/`. For this story the frontend change is minimal (one conditional + one translation), so the blast radius is small — but still consult the docs if anything in `HealthScoreRing.tsx`'s client-component patterns looks unfamiliar.

### Testing standards

- Backend: `pytest` with SQLModel in-memory fixtures. The existing `test_health_score_service.py` has a fixture pattern for inserting transactions — extend it with a `kind` parameter rather than writing a parallel helper.
- Frontend: Vitest + Testing Library, colocated in `__tests__/`. Mock `next-intl` as the existing tests do (see `HealthScoreRing.test.tsx` for pattern).
- Zero regressions: all existing backend (~328) and frontend (~249) tests must still pass. Any pre-existing test that asserted on `savings_ratio` as a number must be updated to set `transaction_kind` explicitly on fixture transactions — the old income/expense math no longer drives the score.

### References

- [Source: backend/app/services/health_score_service.py](backend/app/services/health_score_service.py) — current calculator to modify
- [Source: backend/app/models/transaction.py:31](backend/app/models/transaction.py#L31) — `transaction_kind` field definition
- [Source: backend/app/services/profile_service.py:12-18](backend/app/services/profile_service.py#L12-L18) — `build_or_update_profile` (NOT modified by this story; referenced for profile-period context)
- [Source: backend/app/models/financial_profile.py] — `period_start`/`period_end` fields used to scope the kind query
- [Source: backend/alembic/versions/w9x0y1z2a3b4_add_transaction_kind_to_transactions.py] — migration that introduced `transaction_kind`
- [Source: backend/app/agents/categorization/node.py] — where `transaction_kind` is assigned during categorization (context only; no change here)
- [Source: frontend/src/features/profile/types.ts:13](frontend/src/features/profile/types.ts#L13) — `HealthScoreBreakdown.savings_ratio` type to make nullable
- [Source: frontend/src/features/profile/components/HealthScoreRing.tsx:125-136](frontend/src/features/profile/components/HealthScoreRing.tsx#L125-L136) — breakdown rendering block to update
- [Source: _bmad-output/planning-artifacts/epics.md:1242-1277](_bmad-output/planning-artifacts/epics.md#L1242-L1277) — original story requirements
- [Source: _bmad-output/planning-artifacts/epics.md:2131](_bmad-output/planning-artifacts/epics.md#L2131) — Epic 11 cross-epic consumer note
- [Source: _bmad-output/planning-artifacts/tech-spec-ingestion-categorization.md] — tech spec §2.1, §2.3 (kind field + compatibility matrix)
- [Source: _bmad-output/implementation-artifacts/11-2-transaction-kind-field-expanded-category-taxonomy.md] — Story 11.2 prior art
- [Source: _bmad-output/implementation-artifacts/4-5-financial-health-score-calculation-display.md] — Story 4.5 prior art (original savings ratio formula)
- [Source: _bmad-output/implementation-artifacts/4-8-category-spending-breakdown.md] — Story 4.8 prior art (frontend pattern reference)

### Resolved decisions (formerly open)

- **Partial-score indicator on the ring (AC #7) — resolved 2026-04-22:** chose option (b) — render a visible asterisk + "Partial score — savings data not yet available" helper when `savings_ratio is null`. Rationale: re-normalization alone made the final number indistinguishable from a complete 4-component score, which is slightly dishonest. The marker is small, dismissible as the user's data grows, and keeps the score signal trustworthy. Implementation lives in Task 8.
- **Period scoping on empty profile — resolved 2026-04-22:** when `profile.period_start` or `profile.period_end` is `None` (empty/new profile), short-circuit `savings_score` to `None` without issuing the `GROUP BY` query. Aligns with the "no data" semantics of AC #2 and matches how the other three components already behave on empty profiles. Folded into Task 1.3.

## Dev Agent Record

### Agent Model Used

Claude Opus 4.7 (1M context)

### Debug Log References

- Backend suite: `pytest` → 817 passed, 9 deselected (2026-04-22).
- Frontend suite: `npm test --run` → 52 files, 496 passed (2026-04-22).
- TypeScript noEmit reported 4 pre-existing errors (unrelated — verified via `git stash`).

### Completion Notes List

- **Calculator rewrite:** `_compute_breakdown` now takes `(session, user_id, profile)` and issues a single `SELECT transaction_kind, SUM(ABS(amount)) ... GROUP BY transaction_kind` scoped to `[profile.period_start, profile.period_end]`. No category/sign/MCC inference remains (AC #4).
- **Null semantics:** `savings_ratio` is `int | None`. `None` means "no income-kind entries" (AC #2); `0` means "income present, no savings" (AC #3). The weighted-average final score drops null components and re-normalizes over the remaining weights, keeping the partial score on a 0–100 scale.
- **Empty-profile short-circuit:** if `period_start` or `period_end` is `None`, the service skips the query and returns `savings_ratio = None` — matches "no data" semantics of AC #2.
- **aria-label choice (Task 8.4):** used a dedicated `ariaLabelPartial` key (vs ICU `select`) to keep `en.json`/`uk.json` flat, mirroring the existing `showBreakdown`/`hideBreakdown` pair.
- **Partial marker:** SVG `<text>` asterisk positioned via `dx` offset to the top-right of the score number with `opacity-60` and `data-testid="partial-score-marker"`; muted helper `<p>` renders between the ring and the breakdown toggle.
- **Test fixture migration:** `test_balanced_profile`, `test_overspending_profile`, `test_high_savings_ratio`, `test_zero_income`, `test_breakdown_contains_all_components`, `test_score_is_appended_not_replaced` now create an `Upload` + `Transaction` rows with explicit `transaction_kind`. Legacy profile-sum math no longer drives the score.
- **No migration, no profile column added** (Dev Notes §"Why not cache on profile").

### File List

- backend/app/services/health_score_service.py
- backend/tests/test_health_score_service.py
- backend/tests/test_health_score_api.py
- frontend/src/features/profile/types.ts
- frontend/src/features/profile/components/HealthScoreRing.tsx
- frontend/src/features/profile/__tests__/HealthScoreRing.test.tsx
- frontend/messages/en.json
- frontend/messages/uk.json
- VERSION
- docs/tech-debt.md
- _bmad-output/implementation-artifacts/sprint-status.yaml
- _bmad-output/implementation-artifacts/4-9-savings-ratio-wired-to-transaction-kind.md

### Change Log

- 2026-04-22 — Story 4.9: Savings Ratio rewired to `transaction_kind`. Adds null sentinel (`savings_ratio: int | None`), re-normalized final score, and a partial-score marker + helper line. 3 new i18n strings (en + uk). 7 new backend tests, 4 new frontend tests; 6 existing backend tests migrated to kind-aware fixtures. Version bumped 1.27.1 → 1.28.0 (new user-facing "Not enough data yet" state + partial marker).
- 2026-04-22 — Code review fixes: asterisk marker `dx` switched from `"1.25rem"` (unreliable SVG unit) to numeric `20` (px). Final-score computation now uses `int(round(...))` instead of truncation, aligning with how `savings_score` is rounded (`_compute_breakdown`). Return type of `_compute_breakdown` narrowed from `dict[str, Any]` to `dict[str, int | None]`; `typing.Any` import dropped. Test `test_no_income_returns_null` updated to match rounded final score. Observability gap on the new `GROUP BY transaction_kind` query promoted to [TD-066](../../../docs/tech-debt.md). Two LOW findings kept story-local under Review Follow-ups (AI). Status → done.
