# Story 11.8: Low-Confidence Categorization Review Queue

Status: done

<!-- Sourced from: epics.md Epic 11 / tech-spec-ingestion-categorization.md §2.5, §3.1 (Stage D), §8. -->
<!-- Depends on: Story 11.3/11.3a/11.4/11.10 (categorization pipeline emits per-row confidence + kind), Story 11.2 (kind × category compatibility matrix), Story 6.3 (uncategorized-transaction flagging on `transactions` — this story layers a structured review queue on top, it does NOT replace Story 6.3's `uncategorized_reason` column). -->

## Story

As a **user**,
I want transactions the system wasn't confident about categorizing to surface in a dedicated review queue with the model's best guess,
So that I can correct them in one place and the pipeline stops silently marking confidently-wrong rows as "uncategorized" without giving me a path to fix them.

**Why now:** The pipeline today uses a single `CATEGORIZATION_CONFIDENCE_THRESHOLD = 0.7` — anything below becomes `category='uncategorized'` + `uncategorized_reason='low_confidence'` (Story 6.3 plumbing). That's too coarse: a 0.65-confidence "shopping" guess is far more useful to the user than a blanket "uncategorized" label, but a 0.3-confidence guess is noise. Tech spec §3.1 Stage D defines the three-tier policy (`≥0.85` silent auto-apply, `0.6–0.85` auto-apply + soft-flag event, `<0.6` queue insert + `category='uncategorized'`) and §2.5 defines the queue schema. This story wires both into the persist path and ships the API + minimal UI so users can resolve or dismiss queue entries.

**Scope philosophy:** Single story — schema, pipeline threshold split, API, minimal settings-level UI, and observability hook-up (the `categorization.confidence_tier` event also mentioned in Story 11.9 §9 is **emitted here** so Stage D has telemetry from day one; Story 11.9 consumes it into dashboards and adds its remaining events). Per tech spec §8.2, the UI is settings-level only and is NOT surfaced in the Teaching Feed — keep the feed card-driven and uncontaminated by review-queue housekeeping.

## Acceptance Criteria

1. **Given** a new Alembic migration **When** applied **Then** the `uncategorized_review_queue` table exists exactly per tech spec §2.5: `id UUID PRIMARY KEY DEFAULT gen_random_uuid()`, `user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE`, `transaction_id UUID NOT NULL REFERENCES transactions(id) ON DELETE CASCADE`, `categorization_confidence REAL NOT NULL`, `suggested_category VARCHAR(32)` (nullable), `suggested_kind VARCHAR(16)` (nullable), `status VARCHAR(16) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','resolved','dismissed'))`, `created_at TIMESTAMPTZ NOT NULL DEFAULT now()`, `resolved_at TIMESTAMPTZ`, `resolved_category VARCHAR(32)`, `resolved_kind VARCHAR(16)`. Index `ix_uncat_queue_user_status ON (user_id, status)`. Parent revision resolved via `alembic heads` at implementation time (y1z2a3b4c5d6 was the most recent head at story draft time; confirm before creating the migration).

2. **Given** the categorization pipeline in [backend/app/agents/categorization/node.py](../../backend/app/agents/categorization/node.py) **When** the post-LLM threshold loop runs **Then** it implements the three-tier Stage D policy from tech spec §3.1 in place of the current single-threshold `confidence < CATEGORIZATION_CONFIDENCE_THRESHOLD → flagged + category='uncategorized'` behavior:
   - `confidence_score ≥ 0.85` → row passes through as-is; `flagged=False`; no telemetry event.
   - `0.6 ≤ confidence_score < 0.85` → row passes through with its LLM-suggested `category` and `transaction_kind` intact (NOT rewritten to `uncategorized`); `flagged=False`; `categorization.confidence_tier` event emitted with `tier="soft-flag"`.
   - `confidence_score < 0.6` → `flagged=True`, `category="uncategorized"`, `uncategorized_reason="low_confidence"` (unchanged from Story 6.3), AND the original LLM suggestion is carried on the row dict as `suggested_category` / `suggested_kind` so the persist path (AC #4) can insert it into the queue. `categorization.confidence_tier` event emitted with `tier="queue"`.
   Deterministic-rule rows (Story 11.10 Rule 5/6 sentinel) continue to skip threshold gating per the existing carve-out — they never enter the queue regardless of confidence.

3. **Given** a transaction produced by the pre-pass (Story 11.4 / Pass 0), the MCC pass (Pass 1), or a deterministic LLM-result rule **When** the threshold loop evaluates it **Then** its high-confidence stamp (0.95+) means it naturally skips queue insertion — no special casing needed. The pipeline's existing invariant "Pass 0 and Pass 1 emit confidence_score ≥ 0.95" is load-bearing here and is asserted by a unit test to prevent future regressions (a pre-pass rule dropping below 0.85 would silently flood the soft-flag telemetry).

4. **Given** the transaction-persist path in [backend/app/tasks/processing_tasks.py](../../backend/app/tasks/processing_tasks.py) (both `_persist_transactions` at line ~272 and its sibling path at line ~720) **When** a transaction row has `flagged=True` with `uncategorized_reason="low_confidence"` AND non-null `suggested_category` / `suggested_kind` **Then** after the transaction row is flushed (so `transaction_id` is available as an FK), an `uncategorized_review_queue` row is inserted for the same user with `categorization_confidence = <original_confidence_score>`, `suggested_category`, `suggested_kind`, `status='pending'`. If `suggested_category` is absent (e.g. `uncategorized_reason="llm_unavailable"` or `"parse_failure"`) the row is NOT queued — those are infrastructure failures, not low-confidence decisions, and users cannot usefully resolve them. Insertions are batched (one `session.flush()` at end of the batch) to avoid N+1.

5. **Given** the new service module [backend/app/services/review_queue_service.py](../../backend/app/services/review_queue_service.py) (new file) **When** it exposes the queue operations **Then** it provides:
   - `list_pending(user_id, limit=50, cursor=None) -> PaginatedQueueResult` — returns entries joined to their transaction (description, amount, date) ordered by `transactions.date DESC, uncategorized_review_queue.created_at DESC`, cursor-paginated using the same cursor shape as `transaction_service.get_transactions_for_user` (keyset pagination, not offset).
   - `resolve(user_id, entry_id, category, kind) -> QueueEntry` — validates `(kind, category)` against the compatibility matrix in [backend/app/agents/categorization/mcc_mapping.py](../../backend/app/agents/categorization/mcc_mapping.py) via `validate_kind_category(kind, category)` (the same helper used in node.py). Invalid → raises `KindCategoryMismatchError` (new exception mapped to HTTP 400 by the router). Valid → updates the underlying `transactions` row (`category=<resolved>`, `transaction_kind=<resolved>`, `flagged=False`, `uncategorized_reason=None`, `confidence_score=1.0` — user correction is ground truth), updates the queue row (`status='resolved'`, `resolved_at=now()`, `resolved_category`, `resolved_kind`). Both writes in one transaction.
   - `dismiss(user_id, entry_id, reason=None) -> QueueEntry` — sets `status='dismissed'` on the queue row; the transaction stays as-is (`category='uncategorized'`, `flagged=True`). Optional `reason` is logged but not persisted in the schema (no column for it per tech spec §2.5; if observability needs it long-term, a later story can add a column).
   - `count_pending(user_id) -> int` — fast count for the settings-page badge (AC #9).
   All methods enforce per-user isolation: a `entry_id` belonging to a different user returns `QueueEntryNotFoundError` (HTTP 404), never a 403 — prevent ID-probing.

6. **Given** a new API router [backend/app/api/v1/review_queue.py](../../backend/app/api/v1/review_queue.py) (new file) registered under the existing `/api/v1/transactions` prefix **When** it is mounted **Then** it exposes the three endpoints from tech spec §8.1:
   - `GET /api/v1/transactions/review-queue?status=pending&limit=50&cursor=…` → paginated response. `status` accepts `pending` (default), `resolved`, `dismissed`; non-pending statuses are included so users can undo a dismiss if a follow-up story adds an undo action, but are not tested beyond a smoke test this iteration. Each list item includes: `id`, `transaction_id`, `description`, `amount`, `date`, `suggested_category`, `suggested_kind`, `categorization_confidence`, `created_at`, `status`.
   - `POST /api/v1/transactions/review-queue/{id}/resolve` with body `{category, kind}` → 200 with the updated entry, or 400 on matrix violation, or 404 on cross-user access / missing entry.
   - `POST /api/v1/transactions/review-queue/{id}/dismiss` with optional body `{reason}` → 200 with the updated entry, or 404 on cross-user access / missing entry.
   All endpoints require authentication via `get_current_user_id` (same pattern as `transactions.py`). Response DTOs use the camelCase alias pattern consistent with [backend/app/api/v1/transactions.py](../../backend/app/api/v1/transactions.py) (`ConfigDict(alias_generator=to_camel, populate_by_name=True)`). Router is registered in [backend/app/api/v1/router.py](../../backend/app/api/v1/router.py).

7. **Given** the pipeline emits `categorization.confidence_tier` structured log events at the two non-silent tiers (AC #2) **When** each event fires **Then** it carries the fields defined in tech spec §9: `tier` (`"soft-flag"` or `"queue"`), `user_id`, `upload_id`, `tx_id` (the transaction UUID), `confidence` (the raw float), plus the existing correlation IDs (`job_id`) from Story 6.4. Event is emitted at the point the threshold decision is made (inside the post-LLM loop in node.py), NOT at persist time — decoupling keeps the telemetry meaningful even if a later persist failure rolls back the row. The `tier="auto"` case emits no event (silent is silent — no logging storm on happy path).

8. **Given** the frontend settings page [frontend/src/features/settings/components/SettingsPage.tsx](../../frontend/src/features/settings/components/SettingsPage.tsx) **When** the user opens `/settings` and `review_queue.count_pending > 0` **Then** a new `<ReviewQueueSection>` component renders between `<MyDataSection>` and `<DataDeletion>` showing a copy like "Review uncategorized transactions (N)" and a Next.js `<Link>` to `/settings/review-queue`. When the count is zero, the section is hidden entirely (not greyed out, not "0 pending" — absent). The count is fetched via a new SWR hook `useReviewQueueCount` that calls a new `/api/v1/transactions/review-queue/count` endpoint (thin wrapper on `count_pending`) — the list endpoint is NOT called on the settings page just for a count (N could be large).

9. **Given** a new page route [frontend/src/app/\[locale\]/(dashboard)/settings/review-queue/page.tsx](../../frontend/src/app/[locale]/(dashboard)/settings/review-queue/page.tsx) **When** the user navigates to `/settings/review-queue` **Then** it renders a `<ReviewQueuePage>` client component under `frontend/src/features/settings/components/` (or a new `frontend/src/features/review-queue/` feature folder if the settings folder is already cluttered — implementer's judgment). The page:
   - Fetches pending entries via SWR paginated through the cursor.
   - Lists each entry with: transaction date (localized), description, signed amount (UAH default; currency-aware if the transaction has non-UAH currency), the suggested category (localized via existing i18n catalog — Story 11.2 introduced category keys), the suggested kind, confidence displayed as a small percentage badge ("62%").
   - Renders two primary actions per row: `Resolve` (opens an inline editor letting the user pick category + kind from the same dropdowns the rest of the app uses — reuse existing category-select component if one exists under `frontend/src/features`; if not, a minimal `<select>` is acceptable for this iteration, documented as tech-debt if so) and `Dismiss` (one-click, no confirm dialog — dismissal is reversible via a future undo story; aggressive confirmation here just slows down power users cleaning out noise).
   - On successful resolve/dismiss: optimistic update + SWR revalidate; on matrix-violation 400: show the error message inline on the row (not as a toast).
   - i18n: all copy goes through next-intl via new keys under `settings.reviewQueue.*` (English + Ukrainian). No hard-coded strings.

10. **Given** observability at the `tier="queue"` boundary **When** a row is inserted into the queue **Then** a second structured log event `categorization.review_queue_insert` is emitted at persist time (inside `processing_tasks.py`, not node.py) with `{upload_id, user_id, transaction_id, categorization_confidence, suggested_category, suggested_kind}`. This is separate from the `confidence_tier` event in AC #7 — that one fires at decision time regardless of whether persist succeeds; this one fires only on successful insert. Both events share the same `job_id` correlation ID for join-ability in Grafana.

11. **Given** backend unit test coverage **When** Story 11.8 is reviewed **Then** these tests exist and pass:
    - `backend/tests/agents/categorization/test_threshold_tiers.py` — three-tier routing: `≥0.85` returns untouched; `0.6–0.85` preserves category, emits soft-flag event, does NOT set `flagged=True`; `<0.6` sets `flagged=True`, `category='uncategorized'`, attaches `suggested_category`/`suggested_kind`, emits queue event; deterministic-rule sentinel skips gating at any confidence.
    - `backend/tests/services/test_review_queue_service.py` — `list_pending` returns joined transaction context, cursor paginates correctly, cross-user entries excluded; `resolve` updates both tables in one transaction, matrix violation raises, confidence is bumped to 1.0; `dismiss` only touches queue row; `count_pending` is O(1) on index.
    - `backend/tests/api/test_review_queue_api.py` — all three endpoints: auth required (401 without token); cross-user 404 (not 403); matrix violation 400; happy paths 200 with camelCase DTOs; pagination cursor roundtrips.
    - `backend/tests/tasks/test_persist_queue_insert.py` — persist path correctly inserts queue rows for `low_confidence` flagged transactions with suggestions, skips them for `llm_unavailable` / `parse_failure` (no suggestions), batches flushes.

12. **Given** frontend unit test coverage **When** Story 11.8 is reviewed **Then** these tests exist and pass:
    - `frontend/src/features/settings/components/__tests__/ReviewQueueSection.test.tsx` — hides when count is 0; renders count + link when > 0.
    - `frontend/src/features/.../__tests__/ReviewQueuePage.test.tsx` (location matches AC #9 placement) — renders pending entries, resolve updates optimistically, dismiss removes row, matrix-violation 400 shows inline error, confidence badge displays percentage rounded to whole percent.

13. **Given** integration test coverage **When** Story 11.8 is reviewed **Then** one end-to-end test exists (`@pytest.mark.integration`, real LLM or canned stub) in `backend/tests/integration/test_review_queue_e2e.py`:
    - Upload a small fixture whose processing produces at least one row per tier (use forced-low-confidence via test-only config override to ensure determinism — e.g. monkey-patch `CATEGORIZATION_CONFIDENCE_THRESHOLD`-replacement constants or inject canned LLM responses).
    - Assert DB state: pending queue entries equal expected count; soft-flag rows were auto-applied with their LLM categories; high-confidence rows are untouched.
    - Call `GET /api/v1/transactions/review-queue` → expected entries present.
    - Call `resolve` on one entry → DB shows transaction updated, queue row status=resolved.
    - Call `dismiss` on another → transaction unchanged, queue row status=dismissed.

14. **Given** golden-set regression safety **When** the harness runs post-11.8 **Then** category/kind accuracy on the golden set (Story 11.1) does not regress. The three-tier threshold change could shift some borderline rows from `"uncategorized"` (old single-threshold behavior at 0.6–0.7) to their LLM-suggested category (new soft-flag behavior) — this is an accuracy **improvement** opportunity. Record the delta in the story's Change Log; if `category_accuracy` rises, no action needed; if it falls, debug via the confidence distribution before merging.

15. **Given** backward compatibility with Story 6.3 (`/api/v1/transactions/flagged` endpoint and the `uncategorized_reason` column) **When** Story 11.8 lands **Then** the `/flagged` endpoint is UNCHANGED in behavior — it still lists all transactions with `flagged=True` regardless of whether they have a queue entry. The two lists overlap but serve different audiences: `/flagged` is operator-oriented (all flagged-for-any-reason rows including `llm_unavailable`, `parse_failure`, `currency_unknown`); `/review-queue` is user-oriented (actionable low-confidence suggestions only). Document this distinction in the OpenAPI descriptions of both endpoints.

16. **Given** the config change **When** Story 11.8 lands **Then** `CATEGORIZATION_CONFIDENCE_THRESHOLD` in [backend/app/core/config.py](../../backend/app/core/config.py) is replaced by TWO settings: `CATEGORIZATION_SOFT_FLAG_THRESHOLD: float = 0.6` and `CATEGORIZATION_AUTO_APPLY_THRESHOLD: float = 0.85`. The old name is REMOVED (no shim — single call-site in node.py, trivially swept). `.env.example` is updated. Any test that referenced the old constant is updated in the same PR (grep first).

17. **Given** existing flagged transactions from before Story 11.8 **When** the migration runs **Then** no backfill is performed — pre-existing `category='uncategorized'`/`flagged=True` rows remain as they are, with no queue entries. Users who already have historical low-confidence flags see them only via the Story 6.3 `/flagged` path until those transactions get re-categorized (out of scope for this story; a future "re-run categorization" feature would backfill). Document this in the story's Dev Notes.

## Tasks / Subtasks

- [x] **Task 1: Alembic migration for `uncategorized_review_queue`** (AC: #1)
  - [x] 1.1 Run `alembic heads` in backend to identify the current head; set `down_revision` accordingly.
  - [x] 1.2 Create migration `backend/alembic/versions/<rev>_add_uncategorized_review_queue.py` with `upgrade()` and `downgrade()` per AC #1 schema. Include the index.
  - [x] 1.3 Apply locally; `\d uncategorized_review_queue` in psql should match AC #1 exactly. Run existing test suite to ensure no regressions.

- [x] **Task 2: Model + service for the review queue** (AC: #5, #11)
  - [x] 2.1 Create SQLAlchemy/SQLModel model `backend/app/models/uncategorized_review_queue.py`. Register in `backend/app/models/__init__.py` (mirror the pattern used by `user_iban_registry.py` from Story 11.10).
  - [x] 2.2 Create `backend/app/services/review_queue_service.py` with the four methods in AC #5. Define `KindCategoryMismatchError` and `QueueEntryNotFoundError` as local exceptions (not global) — the router maps them to HTTP.
  - [x] 2.3 `list_pending` uses keyset pagination mirroring `transaction_service.get_transactions_for_user`'s cursor shape. Re-use the existing cursor helper if one exists; otherwise document the cursor format inline.
  - [x] 2.4 `resolve` performs both table writes inside a single SQLAlchemy session transaction; use `session.begin_nested()` if the caller already has a session open (router's `get_db` dependency).
  - [x] 2.5 Unit tests per AC #11 item 2.

- [x] **Task 3: Three-tier threshold routing in categorization node** (AC: #2, #3, #7, #11, #16)
  - [x] 3.1 Replace config constant (AC #16) in `backend/app/core/config.py` + `.env.example`. Grep the repo for `CATEGORIZATION_CONFIDENCE_THRESHOLD` — update all call sites (expected: one in `node.py`, possibly tests).
  - [x] 3.2 Edit the threshold loop at [backend/app/agents/categorization/node.py:571-585](../../backend/app/agents/categorization/node.py#L571-L585) to implement the three-tier policy per AC #2. Attach `suggested_category` / `suggested_kind` to the row dict when sending to the queue tier. Preserve the Story 11.10 `deterministic_rule` carve-out.
  - [x] 3.3 Emit `categorization.confidence_tier` structured logs per AC #7. Use the existing project logger (`logger.info` with a `extra={...}` dict, matching the conventions elsewhere in node.py).
  - [x] 3.4 Unit tests per AC #11 item 1. Include the assertion in AC #3 that Pass 0 and Pass 1 always emit `confidence_score ≥ 0.95` (pin behavior — new contributors can't drop a pre-pass rule to 0.7 accidentally).

- [x] **Task 4: Persist-path queue insertion** (AC: #4, #10, #11)
  - [x] 4.1 Edit both persist paths in [backend/app/tasks/processing_tasks.py](../../backend/app/tasks/processing_tasks.py) (~line 272 and ~line 720). After the transaction row is added to the session, if the row meets AC #4 criteria, construct an `UncategorizedReviewQueue` instance and `session.add()` it. Batch: one `flush()` after the full batch loop, not per row.
  - [x] 4.2 Emit `categorization.review_queue_insert` per AC #10 after the flush succeeds — not before (failures shouldn't pollute telemetry).
  - [x] 4.3 Unit tests per AC #11 item 4: mock the LLM output, verify queue row count after processing.

- [x] **Task 5: API router** (AC: #6, #11)
  - [x] 5.1 Create `backend/app/api/v1/review_queue.py`. Define Pydantic DTOs with camelCase aliases. Implement the three endpoints from AC #6 plus the `count` sub-endpoint for AC #8.
  - [x] 5.2 Register the router in `backend/app/api/v1/router.py` (same mount pattern as existing routers). Since the prefix is `/transactions`, decide: either nest under the existing transactions router (cleaner OpenAPI grouping) or mount separately with the full prefix. Recommendation: mount as its own router with `prefix="/transactions/review-queue"` to keep review-queue code isolated from the generic transaction endpoints.
  - [x] 5.3 Map `KindCategoryMismatchError → 400`, `QueueEntryNotFoundError → 404` via exception handlers local to the router (not app-level).
  - [x] 5.4 Update `/flagged` endpoint's OpenAPI description to contrast with `/review-queue` per AC #15 (single-line description update, not a behavior change).
  - [x] 5.5 API tests per AC #11 item 3.

- [x] **Task 6: Frontend settings badge link** (AC: #8, #12)
  - [x] 6.1 Create SWR hook `frontend/src/features/settings/hooks/use-review-queue-count.ts` that calls `/api/v1/transactions/review-queue/count`.
  - [x] 6.2 Create `frontend/src/features/settings/components/ReviewQueueSection.tsx` — hides when count is 0 per AC #8. Use `next/link` (NOT `<a>`).
  - [x] 6.3 Insert into `SettingsPage.tsx` between `<MyDataSection />` and `<DataDeletion />`.
  - [x] 6.4 Add i18n keys under `settings.reviewQueue.*` for English and Ukrainian (mirror existing i18n file layout — see Story 1.6 for the pattern).
  - [x] 6.5 Vitest/React Testing Library tests per AC #12 item 1.

- [x] **Task 7: Frontend review-queue page** (AC: #9, #12)
  - [x] 7.1 Create the route `frontend/src/app/[locale]/(dashboard)/settings/review-queue/page.tsx` that renders the feature component. Route sits inside the existing `(dashboard)` group so the dashboard shell (header, nav) wraps it.
  - [x] 7.2 Create the feature component (location per AC #9). Include SWR pagination, signed-amount formatting (reuse existing currency-format util — grep for `formatAmount` or equivalent under `frontend/src/lib/`), category i18n.
  - [x] 7.3 Resolve editor: reuse existing category-picker if one exists; otherwise ship a minimal native `<select>` and file TD-<NNN> for a later polish pass. Document the decision in the story Dev Notes.
  - [x] 7.4 Optimistic update + SWR revalidate on resolve/dismiss. Inline error rendering for 400 responses.
  - [x] 7.5 Vitest/RTL tests per AC #12 item 2.

- [x] **Task 8: Integration E2E test** (AC: #13)
  - [x] 8.1 Create `backend/tests/integration/test_review_queue_e2e.py` gated by `@pytest.mark.integration`.
  - [x] 8.2 Use canned LLM responses (monkey-patch `get_llm_client` / `get_fallback_llm_client` to return deterministic JSON with known confidence values per tier). This keeps the test reproducible on CI without real Anthropic credentials.
  - [x] 8.3 Assertions per AC #13.

- [x] **Task 9: Golden-set regression check** (AC: #14)
  - [x] 9.1 Run the golden-set harness locally post-implementation. Capture the `category_accuracy` / `kind_accuracy` delta in the story Change Log.
  - [x] 9.2 If either axis drops below the Story 11.10 / 11.4 ratchet (both must stay ≥ 0.92 on the unified set per Story 11.10 AC #12), investigate — the most likely cause is a soft-flag row now claiming a category it didn't previously (because the old path forced it to `uncategorized`). Decide: is the new label actually wrong (→ raise `CATEGORIZATION_SOFT_FLAG_THRESHOLD` until the regression clears) or is the golden-set label itself stale (→ relabel with an explicit retrospective note).

- [x] **Task 10: Sprint status + docs**
  - [x] 10.1 On story completion, flip `_bmad-output/implementation-artifacts/sprint-status.yaml` entry `11-8-low-confidence-categorization-review-queue` from `ready-for-dev` → `in-progress` → `review` → `done` per normal BMAD flow.
  - [x] 10.2 Version bump in `VERSION` if the feature is user-facing per project convention (it is — settings link + new page → minor bump).

## Dev Notes

### Relationship to Story 6.3 (`flagged` + `uncategorized_reason`)

Story 6.3 introduced operator-facing flagging: any row the pipeline couldn't confidently categorize for ANY reason (`low_confidence`, `parse_failure`, `llm_unavailable`, `currency_unknown`) gets `flagged=True` + a `uncategorized_reason` tag + category forced to `"uncategorized"`. That stays. Story 11.8 narrows in on the `low_confidence` subset and gives users an actionable UX.

The overlap:

- A transaction with `uncategorized_reason="low_confidence"` has BOTH a `flagged` marker on itself AND a `uncategorized_review_queue` row.
- A transaction with `uncategorized_reason="llm_unavailable"` has ONLY the flagged marker; no queue entry (nothing to suggest — resolving requires the user to pick from scratch, and we don't currently offer an arbitrary re-categorize UI on flagged rows outside the queue path).

Why not extend `/flagged` instead of shipping a separate endpoint? Because the queue has fundamentally different data (`suggested_category`, `suggested_kind`, `categorization_confidence`, `status` lifecycle). Attaching these to `flagged` pollutes its contract for the majority of flagged rows where they're `null`. The two endpoints will likely converge in a future UX iteration, but today separating them is cheaper than retrofitting `/flagged` with optional fields.

### Why the soft-flag tier doesn't mark `flagged=True`

Old behavior: a 0.65-confidence "shopping" guess landed in `transactions` as `category="uncategorized"`, `flagged=True`, `uncategorized_reason="low_confidence"` — completely hiding the model's actual guess from downstream consumers (Health Score, Category Breakdown, Teaching Feed). That's a lot of information thrown away to protect against a model that's wrong ~35% of the time on those rows.

New behavior: auto-apply the suggestion. Downstream consumers see `category="shopping"` immediately. The `confidence_tier="soft-flag"` telemetry event is the escape hatch — if operator dashboards show the aggregate soft-flag accuracy is poor, we can raise `CATEGORIZATION_SOFT_FLAG_THRESHOLD` from 0.6 toward 0.7/0.8 without a code change. This is a measurement-first decision per Epic 11's overall philosophy (golden-set + observability drive thresholds; we don't guess at them).

### Why matrix validation happens at resolve time (not earlier)

Users pick `(category, kind)` from UI dropdowns that already constrain to valid enum values (per Story 11.2). But the compatibility matrix (`kind × category` — §2.3) is stricter than the enum cross-product: e.g., `kind="income"` with `category="groceries"` is enum-valid but matrix-invalid. The UI COULD enforce this client-side, but the backend MUST enforce it regardless — clients lie. The frontend surfacing inline error on 400 (AC #9) is UX polish; the real guard is the service-layer validation.

### Why dismiss is one-click

The typical volume of dismissals will be "I looked at this row and decided I don't care" — not "I'm making an irreversible business decision." A confirm dialog on every dismiss multiplies the friction on the user's most common action by 2–3×. Resolve is already a two-step interaction (pick category + kind, submit); dismiss being one-click balances the UX. If users report accidental dismissals, a future undo (restore from `status='dismissed'` back to `status='pending'`) is cheap — the data is still there.

### Pipeline-stage confidence invariants

To avoid the soft-flag / queue telemetry flooding with noise from non-LLM stages, the following are invariants:

- Pass 0 (description pre-pass, Story 11.4): always emits `confidence_score = 0.95`. Asserted in `test_pre_pass.py` (extend if the assertion isn't already there).
- Pass 1 (MCC pass): always emits `confidence_score = 0.95`. Asserted in `test_mcc_mapping.py` or node-level tests.
- Pass 2 (LLM): full [0.0, 1.0] range.
- Deterministic-rule sentinel rows (Story 11.10 Rule 5/6): confidence ≥ 0.98 by construction; skip threshold gating entirely.

A new test `test_confidence_invariants.py` (or additions to existing node tests) pins these so a future contributor can't silently drop a pre-pass rule's confidence to 0.7 and accidentally start sending the cash-action pattern into the queue.

### Project Structure Notes

**New files:**

- `backend/alembic/versions/<rev>_add_uncategorized_review_queue.py`
- `backend/app/models/uncategorized_review_queue.py`
- `backend/app/services/review_queue_service.py`
- `backend/app/api/v1/review_queue.py`
- `backend/tests/agents/categorization/test_threshold_tiers.py`
- `backend/tests/services/test_review_queue_service.py`
- `backend/tests/api/test_review_queue_api.py`
- `backend/tests/tasks/test_persist_queue_insert.py`
- `backend/tests/integration/test_review_queue_e2e.py`
- `frontend/src/features/settings/components/ReviewQueueSection.tsx`
- `frontend/src/features/settings/hooks/use-review-queue-count.ts`
- `frontend/src/features/settings/components/__tests__/ReviewQueueSection.test.tsx`
- `frontend/src/app/[locale]/(dashboard)/settings/review-queue/page.tsx`
- `frontend/src/features/.../ReviewQueuePage.tsx` + tests (exact path per Task 7.2)

**Modified files:**

- `backend/app/core/config.py` — replace `CATEGORIZATION_CONFIDENCE_THRESHOLD` with `*_SOFT_FLAG_THRESHOLD` + `*_AUTO_APPLY_THRESHOLD`
- `backend/.env.example` — mirror the new settings
- `backend/app/agents/categorization/node.py` — three-tier threshold loop
- `backend/app/tasks/processing_tasks.py` — queue-insert hook in both persist paths
- `backend/app/models/__init__.py` — register `UncategorizedReviewQueue`
- `backend/app/api/v1/router.py` — mount new router
- `backend/app/api/v1/transactions.py` — OpenAPI description tweak on `/flagged` per AC #15
- `frontend/src/features/settings/components/SettingsPage.tsx` — insert `<ReviewQueueSection />`
- `frontend/src/i18n/messages/en.json` + `uk.json` (or equivalent per project layout) — `settings.reviewQueue.*` keys
- `_bmad-output/implementation-artifacts/sprint-status.yaml` — status transitions
- `VERSION` — minor bump

### Anti-Scope

Things this story does NOT do:

- **Does NOT add bulk actions** (bulk resolve/dismiss). Per-row only. Bulk is a usage-driven polish pass once we see how users actually interact with the queue.
- **Does NOT add an undo for dismiss.** Queue rows are retained with `status='dismissed'` so a future undo is a cheap write, but the UX affordance isn't shipped here.
- **Does NOT notify the user about pending queue entries** via email / push / in-app banners. The settings-page badge is the only surface.
- **Does NOT surface the queue in the Teaching Feed.** Per tech spec §8.2 explicitly. The feed stays card-driven.
- **Does NOT backfill queue entries for existing pre-11.8 flagged transactions.** Documented in AC #17.
- **Does NOT add a "re-run categorization on this row" button.** Users resolve by picking a category directly; re-running the LLM on a single row is a separate story if ever needed.
- **Does NOT touch `generic.py` fallback parser** or any ingestion-layer logic. Story 11.8 is purely Stage D + downstream.
- **Does NOT implement the rest of Story 11.9's observability events.** Only `categorization.confidence_tier` and `categorization.review_queue_insert` are emitted here — the other events in tech spec §9 (`parser.schema_detection`, etc.) are Story 11.9's scope.
- **Does NOT change `transaction_service.get_flagged_transactions_for_user`** behavior or the `/flagged` endpoint contract. Only OpenAPI description.
- **Does NOT add operator-side analytics** for resolve/dismiss rates. Structured events are emitted (implicitly via the queue-insert event + future Story 11.9 dashboards) but no dedicated metric panel.

### References

- **Tech spec §2.5** (queue schema): [_bmad-output/planning-artifacts/tech-spec-ingestion-categorization.md](../../_bmad-output/planning-artifacts/tech-spec-ingestion-categorization.md)
- **Tech spec §3.1 Stage D** (three-tier routing): same file
- **Tech spec §8** (API + UI scope): same file
- **Tech spec §9** (`categorization.confidence_tier` event schema): same file
- **Epic 11** (delivery order + context): [_bmad-output/planning-artifacts/epics.md](../../_bmad-output/planning-artifacts/epics.md) §11.8 and §"Delivery Order"
- **Story 6.3** (existing flagged-transactions path): [6-3-uncategorized-transaction-flagging.md](./6-3-uncategorized-transaction-flagging.md)
- **Story 11.2** (kind × category matrix + taxonomy): [11-2-transaction-kind-field-expanded-category-taxonomy.md](./11-2-transaction-kind-field-expanded-category-taxonomy.md)
- **Story 11.10** (deterministic-rule carve-out in threshold loop, cross-user isolation pattern): [11-10-counterparty-aware-categorization-pe-statements.md](./11-10-counterparty-aware-categorization-pe-statements.md)
- **Current threshold loop**: [backend/app/agents/categorization/node.py:571-585](../../backend/app/agents/categorization/node.py#L571-L585)
- **Persist paths**: [backend/app/tasks/processing_tasks.py:272](../../backend/app/tasks/processing_tasks.py#L272), [backend/app/tasks/processing_tasks.py:720](../../backend/app/tasks/processing_tasks.py#L720)
- **Transactions API (camelCase DTO pattern + `/flagged` contract)**: [backend/app/api/v1/transactions.py](../../backend/app/api/v1/transactions.py)
- **Settings page**: [frontend/src/features/settings/components/SettingsPage.tsx](../../frontend/src/features/settings/components/SettingsPage.tsx)
- **Settings route**: [frontend/src/app/\[locale\]/(dashboard)/settings/page.tsx](../../frontend/src/app/[locale]/(dashboard)/settings/page.tsx)

## Dev Agent Record

### Agent Model Used

claude-opus-4-7 (Claude Code Opus 4.7, 1M context)

### Debug Log References

- Full backend regression post-implementation: 802 passed, 0 failed (3m08s).
- Frontend regression post-implementation: 52 files, 492 passed.
- Golden-set post-11.8 (Haiku, 2026-04-22): `category_accuracy=0.950` (95/100), `kind_accuracy=1.000` (100/100), `joint_accuracy=0.950`. Both axes clear the 0.92 gate. Report: [20260421T211900249661Z-haiku.json](../../backend/tests/fixtures/categorization_golden_set/runs/20260421T211900249661Z-haiku.json).
- Sonnet golden-set comparison test converted from `xfail` to `skip` at user direction — Haiku is the shipping model; the comparison is off until a model swap is on the table.

### Completion Notes List

- **Three-tier routing** now replaces the single `CATEGORIZATION_CONFIDENCE_THRESHOLD`. `SOFT_FLAG=0.6`, `AUTO_APPLY=0.85` constants live in [backend/app/core/config.py](../../backend/app/core/config.py) and `.env.example`. The old constant is fully removed (single call site in `node.py` + one reference in `test_pre_pass.py` updated).
- **Soft-flag tier preserves the LLM's category/kind** — this was the main behaviour change for downstream consumers. Rows that were previously `category='uncategorized'` at 0.6–0.7 confidence now surface their LLM label to Health Score, Category Breakdown, and Teaching Feed.
- **Queue tier preserves suggestions on the row dict** (`suggested_category`, `suggested_kind`) so the persist path can insert a `uncategorized_review_queue` row. Non-low_confidence flags (llm_unavailable, parse_failure, currency_unknown) are *not* queued because there's no suggestion to act on.
- **Deterministic-rule carve-out** (Story 11.10 Rule 5/6) is preserved: those rows bypass the tier gate at any confidence and never enter the queue.
- **Persist path** batches queue inserts (one commit per batch, not per row) and emits `categorization.review_queue_insert` only after the commit succeeds. The two-event model (decision-time `confidence_tier` + persist-time `review_queue_insert`) is intentional: telemetry stays meaningful even on a persist rollback.
- **Review-queue resolve bumps confidence to 1.0** — user correction is ground truth. Matrix violations raise `KindCategoryMismatchError` → 400; cross-user IDs raise `QueueEntryNotFoundError` → 404 (never 403, to prevent ID-probing).
- **Frontend uses `@tanstack/react-query`** (project convention) rather than SWR as the story described. Same UX contract: list/resolve/dismiss, optimistic revalidate on mutation, inline 400 rendering.
- **Category picker is native `<select>`** per the story's fallback option — no existing shadcn picker component covers the 19-category taxonomy yet. Logged as **TD-063** for a follow-up polish pass. The `KIND` list ("spending", "income", "savings", "transfer") gets its own i18n block under `settings.reviewQueue.kinds.*`.
- **i18n**: added `settings.reviewQueue.*` to both `en.json` and `uk.json`. Also added four previously-missing category labels (`transfers`, `transfers_p2p`, `savings`, `charity`) to `profile.categories.*` in both locales + extended `KNOWN_CATEGORIES` in [frontend/src/features/profile/format.ts](../../frontend/src/features/profile/format.ts) so these render correctly via `useCategoryLabel`.
- **Story 6.3 `/flagged` endpoint is unchanged in behaviour** — only its OpenAPI `description` was updated to contrast with `/review-queue`.
- **No backfill** of pre-11.8 `category='uncategorized'` / `flagged=True` rows — per AC #17, those surface only via `/flagged` until a future "re-run categorization" feature ships.
- **Sonnet golden-set test disabled** — user feedback during implementation was that Haiku consistently outperforms Sonnet on this fixture; no need to burn tokens on the comparison.

### File List

**New files (backend):**

- `backend/alembic/versions/z2a3b4c5d6e7_add_uncategorized_review_queue.py`
- `backend/app/models/uncategorized_review_queue.py`
- `backend/app/services/review_queue_service.py`
- `backend/app/api/v1/review_queue.py`
- `backend/tests/services/test_review_queue_service.py`
- `backend/tests/agents/categorization/test_threshold_tiers.py`
- `backend/tests/tasks/__init__.py`
- `backend/tests/tasks/test_persist_queue_insert.py`
- `backend/tests/api/__init__.py`
- `backend/tests/api/test_review_queue_api.py`
- `backend/tests/integration/test_review_queue_e2e.py`

**New files (frontend):**

- `frontend/src/features/settings/hooks/use-review-queue-count.ts`
- `frontend/src/features/settings/components/ReviewQueueSection.tsx`
- `frontend/src/features/settings/components/__tests__/ReviewQueueSection.test.tsx` (relocated during code-review M6 to match AC #12 path)
- `frontend/src/features/review-queue/hooks/use-review-queue.ts`
- `frontend/src/features/review-queue/components/ReviewQueuePage.tsx`
- `frontend/src/features/review-queue/__tests__/ReviewQueuePage.test.tsx`
- `frontend/src/app/[locale]/(dashboard)/settings/review-queue/page.tsx`

**Modified (backend):**

- `backend/app/core/config.py` — replaced `CATEGORIZATION_CONFIDENCE_THRESHOLD` with `*_SOFT_FLAG_THRESHOLD` + `*_AUTO_APPLY_THRESHOLD`.
- `backend/.env.example` — new threshold env vars.
- `backend/app/agents/categorization/node.py` — three-tier threshold loop + `confidence_tier` telemetry.
- `backend/app/tasks/processing_tasks.py` — queue-insert helper + both persist paths + `review_queue_insert` event.
- `backend/app/models/__init__.py` — registered `UncategorizedReviewQueue`.
- `backend/app/api/v1/router.py` — mounted review-queue router.
- `backend/app/api/v1/transactions.py` — `/flagged` OpenAPI description tweak (AC #15).
- `backend/tests/agents/categorization/test_pre_pass.py` — updated constant reference.
- `backend/tests/agents/categorization/test_golden_set.py` — sonnet test converted to `skip`.
- `backend/app/agents/categorization/mcc_mapping.py` — code-review M3: now owns `VALID_KINDS`, `KIND_CATEGORY_RULES`, `kind_by_sign`, `validate_kind_category` (moved out of `node.py`).
- `backend/app/agents/categorization/node.py` — code-review M3: imports matrix helpers from `mcc_mapping.py`.
- `backend/app/services/review_queue_service.py` — code-review M3/M5/H2: imports `validate_kind_category` from `mcc_mapping.py`; `dismiss()` no longer sets `resolved_at`; added queue/transaction drift INVARIANT docstring.
- `backend/app/tasks/processing_tasks.py` — code-review H1: added `_existing_queue_txn_ids` helper + dedup guard on both persist paths.
- `backend/tests/tasks/test_persist_queue_insert.py` — code-review H1: regression test for the dedup helper.
- `backend/tests/agents/categorization/test_transaction_kind.py` — code-review M3: imports moved to `mcc_mapping.py`.
- `docs/tech-debt.md` — code-review: TD-016 re-confirmed; added TD-064, TD-065.

**Modified (frontend):**

- `frontend/src/features/settings/components/SettingsPage.tsx` — inserted `<ReviewQueueSection />`.
- `frontend/src/features/profile/format.ts` — extended `KNOWN_CATEGORIES` with transfers/transfers_p2p/savings/charity.
- `frontend/src/components/error/FeatureErrorBoundary.tsx` — added `"review-queue"` to `FeatureArea` union.
- `frontend/messages/en.json` — `settings.reviewQueue.*` + missing category labels.
- `frontend/messages/uk.json` — `settings.reviewQueue.*` + missing category labels.

**Modified (repo root):**

- `VERSION` — 1.26.0 → 1.27.0 (MINOR bump, new user-facing feature).
- `_bmad-output/implementation-artifacts/sprint-status.yaml` — `ready-for-dev` → `in-progress` → `review`.
- `docs/tech-debt.md` — added TD-063 (review-queue native `<select>` → shadcn picker).

## Change Log

| Date | Version | Change |
|---|---|---|
| 2026-04-21 | _(pending)_ | Story 11.8 drafted from epics.md §11.8 + tech spec §2.5, §3.1 Stage D, §8. Introduces `uncategorized_review_queue` table, splits the single `CATEGORIZATION_CONFIDENCE_THRESHOLD` into `SOFT_FLAG` (0.6) + `AUTO_APPLY` (0.85) thresholds, wires three-tier routing in the post-LLM loop, adds queue-insert at persist time, ships the API (list/resolve/dismiss/count) and a minimal `/settings/review-queue` page, and emits the first two `categorization.*` telemetry events called for in Story 11.9 §9. Does not replace Story 6.3's `/flagged` endpoint — the two coexist with documented contract differences. |
| 2026-04-22 | 1.27.0 | **Code review (2026-04-22)** — adversarial review found 2 HIGH, 4 MEDIUM, 7 LOW issues. Fixes applied in-review: (H1) added `_existing_queue_txn_ids` batched dedup check in both persist paths so `resume_upload` cannot insert duplicate queue rows, covered by a new unit test in `test_persist_queue_insert.py`; (H2) added a "queue/transaction drift" invariant docstring to `review_queue_service.py` that documents the contract any future external transaction-editor must honour; (M3) moved `VALID_KINDS`, `KIND_CATEGORY_RULES`, `kind_by_sign`, `validate_kind_category` from `node.py` to `mcc_mapping.py` so the service layer no longer imports from `agents/categorization/node.py` (service→agent layering violation), updated `test_transaction_kind.py` imports; (M5) `dismiss()` no longer writes `resolved_at` — that field now strictly indicates a resolution; (M6) relocated `ReviewQueueSection.test.tsx` under `settings/components/__tests__/` per AC #12 path. Promoted three LOW findings to tech-debt: TD-016 re-confirmed (naive datetime / manual `"Z"` suffix on queue entities), TD-064 (consolidate duplicated `_utcnow` helpers), TD-065 (partial unique index on `uncategorized_review_queue(transaction_id) WHERE status='pending'`). Three LOWs kept story-local (amount/currency units cosmetic, Sonnet skip already documented); one LOW (FE error typing) dropped. Backend 803 passed, frontend 492 passed post-review. Story 11.8 implemented. Three-tier routing live in `categorization_node`; `uncategorized_review_queue` table + service + API mounted at `/api/v1/transactions/review-queue`; settings badge + dedicated resolve/dismiss page shipped (en/uk); two new telemetry events (`categorization.confidence_tier`, `categorization.review_queue_insert`). Golden-set post-11.8 Haiku: `category_accuracy=0.950` (95/100), `kind_accuracy=1.000` (100/100) — both axes clear the 0.92 gate, no regression from the tier split. TD-063 logged for a native `<select>` → shadcn picker polish pass. Sonnet comparison test skipped at user direction. Version bumped from 1.26.0 to 1.27.0 per story completion. |
