# Tech Debt Register

Central log of known tech debt across the codebase. Items here were surfaced during code reviews, retrospectives, or development but deliberately deferred to keep individual stories focused.

## How to use this file

- **Add an entry** when you defer a fix that future work should pick up. Don't use it as a TODO list for in-progress work — that belongs in story files.
- **Reference an entry** from PRs, story files, and code comments by its ID (`TD-001`, etc.) so the link survives refactors.
- **Close an entry** by deleting it (preferred) or moving it to a `## Resolved` section with the commit/PR that addressed it. Don't just check a box — keep this file lean.
- **Severity:** HIGH = product-visible risk or recurring drag, MEDIUM = should fix opportunistically, LOW = nice-to-have polish.

Each entry should answer: what's wrong, where, why it was deferred, and what fixing it would look like.

---

## Open

### TD-001 — `(auth)` pages are client components, not server components with `generateMetadata` [HIGH]

**Where:** [frontend/src/app/[locale]/(auth)/login/page.tsx](frontend/src/app/[locale]/(auth)/login/page.tsx), [signup/page.tsx](frontend/src/app/[locale]/(auth)/signup/page.tsx), [forgot-password/page.tsx](frontend/src/app/[locale]/(auth)/forgot-password/page.tsx), [forgot-password/confirm/page.tsx](frontend/src/app/[locale]/(auth)/forgot-password/confirm/page.tsx)

**Problem:** Every `(auth)` page is a client component using `useAuth` + `useRouter` for the redirect-when-authenticated guard. Because they're client components, none of them can export `generateMetadata`, so the HTML `<title>` is always the default app title — never localized. SEO previews and browser tabs don't reflect the page (e.g. "Reset your password" / "Відновлення паролю").

**Why deferred:** Touches all four `(auth)` pages, not just one story's scope. Story 1.8's tasks (7.1/7.2) originally specified server components but the dev mirrored the existing pattern across the route group.

**Fix shape:** Convert each page to an async Server Component with `generateMetadata({ params })`. Move the redirect-when-authenticated guard from a client `useEffect` to a server-side `auth()` call from `next-auth` followed by `redirect()` from `next/navigation`. Form components can stay `"use client"`. Couple this with TD-002 (router import) since both involve the same pages.

**Surfaced in:** Story 1.8 code review (2026-04-16)

---

### TD-002 — `useRouter` from `next/navigation` + manual locale prefix in `(auth)` pages [HIGH]

**Where:** [frontend/src/app/[locale]/(auth)/login/page.tsx](frontend/src/app/[locale]/(auth)/login/page.tsx), [signup/page.tsx](frontend/src/app/[locale]/(auth)/signup/page.tsx), [forgot-password/page.tsx](frontend/src/app/[locale]/(auth)/forgot-password/page.tsx), [forgot-password/confirm/page.tsx](frontend/src/app/[locale]/(auth)/forgot-password/confirm/page.tsx)

**Problem:** Architecture rule says use `useRouter` from `@/i18n/navigation` for locale-aware redirects. All `(auth)` pages instead import `useRouter` from `next/navigation` and manually prefix with `` `/${locale}/dashboard` ``. This was reportedly a workaround because the i18n router didn't trigger a reliable page reload after navigation (suspected: missing reload on locale change), but the root cause was never documented.

**Why deferred:** Replacing the pattern requires verifying the i18n router actually works in this codebase's Next.js + next-intl combo, and likely a sweep across all `(auth)` pages at once. Out of scope for any single auth story.

**Fix shape:**
1. Reproduce the original "no page reload" issue in a minimal repro (one auth page).
2. Determine whether it's a next-intl version bug, a misconfigured `routing.ts`, or a misuse on our side.
3. If fixable: switch all four `(auth)` pages to `useRouter` from `@/i18n/navigation` and drop the manual locale prefix.
4. If unfixable: document the workaround in `frontend/AGENTS.md` so future devs don't try to "fix" it.

If TD-001 is taken first, the redirect moves server-side and this debt evaporates for `(auth)` pages.

**Surfaced in:** Story 1.8 code review (2026-04-16)

---

### TD-003 — Inconsistent Cognito error code names across service handlers [LOW]

**Where:** [backend/app/services/cognito_service.py](backend/app/services/cognito_service.py) — `_handle_cognito_error` vs `_handle_forgot_password_error`

**Problem:** The same Cognito exception maps to different application error codes depending on which flow it came from:

| Cognito exception | Verify flow code | Reset flow code |
|---|---|---|
| `CodeMismatchException` | `INVALID_CODE` | `RESET_CODE_INVALID` |
| `ExpiredCodeException` | `CODE_EXPIRED` | `RESET_CODE_EXPIRED` |

Frontend has to know both codes to render the same error message. Doubles the surface area for future refactors.

**Why deferred:** Renaming is a backward-incompatible API change for any consumer relying on the existing codes. Low impact today (only the frontend consumes them) but worth bundling with a future auth-error cleanup.

**Fix shape:** Pick one canonical name per exception, update the handler maps, update the frontend i18n error-code lookup, and update tests. Decide whether to keep flow-prefixed codes (`RESET_CODE_*`) or drop the prefix.

**Surfaced in:** Story 1.8 code review (2026-04-16)

---

### TD-004 — `ForgotPasswordForm` "Try again" button is untested [LOW]

**Where:** [frontend/src/features/auth/components/ForgotPasswordForm.tsx:103-109](frontend/src/features/auth/components/ForgotPasswordForm.tsx#L103-L109)

**Problem:** The success-panel "Try again" button resets `submittedEmail` to `null` and re-renders the form. No test exercises this path; if it regresses, users land in a dead-end success screen.

**Why deferred:** Low impact, easy to add later.

**Fix shape:** One Vitest case: submit form successfully, assert success panel renders, click "Try again", assert form re-renders with empty email field.

**Surfaced in:** Story 1.8 code review (2026-04-16)

---

### TD-006 — Divergent version-fallback sentinels across backend and frontend [LOW]

**Where:** [backend/app/core/version.py:16](backend/app/core/version.py#L16) (`"0.0.0+unknown"`) and [frontend/next.config.ts:16](frontend/next.config.ts#L16) (`"0.0.0+dev"`)

**Problem:** Both stacks fall back to a sentinel when `/VERSION` can't be read, but the sentinels are different strings. In the (unlikely but possible) scenario where both fallbacks fire in the same deployment, `GET /health` reports `0.0.0+unknown` while the UI badge shows `v0.0.0+dev` — breaking the "backend and frontend always agree on version" premise that AC #3/#4 imply. Also makes it harder to grep logs for "any machine in a degraded version state" because you have to know both strings.

**Why deferred:** Both fallback paths are unreachable in normal operation (the file is committed at the repo root). Picking a single sentinel is a 5-line change but has no user impact today.

**Fix shape:** Pick one canonical sentinel (suggest `"0.0.0+unknown"` — more honest than `+dev`), export it from a shared config or duplicate the constant in both stacks with a comment pointing at the other copy. Update tests if any assert on the sentinel (currently none).

**Surfaced in:** Story 1.9 code review (2026-04-16)

---

### TD-005 — Unicode emoji envelope instead of `lucide-react` `Mail` icon [LOW]

**Where:** [frontend/src/features/auth/components/ForgotPasswordForm.tsx:80-82](frontend/src/features/auth/components/ForgotPasswordForm.tsx#L80-L82)

**Problem:** The success panel renders a `✉️` unicode emoji. Emoji rendering varies by OS / font fallback (some renders are flat-mono, some color); not on-brand. `lucide-react` is already in the dependency tree and used elsewhere for icons.

**Fix shape:** Replace the `<div>{"\u2709\uFE0F"}</div>` with `<Mail className="h-10 w-10 ..." aria-hidden />` from `lucide-react`. Match sizing/color to the surrounding design.

**Surfaced in:** Story 1.8 code review (2026-04-16)

---

### TD-007 — Resume path may double-count insight cards [LOW]

**Where:** [backend/app/tasks/processing_tasks.py:629-643](backend/app/tasks/processing_tasks.py#L629-L643), [processing_tasks.py:680-681](backend/app/tasks/processing_tasks.py#L680-L681)

**Problem:** When `resume_upload` re-runs the education agent for a previously-failed job, it appends every returned insight card to the DB without dedup, then sets `insight_count = prior_insight_count + len(insight_cards)`. If the original run had already persisted N insights and crashed, the resume path will produce another N (or more) duplicate Insight rows AND surface the inflated count in the user-facing summary card (Story 2.8 made this number user-visible — previously it was internal).

**Why deferred:** Pre-existing behaviour from the resume design; fixing it requires either (a) clearing prior `Insight` rows for the upload before resume, or (b) deduping on `(upload_id, headline, key_metric)` in the loop. Either is a behavioural change to the resume contract that warrants its own story.

**Fix shape:**
1. Decide policy — wipe-and-replay vs. dedup-and-append.
2. If wipe-and-replay: `session.exec(delete(Insight).where(Insight.upload_id == upload_id))` at the top of the resume insight loop, then count `len(insight_cards)` (no `prior_insight_count` arithmetic).
3. If dedup-and-append: build a set of existing `(headline, key_metric)` tuples for this upload, skip cards whose key already exists, and recompute `insight_count` from the post-commit DB count.
4. Either way, drop the `prior_insight_count + len(insight_cards)` shortcut in favor of `select(func.count()).where(Insight.upload_id == upload_id)`.

**Surfaced in:** Story 2.8 code review (2026-04-16)

---

### TD-008 — UploadDropzone outer container keeps "selected" styling under the completion summary card [LOW]

**Where:** [frontend/src/features/upload/components/UploadDropzone.tsx:188-194](frontend/src/features/upload/components/UploadDropzone.tsx#L188-L194)

**Problem:** When `processingComplete === true`, `selectedFile` is still set so `getState()` returns `"selected"` and the dropzone container applies `border-primary/30 bg-primary/5` styling around the celebration UploadSummaryCard. Visually the celebration sits inside a "file is staged for upload" frame instead of a clean completion frame. Functional behaviour (clicks on the card stop-propagating, summary card renders correctly) is fine; this is purely a visual polish item.

**Why deferred:** Touching the state machine inside `getState()` to add a `"completed"` state risks side effects on the file picker (cursor-pointer + onClick), drag/drop handlers, and aria styling — all out of scope for a visual polish.

**Fix shape:** Either (a) add a `processingComplete` short-circuit in `getState()` that returns a new `"completed"` state with neutral styling, or (b) compute the className inline in JSX so `processingComplete` overrides the `"selected"` border class. Option (b) is the smaller change; option (a) is the cleaner long-term fix.

**Surfaced in:** Story 2.8 code review (2026-04-16)

---

### TD-009 — Two parallel `formatCurrency` helpers with different amount semantics [LOW]

**Where:** [frontend/src/lib/format/currency.ts](frontend/src/lib/format/currency.ts), [frontend/src/features/profile/format.ts](frontend/src/features/profile/format.ts)

**Problem:** There are two `formatCurrency` exports. The `lib/format` version takes a unit amount (e.g. `1234.56`) and formats with fixed 2-fraction digits. The `features/profile` version takes **kopiykas** (integer), divides by 100, and relies on Intl's per-currency default fraction digits (JPY → 0, UAH → 2). Story 2.9 added the optional `currency` argument to both in parallel; the implementations now drift in three dimensions: amount units, fraction-digit behaviour, and locale-fallback logic. Callers must know which one to import based on whether their data is already-decimal or kopiykas — an easy regression hazard.

**Why deferred:** Task 9.2 of Story 2.9 explicitly recommended deduplicating, but the dev deferred because consolidation requires auditing every call site (MonthlyComparison, CategoryBreakdown, UncategorizedTransactions, upload summary, etc.) and deciding on a single kopiykas-vs-units API. The tactical fix (just adding the `currency` arg to both) kept the story focused.

**Fix shape:**
1. Decide on a canonical API in `@/lib/format/currency` — likely `formatKopiykas(amount: number, locale, currency)` and delete the profile-local copy.
2. Grep `formatCurrency(` across `frontend/src` and migrate each call site, being careful about the `amount / 100` difference.
3. Align fraction-digit behaviour — the lib version hardcodes 2, the profile version uses Intl defaults; choose one (Intl defaults are more correct for JPY).
4. Drop `SUPPORTED_CURRENCIES` duplication — export the set from a single module.

**Surfaced in:** Story 2.9 code review (2026-04-16)

---

### TD-010 — `CurrencyInfo.symbol` field is populated but never consumed [LOW]

**Where:** [backend/app/services/currency.py:16](backend/app/services/currency.py#L16)

**Problem:** `CurrencyInfo` defines a `symbol: str` field and every entry in `CURRENCY_MAP` populates it ("₴", "$", "CHF", etc.). No backend or API code reads it — the frontend uses `Intl.NumberFormat` to derive symbols, which is the correct source. The field sits there as dead metadata.

**Why deferred:** Not a functional issue, and removing it is a (tiny) API change to `CurrencyInfo` that could surface if anyone imported the symbol elsewhere. Cheap to clean up opportunistically.

**Fix shape:** Either (a) delete the `symbol` field and drop the third constructor arg from all nine entries, or (b) expose it via a new API endpoint if there's a real consumer need. Option (a) is the default — YAGNI wins here.

**Surfaced in:** Story 2.9 code review (2026-04-16)

---

### TD-012 — No offline eval harness for insight `key_metric` quality / length drift [MEDIUM]

**Where:** [backend/app/agents/education/prompts.py](backend/app/agents/education/prompts.py), [backend/app/agents/education/node.py](backend/app/agents/education/node.py)

**Problem:** AC #3 of Story 3.9 asserts that on a sample of 10 newly generated insight cards, ≥ 90% of `key_metric` values should be ≤ 60 characters with no more than one numeric figure. The story ships with no offline evaluation — only prompt-content unit tests (which verify the instruction text is present) and a runtime observability log `key_metric_length_over_30` (which only fires post-generation). If the LLM silently ignores the constraint in production — as it did with the previous 30-char rule, producing compound strings like `"₴87,582.04 (25.9% of total) vs. ₴213,238.50 finance allocation"` — we discover the regression from user-visible UI noise or by combing logs, not from CI.

Note: the team's **intentional stance** is that value quality outranks strict brevity; the original 30-char failure was primarily a visual-hierarchy bug (font larger than the headline), fixed via styling in Story 4.2. So this is a "nice to have guardrail," not "this story is broken."

**Why deferred:** Building an eval harness (sample LLM runs against representative fixtures, score the outputs, assert percentile compliance) is meaningfully larger than the prompt tweak itself and would need its own eval corpus. Out of scope for a single-line prompt refinement story.

**Fix shape:**
1. Add a lightweight eval script under `backend/evals/` (new dir) that feeds a fixed set of 10 user-context + rag-context fixtures through `education_node` with a real LLM (or a higher-fidelity mock replaying recorded responses).
2. Assert: (a) ≥ 90% of `key_metric` values ≤ 60 chars, (b) ≤ 1 numeric figure per value (regex: at most one contiguous digit run per string, allowing `%` and currency adjacency).
3. Wire to CI as a manual / nightly job (not per-commit — LLM calls cost money and are flaky).
4. When the eval surfaces drift, iterate on prompts (EN + UK) rather than hard-failing the build.
5. Alternatively — aggregate the existing `key_metric_length_over_30` log into a weekly dashboard metric before building a full eval; real production data may be cheaper than synthetic fixtures.

**Surfaced in:** Story 3.9 code review (2026-04-16)

---

### TD-011 — `extract_raw_currency` hardcodes CSV header keys [LOW]

**Where:** [backend/app/services/currency.py:54-65](backend/app/services/currency.py#L54-L65)

**Problem:** `extract_raw_currency(raw_data)` only checks `("Валюта", "Currency")` when recovering the raw alpha from a parsed row's `raw_data`. Any future bank parser whose CSV uses a different header (e.g. PrivatBank Lite, a different European bank, a localized variant) will silently return `None` even when `raw_data` contains the value under another key — the API's `currencyUnknownRaw` field will be blank and the user will see a flagged row with no indication of which currency failed.

**Why deferred:** Only two parsers (Monobank, PrivatBank) and they share "Валюта". Generic parser uses heuristic column detection but its keyword list includes both "Валюта" and "Currency" already. Real risk only when bank #4 lands.

**Fix shape:** Either (a) have parsers stamp a canonical key into `raw_data` (e.g. `raw_data["_currency_raw"] = raw_currency`) so the helper just reads one key, or (b) extend `extract_raw_currency` to accept the parser's header-alias list. Option (a) is cleaner but requires touching all three parser implementations; option (b) is more surgical.

**Surfaced in:** Story 2.9 code review (2026-04-16)

---

### TD-013 — `AuditMiddleware` skips failed/unauthorized requests, masking enumeration & abuse [HIGH]

**Where:** [backend/app/core/audit.py:53](backend/app/core/audit.py#L53)

**Problem:** The middleware short-circuits with `if response.status_code >= 400: return response`, so the audit trail records only happy-path access. Enumeration attempts (401/403 on other users' UUIDs), 404 scans, and 5xx during exploitation never appear in `audit_logs`. GDPR Article 32 expects evidence of unauthorized access *attempts*, not just successful ones — a real compliance audit would flag this gap immediately. Story 5.6 AC1 is technically satisfied (it speaks of requests that "access" data, i.e. successes), so this didn't block the story, but the trail is materially weaker than what the compliance posture implies.

**Why deferred:** Logging failures properly needs a new `status_code` column on `audit_logs` (another migration) plus a design decision on attribution for `401` responses (the bearer token may be invalid/missing — no trustworthy `sub` to log against). That's a full sub-story, not a 10-line patch.

**Fix shape:**
1. Add `status_code SMALLINT NOT NULL` to `audit_logs` (new Alembic migration).
2. Drop the `>= 400` skip; always log when there is a parseable Bearer token + a sub claim.
3. For `401` with no/invalid token, decide explicitly: either log with `user_id = 'anonymous'` + IP/UA (good signal for abuse detection) or skip (current behavior, document the choice).
4. Add tests covering each status-code class.
5. Update the operator runbook with a "failed-access investigation" query.

**Surfaced in:** Story 5.6 code review (2026-04-16)

---

### TD-014 — `audit_logs` 2-year retention policy is claimed but not enforced anywhere [MEDIUM]

**Where:** [backend/alembic/versions/o1p2q3r4s5t6_add_audit_logs_table.py](backend/alembic/versions/o1p2q3r4s5t6_add_audit_logs_table.py), Story 5.6 Dev Notes ("Retention policy" section)

**Problem:** Story 5.6 AC5 mandates "retention policy of 2 years minimum". The dev notes assert this is "enforced at the infrastructure level (CloudWatch log group retention + no automated DB cleanup)", but there is no IaC change, no CloudWatch retention setting, no Alembic comment, no scheduled job, and no test pinning the policy. Today the table is append-only, which trivially satisfies "minimum 2 years" by never deleting — but that also means no upper-bound retention, no GDPR-mandated deletion-after-purpose, and no proof of policy if an external auditor asks "show me the retention configuration".

**Why deferred:** This is an infra/IaC story (Terraform or AWS Console + a documented runbook), not a backend code change. Out of scope for the application-level audit trail story.

**Fix shape:**
1. Decide policy (likely: 24 months active in DB, then archive to S3 Glacier, then delete after 7 years for financial-services parity).
2. Implement via either (a) a partitioned table + monthly partition drop job, or (b) a scheduled Lambda / Celery beat task + S3 archival.
3. Document the configured retention in `docs/operator-runbook.md` next to the audit query section.
4. Add an integration test that the cleanup job moves rows older than the threshold.

**Surfaced in:** Story 5.6 code review (2026-04-16)

---

### TD-015 — `AuditMiddleware` integration tests use a stub FastAPI app, not the real one [MEDIUM]

**Where:** [backend/tests/test_audit_middleware.py:51-79](backend/tests/test_audit_middleware.py#L51-L79)

**Problem:** The audit middleware suite builds a minimal `stub_app = FastAPI()` and registers `AuditMiddleware` in isolation. This is fast and reproducible, but it never validates: (a) the real middleware-stack ordering against `RequestLoggingMiddleware` and `CORSMiddleware`, (b) interaction with the real auth dependency (`get_current_user_payload`), or (c) that audit rows from unrelated endpoint tests don't leak into a shared test DB and cause flakiness. The deletion-flow integration test added in Story 5.6 covers part (b) for one path; broader coverage would catch a future middleware reorder regression.

**Why deferred:** Real-app integration would require either spinning up the full `app` per test (slow, conflicts with existing fixtures) or refactoring `conftest.py` to support an audit-aware client fixture. Test-infra refactor with no immediate user-visible payoff.

**Fix shape:** Add an opt-in `audit_real_client` fixture in `conftest.py` that wires `AuditMiddleware` against the real `app` with a per-test SQLite. Migrate one or two representative tests (`test_get_transactions_creates_read_record`, `test_no_bearer_token_no_audit_record`) to use it. Keep the stub-based tests for fast iteration on middleware internals.

**Surfaced in:** Story 5.6 code review (2026-04-16)

---

### TD-016 — `DateTime()` (naive) used across migrations instead of `DateTime(timezone=True)` [MEDIUM]

**Where:** [backend/alembic/versions/o1p2q3r4s5t6_add_audit_logs_table.py:42](backend/alembic/versions/o1p2q3r4s5t6_add_audit_logs_table.py#L42), and likely other timestamp columns across older tables

**Problem:** Multiple migrations use `sa.DateTime()` which maps to Postgres `TIMESTAMP WITHOUT TIME ZONE`. Models strip tzinfo via `.replace(tzinfo=None)`. This works while the app runs in a single UTC timezone, but will silently produce ambiguous timestamps if the Postgres `timezone` server setting ever changes, if a direct SQL consumer connects with a non-UTC session timezone, or if timestamps are correlated across services that do use `timestamptz`. Story 7.1's `card_interactions.created_at` was fixed to `DateTime(timezone=True)` during code review, but the pattern persists in older tables.

**Why deferred:** Fixing existing tables requires ALTER COLUMN migrations for each affected table, plus a codebase-wide audit of every `_utcnow()` / `datetime.utcnow()` call to ensure they produce timezone-aware values. Safe to do but high blast radius for a single story.

**Fix shape:**
1. Audit all Alembic migrations for `sa.DateTime()` without `timezone=True` — list every affected table/column.
2. Create one migration per table (or a single multi-table migration) that ALTERs each column to `TIMESTAMPTZ`. Postgres does this in-place with no rewrite for `TIMESTAMP → TIMESTAMPTZ` when the server timezone is UTC.
3. Update all model `_utcnow()` helpers to return `datetime.now(UTC)` (keep tzinfo).
4. Grep for `datetime.utcnow()` (deprecated in Python 3.12) and replace.

**Surfaced in:** Story 7.1 code review (2026-04-17)

### TD-017 — `card_feedback.created_at` is frozen on vote flip, obscuring vote-change time [LOW]

**Where:** [backend/app/services/feedback_service.py:154](backend/app/services/feedback_service.py#L154)

**Problem:** When a user flips their vote (up → down or down → up), `submit_card_vote` updates the `vote` column in place but leaves `created_at` unchanged. The GET endpoint returns this original timestamp, so "createdAt" in the API response actually means "when the user first voted on this card", not "when the current vote was chosen". Analytics that assume `createdAt` marks the current-state age will be wrong for any flipped vote, and the UI has no way to show "you changed your mind at T".

**Why deferred:** No consumer currently depends on vote-change timing; the ambiguity is latent. Fix touches both schema (add `updated_at`) and response shape, which is broader than a LOW nit warrants inside Story 7.2.

**Fix shape:**
1. Add `updated_at timestamptz NOT NULL default now()` column to `card_feedback` via Alembic migration.
2. Update `submit_card_vote` to set `updated_at = _utcnow()` on both INSERT and UPDATE paths.
3. Expose `updatedAt` in `CardVoteOut` and `CardFeedbackResponse`.
4. Frontend `CardFeedbackState` picks up `updatedAt`.

**Surfaced in:** Story 7.2 code review (2026-04-17)

### TD-018 — No concurrency test for `submit_card_vote` unique-constraint race path [LOW]

**Where:** [backend/app/services/feedback_service.py:106-160](backend/app/services/feedback_service.py#L106-L160), [backend/tests/test_feedback_service.py](backend/tests/test_feedback_service.py)

**Problem:** The `submit_card_vote` service now catches `IntegrityError` on concurrent first-vote inserts, rolls back, and re-loads the winner's row to UPDATE its vote. This branch is never exercised by tests — existing tests only hit the sequential SELECT-hit or single-session INSERT paths. A future refactor could silently regress the IntegrityError retry without any test failing.

**Why deferred:** Reliably simulating the race requires either two independent `SQLModelAsyncSession` instances against a file-backed SQLite DB (brittle, SQLite locking behaves differently from Postgres), or a Postgres testcontainer (new dev-dependency + CI wiring). Outside the scope of Story 7.2's bugfix.

**Fix shape:**
1. Add a Postgres testcontainer fixture (or extend the existing test DB setup) so tests can exercise real INSERT contention.
2. Write a test that spawns two coroutines both attempting `submit_card_vote(card_id, user_id, vote="up", ...)` with `asyncio.gather`, asserts exactly one row exists post-race, and both futures resolve without a 500.

**Surfaced in:** Story 7.2 code review (2026-04-17)

### TD-020 — `ReportIssueForm` free-text `sr-only` label duplicates the placeholder text [LOW]

**Where:** [frontend/src/features/teaching-feed/components/ReportIssueForm.tsx:99-110](frontend/src/features/teaching-feed/components/ReportIssueForm.tsx#L99-L110)

**Problem:** The free-text textarea's `<label className="sr-only">` reuses `t("freeText.placeholder")` ("Describe the issue...") as both the accessible label and the placeholder. Screen readers announce the same string twice — once as the label, once as the placeholder hint — and the label doesn't describe the field's purpose (optional details about the reported issue), only restates the prompt. Not WCAG-failing, but sub-par for SR users.

**Why deferred:** Purely cosmetic a11y polish; behaviour is correct and the form already has a visible category label, a dialog `aria-label`, and `aria-live` states. Outside the scope of Story 7.3's functional fixes.

**Fix shape:**
1. Either (a) reuse the existing `t("freeText.toggle")` key ("Add details (optional)") for the `sr-only` label — it already describes the field's purpose — or (b) add a new `feed.reportIssue.freeText.label` key and mirror it in `uk.json`.
2. Update the `<label>` text accordingly; keep the `htmlFor` → `id` association.

**Surfaced in:** Story 7.3 code review (2026-04-17)

---

### TD-019 — GET `/api/v1/feedback/cards/{cardId}` is not rate-limited [LOW]

**Where:** [backend/app/api/v1/feedback.py:111-132](backend/app/api/v1/feedback.py#L111-L132)

**Problem:** The GET card-feedback endpoint is invoked on every Teaching Feed card mount with the user's bearer token. Unlike the POST endpoint it does not call `rate_limiter.check_feedback_rate_limit`, so a misbehaving client (or abuse) can hammer the endpoint indefinitely. Reads are typically exempt, but this path hits Postgres per call and could be a cheap amplification vector.

**Why deferred:** Read-path throttling wasn't explicitly required by Story 7.2 ACs and the endpoint is per-card low-volume in normal use. Safer to add under a dedicated "feedback read tier" once there's observability on actual call rates.

**Fix shape:**
1. Add `check_feedback_read_rate_limit(user_id, max_reads=120, window_seconds=60)` (or similar tier) to `RateLimiter`, distinct from the write tier.
2. Wire `Depends(get_rate_limiter)` into `get_card_feedback` and call the new method.
3. Add a 429 test mirroring `test_submit_vote_rate_limited`.

**Surfaced in:** Story 7.2 code review (2026-04-17)

---

### TD-021 — `FreeTextFeedbackEntry.feedbackSource` is returned by the API but never rendered [LOW]

**Where:** [backend/app/api/v1/data_summary.py:61-67](backend/app/api/v1/data_summary.py#L61-L67), [frontend/src/features/settings/hooks/use-data-summary.ts:34-39](frontend/src/features/settings/hooks/use-data-summary.ts#L34-L39), [frontend/src/features/settings/components/MyDataSection.tsx:175-189](frontend/src/features/settings/components/MyDataSection.tsx#L175-L189)

**Problem:** Each `FreeTextFeedbackEntry` in the data summary response includes `feedbackSource` (`"card_vote"` vs `"issue_report"`), and the TS interface mirrors the field. `MyDataSection` never reads it, so a user browsing their "My Data" list cannot tell whether a given free-text line is a vote follow-up comment or the body of an issue report. Dead field on the wire = YAGNI surface.

**Why deferred:** Not a functional defect — the data is still accurate and the free-text itself is shown. Calling the right UX treatment (small badge? grouped sections? drop from the DTO?) needs a product call that was out of scope for Story 7.4.

**Fix shape:** Pick one of:
1. Render a small translated label/badge next to each entry (`Vote comment` / `Issue report`), adding `feedbackSourceVote` / `feedbackSourceIssue` keys to `en.json` / `uk.json`.
2. Group the free-text list into two subsections by source.
3. Remove `feedbackSource` from `FreeTextFeedbackEntry` (both backend Pydantic model and frontend interface) if the UI never needs it.

**Surfaced in:** Story 7.4 code review (2026-04-17)

---

### TD-022 — `CardFeedback.free_text` has no `max_length=500` on the model [LOW]

**Where:** [backend/app/models/feedback.py:50](backend/app/models/feedback.py#L50)

**Problem:** Architecture spec says `free_text` is capped at 500 chars (`_bmad-output/planning-artifacts/architecture.md#Feedback Data Model`), but the SQLModel field is `free_text: Optional[str] = Field(default=None)` — no `max_length`, no DB-level `String(500)`. Submission endpoints (`submit_card_vote`, `submit_issue_report`) may validate via Pydantic schemas, but the model itself accepts arbitrarily long strings, so a direct insert or a schema regression would silently store unbounded text. The data-summary endpoint then serves whatever is there (now capped to 100 rows by Story 7.4 review, but each row is still unbounded).

**Why deferred:** Discovered during Story 7.4 review while adding the query `.limit(100)` cap. Fixing this cleanly likely needs an Alembic migration to alter the column type to `VARCHAR(500)` and a cross-check of the POST endpoint validators. Out of scope for the 7.4 privacy-integration story.

**Fix shape:**
1. Add `max_length=500` to the SQLModel field: `free_text: Optional[str] = Field(default=None, max_length=500)`.
2. Write an Alembic migration to alter the column to `VARCHAR(500)` (truncate strategy TBD — probably fail-fast if any existing row exceeds 500).
3. Audit POST endpoint validators (`submit_card_vote`, `submit_issue_report`, any future Layer-3 feedback_responses submission) to ensure they reject >500-char input with a 400, rather than relying on the DB to truncate.

**Surfaced in:** Story 7.4 code review (2026-04-17)

---

### TD-023 — `FollowUpPanel` is missing swipe-down dismissal [LOW]

**Where:** [frontend/src/features/teaching-feed/components/FollowUpPanel.tsx](frontend/src/features/teaching-feed/components/FollowUpPanel.tsx)

**Problem:** Story 7.5 AC #3 lists two dismissal paths: "tap outside the panel **or swipe it down**". The panel now supports tap-outside (document-level `pointerdown` listener) and Escape-key dismiss, but swipe-down is not implemented. Mobile users — the primary audience for the Teaching Feed — have no gesture affordance matching the slide-up visual.

**Why deferred:** Touch-gesture handling isn't shipped by shadcn/Button; adding it needs a small pointer-tracking hook (`pointerdown` → `pointermove` → measure `deltaY` + threshold) with cleanup, plus tests that simulate pointer events under fake timers. The other AC #3 dismissal paths are functional, and the current taps-outside behaviour arguably covers most intents.

**Fix shape:**
1. Add a `usePointerSwipe` custom hook (or inline effect) in `FollowUpPanel.tsx` that listens for `pointerdown` on the panel, tracks `pointermove` deltaY, applies a live `translateY` on the panel element, and fires `onDismiss()` when `deltaY > 80px` on `pointerup` (otherwise springs back with a CSS transition).
2. Ensure the pointer handlers don't conflict with the document-level outside-tap listener (use `pointerdown`'s `stopPropagation` or check `event.target` vs panel ref).
3. Add a Vitest test that fires `pointerdown` on the panel, `pointermove` with `clientY` delta > 80, `pointerup`, and asserts `onDismiss` was called.

**Surfaced in:** Story 7.5 code review (2026-04-17)

---

### TD-024 — Thumbs-up follow-up probability is an inline literal, not a named constant [LOW]

**Where:** [frontend/src/features/teaching-feed/components/CardFeedbackBar.tsx:92](frontend/src/features/teaching-feed/components/CardFeedbackBar.tsx#L92)

**Problem:** The 1-in-10 trigger for the thumbs-up follow-up panel is expressed inline as `Math.random() < 0.1`. The `0.1` is meaningful (product-tuning knob — matches PRD FR51 "1 in 10 occurrences"), but reads as a magic number. If product ever wants to tune this (e.g. A/B at 0.05 vs 0.15), or if a second variant adds its own probability, the intent-free literal is easy to miss during grep and easy to drift between call sites.

**Why deferred:** One-line polish with no functional impact; fixing requires agreement on the constant's scope (per-component, per-feature module, or a shared feedback-config) which is a larger design call than the Story 7.6 scope.

**Fix shape:**
1. Extract `const THUMBS_UP_FOLLOW_UP_PROBABILITY = 0.1` at module scope in `CardFeedbackBar.tsx` (or, better, in a shared `features/teaching-feed/config.ts` alongside any future feedback tunables).
2. Replace the inline literal with the named constant.
3. If a shared config module is introduced, also move the 300ms `followUpTimerRef` delay there for consistency.

**Surfaced in:** Story 7.6 code review (2026-04-17)

---

### TD-027 — `insights.category` is not indexed; cluster-flagging `GROUP BY` full-scans insights [LOW]

**Where:** [backend/app/models/insight.py:23](backend/app/models/insight.py#L23), [backend/app/tasks/cluster_flagging_tasks.py:47-62](backend/app/tasks/cluster_flagging_tasks.py#L47-L62)

**Problem:** The cluster-flagging Celery task runs a `GROUP BY i.category` across the whole `card_feedback` ⋈ `insights` join on every daily execution. `insights` has an index on `user_id` but none on `category`, so the group-by forces a full scan + hash aggregate. Fine while `insights` is small; becomes measurable drag once the table grows to tens of millions of rows, especially given the task runs unthrottled in a single session.

**Why deferred:** No current pain — dev/staging tables are small, and the batch runs at 02:00 UTC once per day (and even that depends on TD-026 being resolved first). Low value until there is evidence of real query time or the row count crosses a threshold.

**Fix shape:**
1. Add an Alembic migration creating `ix_insights_category` on `insights(category)`.
2. Confirm the Postgres planner now uses an index scan / sort for the Phase 1 query in the flagging task (`EXPLAIN ANALYZE`).
3. Consider a composite `(category, user_id)` instead if analytics queries also filter by owner; plain `(category)` is sufficient for the current batch query.

**Surfaced in:** Story 7.8 code review (2026-04-17)

---

### TD-028 — No end-to-end canary that beat actually publishes scheduled messages [MEDIUM]

**Where:** [infra/terraform/modules/ecs/main.tf:199-209](infra/terraform/modules/ecs/main.tf#L199-L209), [docs/operator-runbook.md#Verifying-beat-is-running](docs/operator-runbook.md)

**Problem:** Story 7.9 shipped a container-level healthcheck (`python -c 'from app.tasks.celery_app import celery_app'`) that proves the Celery app still imports, but does NOT detect silent scheduler failures where beat is up yet not publishing — e.g. an empty `beat_schedule`, a wedged mainloop, clock drift that skips a cadence, or a corrupted `celerybeat-schedule` file. Story 7.9's original AC #7 called for a smoke check that asserts "the `celery` queue has seen a message matching a known scheduled task name within the last 24 h, and fails loudly when it has not"; the shipped implementation intentionally does not cover that.

**Why deferred:** Building a real canary requires either a CloudWatch log metric filter + alarm on `"Scheduler: Sending due task"` lines in `/ecs/${env}-beat`, or a weekly cron that inspects the broker queue / `flagged_topic_clusters` freshness. Both are additive work beyond the "make beat run at all" scope of Story 7.9. The import-only healthcheck was a conscious downgrade documented in the story's AC #7 narrowing.

**Fix shape:**
1. Add an `aws_cloudwatch_log_metric_filter` on `/ecs/${env}-beat` matching the `"Scheduler: Sending due task"` substring.
2. Add an `aws_cloudwatch_metric_alarm` in the same Terraform module that fires when the metric sum over 25h is `< 1`, wired to the existing alerting SNS topic.
3. As a cheaper alternative: weekly Celery beat-schedule canary task that checks `flagged_topic_clusters` for freshness and pages if the last `last_evaluated_at` is older than 26h.
4. Remove or tighten the runbook's "Container liveness" bullet once the real canary is live, so operators don't confuse the two.

**Surfaced in:** Story 7.9 code review (2026-04-17)

---

### TD-025 — `_sessionFlags` module-level object read inside useEffect without being in deps [LOW]

**Where:** [frontend/src/features/teaching-feed/components/CardFeedbackBar.tsx:24](frontend/src/features/teaching-feed/components/CardFeedbackBar.tsx#L24), [CardFeedbackBar.tsx:59-71](frontend/src/features/teaching-feed/components/CardFeedbackBar.tsx#L59-L71), [CardFeedbackBar.tsx:86](frontend/src/features/teaching-feed/components/CardFeedbackBar.tsx#L86)

**Problem:** `_sessionFlags.hasShownFollowUp` is a mutable module-level object that gates whether the thumbs-down follow-up panel has already been shown in this session. The flag is read inside a `useEffect`, but the deps array (`[followUpPending, feedbackId, followUpVariant]`) does not include it — React will not re-run the effect when the flag flips. This works today because the effect re-runs on every vote (via `followUpPending` → true) and the read happens inside that re-entry, but:
- `react-hooks/exhaustive-deps` under stricter config (or a future ESLint upgrade) may flag it.
- The pattern is invisible to React's reactivity model, so any refactor that decouples the flag from `followUpPending` will silently break the session-cap behavior.
- Exporting the object to allow tests to reset it leaks implementation state into the module surface.

**Why deferred:** No observed bug today; the pattern was inherited from Story 7.5's follow-up panel session-cap fix, and replacing it with a reactive source (ref + context or `useSyncExternalStore`) is a structural change disproportionate to a cosmetic code-smell inside a single story.

**Fix shape:**
1. Replace `_sessionFlags` with either (a) a `useSyncExternalStore`-backed singleton that React can subscribe to, or (b) a React Context provider scoped to the feed page so the flag reads become reactive state, or (c) a `useRef` that lives in the nearest common ancestor of all `CardFeedbackBar` instances — if there isn't one, create one.
2. Drop the `_sessionFlags` named export; replace the test-side reset with the chosen API (e.g. `vi.resetModules()` or a provider remount).
3. Add an ESLint rule or CI check that fails if a module-level mutable object is read inside a hook body without being either a ref or a subscribed store.

**Surfaced in:** Story 7.6 code review (2026-04-17)

---

### TD-029 — Codebase-wide assumption that all integer money is kopiykas (UAH) [HIGH]

**Where:** [backend/app/models/transaction.py:21](backend/app/models/transaction.py#L21) (`amount: int  # Integer kopiykas`), [backend/app/models/pattern_finding.py](backend/app/models/pattern_finding.py) (`baseline_amount_kopiykas`, `current_amount_kopiykas`), [backend/app/services/profile_service.py:46](backend/app/services/profile_service.py#L46), [backend/app/services/health_score_service.py](backend/app/services/health_score_service.py), [backend/app/agents/education/node.py](backend/app/agents/education/node.py) (`_build_spending_summary`), [backend/app/agents/pattern_detection/detectors/trends.py](backend/app/agents/pattern_detection/detectors/trends.py), [frontend/src/features/profile/format.ts](frontend/src/features/profile/format.ts) (`formatCurrency` divides by 100), and likely every other call site that reads `Transaction.amount` or sums money.

**Problem:** `Transaction` carries a per-row `currency_code: int` (ISO 4217 numeric, default `980` = UAH) that parsers set from the source CSV, so non-UAH rows *can* land in the DB. However, every downstream aggregator, formatter, and now the new `pattern_findings` table treats `amount` as if it were always UAH kopiykas — no currency filter, no FX normalization, no per-currency partitioning. Concretely:

- `profile_service.build_or_update_profile` sums `abs(amount)` across all rows into a single "total kopiykas" figure and feeds that into the health score.
- `education_node._build_spending_summary` renders `₴{amount / 100}` regardless of the transaction's actual currency.
- `pattern_detection.detectors.trends` sums across currencies per category and emits `baseline_amount_kopiykas` / `current_amount_kopiykas` columns that bake the kopiyka assumption into the schema.
- The frontend `formatCurrency` in `features/profile/format.ts` divides by 100 and renders with the user's locale currency — not the transaction's.

As long as uploads contain only UAH rows, everything looks right. The moment a user uploads a statement with EUR or USD rows (which the parsers already accept), every aggregate, health score, insight card, and pattern finding becomes silently wrong — mixing currencies as if they were the same unit, displaying `₴` over values that aren't hryvnias.

**Why deferred:** This is a cross-cutting concern that touches the entire read path, not a single story's scope. It was surfaced while reviewing the column naming in `pattern_findings` (Story 8.1) — the columns honestly reflect what the code does, but the underlying assumption leaks into the schema.

**Fix shape:**

1. **Audit.** Grep the whole repo for every read path that touches `Transaction.amount`, every occurrence of the substring `kopiyka`, and every column / variable / identifier with an `_kopiykas` (or equivalent "cents"/"minor_units") suffix. Catalogue each site: aggregation, formatting, persistence, API response, UI render. Expect hits in at least:
   - `backend/app/services/profile_service.py`, `health_score_service.py`, `insight_service.py`
   - `backend/app/agents/education/node.py`, `backend/app/agents/pattern_detection/detectors/trends.py`
   - `backend/app/models/pattern_finding.py` (column names), `backend/app/models/financial_profile.py`, `financial_health_score.py`
   - `backend/app/api/v1/transactions.py`, `profile.py`, any endpoint returning `amount` fields
   - `frontend/src/lib/format/currency.ts`, `frontend/src/features/profile/format.ts`, every component that formats money
2. **Pick a strategy.** Three realistic options:
   - **(a) Filter at aggregation** — every aggregator processes only `currency_code = 980` rows; non-UAH rows are shown raw on the transaction list but excluded from totals, pattern detection, health score, etc. Cheapest, but silently drops data the user uploaded.
   - **(b) Normalize at ingestion** — add an `amount_uah_kopiykas` column computed via an FX rate at the transaction's date; all aggregations read that. Requires an FX rate service + historical rates + a backfill migration. Most accurate, highest effort.
   - **(c) Partition findings by currency** — rename all `_kopiykas` fields to `_minor_units`, add `currency_code` alongside, and emit one finding / profile slice / insight per category-per-currency. Most honest schema; forces the UI to decide how to present multi-currency results.
3. **Rename columns and helpers** once the strategy is chosen. `baseline_amount_kopiykas` → `baseline_amount_minor_units` (option c) or stays as-is if option (a) is adopted with a filter at the aggregator boundary. Update the Alembic migration and the `PatternFinding` SQLModel together. Do the same sweep for `FinancialProfile` and `FinancialHealthScore`.
4. **Update formatters.** Frontend `formatCurrency` / `formatKopiykas` must stop hard-coding `₴` and the `/100` divisor; drive both from the row's `currency_code`. (Note: overlaps with TD-009 — the two `formatCurrency` helpers should collapse into one multi-currency-aware API as part of this work.)
5. **Tests.** Add a representative multi-currency fixture (UAH + USD + EUR in one upload) and assert the chosen behaviour across every aggregator / formatter / agent node: no silent mixing, no `₴` over non-UAH values, pattern findings segregated by currency (if option c) or UAH-only (if option a).

**Related:** TD-009 (two parallel `formatCurrency` helpers — consolidating them is a prerequisite for step 4), TD-010 (`CurrencyInfo.symbol` dead field — decide during step 4 whether to revive it), TD-011 (`extract_raw_currency` hardcodes CSV header keys — tangentially related, same currency-awareness family).

**Surfaced in:** Story 8.1 code review follow-up (2026-04-17) — column naming discussion for `pattern_findings`

---

### TD-030 — `_make_state()` helper duplicated across pipeline test files [LOW]

**Where:** [backend/tests/agents/test_categorization.py](backend/tests/agents/test_categorization.py), [backend/tests/agents/test_education.py](backend/tests/agents/test_education.py), [backend/tests/agents/test_pattern_detection.py](backend/tests/agents/test_pattern_detection.py), [backend/tests/test_pipeline_checkpointing.py](backend/tests/test_pipeline_checkpointing.py)

**Problem:** Each test file defines its own `_make_state()` helper that constructs a `FinancialPipelineState` with every field defaulted. Every time the state TypedDict grows a field (e.g. `pattern_findings` in Story 8.1), all four helpers must be updated in lockstep or tests will fail at construction. Story 8.1 had to modify three existing `_make_state` helpers plus add a fourth in the new test file.

**Why deferred:** Pure test-ergonomics refactor; no runtime impact. Worth doing the next time a state field is added and someone has to touch all four helpers again.

**Fix shape:** Hoist a single `make_pipeline_state(**overrides)` helper into `backend/tests/conftest.py` (or a sibling `tests/agents/_helpers.py`). Every test file imports it. Adding a new state field then requires exactly one edit.

**Surfaced in:** Story 8.1 code review (2026-04-18)

---

### TD-032 — Inactivity badge/text says "month(s)" even for annual subscriptions [LOW]

**Where:** [backend/app/agents/pattern_detection/detectors/recurring.py:110-114](backend/app/agents/pattern_detection/detectors/recurring.py#L110-L114), [frontend/src/features/teaching-feed/components/SubscriptionAlertCard.tsx:24-27](frontend/src/features/teaching-feed/components/SubscriptionAlertCard.tsx#L24-L27)

**Problem:** The detector's `_inactivity_for_annual` returns `max(1, delta_days // 365)` — i.e. missed YEARS — but persists it into a column called `months_with_no_activity`, and `SubscriptionAlertCard` renders the value as `"Inactive {n} month(s)"` regardless of billing frequency. A user with an Adobe annual sub that hasn't charged for 26 months sees "Inactive 2 month(s)" when the truthful copy is "Inactive 2 year(s)" (or "Inactive ~24 month(s)"). Data is technically correct in count-of-missed-cycles terms but the unit label lies.

**Why deferred:** LOW severity because annual subs going dormant for multiple cycles is a long-tail case; the label-vs-value mismatch only bites users in that scenario. Fix requires deciding the canonical unit (rename column to `cycles_missed` + conditional unit in UI, or store months-since consistently and let the UI divide) and coordinating backend + frontend + migration.

**Fix shape:**
1. Pick canonical representation. Recommended: rename column to `cycles_missed` (Alembic migration), keep detector math as-is; UI renders `"Inactive {n} month(s)"` for monthly, `"Inactive {n} year(s)"` for annual.
2. Update `_serialize_subscription` / `SubscriptionInfo` / `SubscriptionAlertCard` to key off `billingFrequency` when formatting the badge.
3. Add a frontend test covering the annual-inactive case so the label never regresses.

**Surfaced in:** Story 8.2 code review (2026-04-18)

---

### TD-033 — `InsightCard.cardType` is typed as plain `string`, not a literal union [LOW]

**Where:** [frontend/src/features/teaching-feed/types.ts:20](frontend/src/features/teaching-feed/types.ts#L20), [frontend/src/features/teaching-feed/components/CardStackNavigator.tsx:13-18](frontend/src/features/teaching-feed/components/CardStackNavigator.tsx#L13-L18)

**Problem:** `cardType: string` with an inline comment listing the three valid values (`"insight" | "subscriptionAlert" | "milestoneFeedback"`). TypeScript doesn't enforce the comment — a typo in the dispatch (`"subscriptionalert"`, `"SubscriptionAlert"`) silently falls through to the default `InsightCard` render with no compile error. The comment stays in sync only by convention.

**Why deferred:** No known miss today; the story explicitly chose `string` so the API contract (server returns whatever literal it wants) stays permissive. Worth tightening once the third card type (`milestoneFeedback`) lands and a discriminated-union dispatcher becomes natural.

**Fix shape:**
1. Introduce `export type CardType = "insight" | "subscriptionAlert" | "milestoneFeedback";` in `types.ts`.
2. Change `cardType: string` to `cardType: CardType` on `InsightCard`.
3. Convert the dispatch helper in `CardStackNavigator` to a discriminated-union `switch (card.cardType)` so the compiler flags missing branches when a new card type is added.

**Surfaced in:** Story 8.2 code review (2026-04-18)

---

### TD-034 — `detected_subscriptions` has no `(upload_id, merchant_name)` uniqueness [LOW]

**Where:** [backend/alembic/versions/u7v8w9x0y1z2_add_detected_subscriptions_table.py:26-80](backend/alembic/versions/u7v8w9x0y1z2_add_detected_subscriptions_table.py#L26-L80), [backend/app/agents/pattern_detection/node.py:64-85](backend/app/agents/pattern_detection/node.py#L64-L85)

**Problem:** `_persist_subscriptions` runs `session.add()` per subscription dict inside the pattern detection node. If the pipeline is retried or resumed after a post-persist failure, `_persist_subscriptions` re-runs and duplicates every row for the upload — same `(user_id, upload_id, merchant_name)` tuple, different `id`. The Education agent then generates duplicate subscription alert cards. Overlaps with TD-007 (same class of retry-duplication issue in the insights resume path).

**Why deferred:** Retries today are uncommon; the `process_upload` task's retry path doesn't routinely re-enter `pattern_detection_node`. Fix requires deciding the contract (unique constraint + `ON CONFLICT DO UPDATE`, or wipe-and-replay per upload) plus a migration.

**Fix shape:**
1. Decide policy: (a) `UNIQUE (upload_id, merchant_name)` + upsert, or (b) `DELETE WHERE upload_id = :id` at the top of `_persist_subscriptions`.
2. If (a): new Alembic migration adding the unique index; `_persist_subscriptions` uses `INSERT ... ON CONFLICT (upload_id, merchant_name) DO UPDATE`.
3. If (b): add the delete at the top of `_persist_subscriptions`. Cheaper but diverges from whatever TD-007 resolves on for insights.
4. Either way, add a test that re-runs `pattern_detection_node` twice for the same upload and asserts exactly N rows.

**Surfaced in:** Story 8.2 code review (2026-04-18)

---

### TD-035 — Inactivity badge color is amber-only; no escalation for severe inactivity [LOW]

**Where:** [frontend/src/features/teaching-feed/components/SubscriptionAlertCard.tsx:35-41](frontend/src/features/teaching-feed/components/SubscriptionAlertCard.tsx#L35-L41)

**Problem:** Story 8.2 AC #6 describes a "red/amber badge" for the inactivity indicator, but the component ships with amber-only styling (`bg-amber-100 text-amber-900`) regardless of how long the sub has been dormant. A 2-cycle-inactive sub and a 12-cycle-inactive sub look identical. Red is reserved in the design system for higher-severity signals, so always-amber under-signals long-dormant auto-renewals — exactly the case a user most wants to act on.

**Why deferred:** Amber satisfies the literal AC (the spec says "red/amber", not "red AND amber"), and deciding the escalation threshold is a product call that wasn't in scope for the detection story. The component also doesn't currently receive enough context to escalate based on absolute time since last charge (only `monthsWithNoActivity`, which is per-cycle).

**Fix shape:**
1. Pick a threshold with product (e.g. ≥ 3 missed cycles for monthly, ≥ 1 missed cycle for annual = red; otherwise amber).
2. Extract a `getInactivityTone(subscription): "red" | "amber"` helper in the component; switch `className` on the result (`bg-red-100 text-red-900` vs current amber).
3. Add Vitest cases: 2-month-inactive → amber, 6-month-inactive → red, 1-year-inactive annual → red.

**Surfaced in:** Story 8.2 code review (2026-04-18)

---

### TD-031 — `detect_anomalies` uses population variance, not sample variance [LOW]

**Where:** [backend/app/agents/pattern_detection/detectors/trends.py:160-163](backend/app/agents/pattern_detection/detectors/trends.py#L160-L163)

**Problem:** Variance is computed as `sum((a - mean) ** 2) / n` (population). With the sample-size guard at `n >= 5`, this underestimates stddev by ~10% compared to the sample formula `/ (n - 1)`. The net effect is that the mean+2σ outlier threshold fires slightly more often than a reader would expect from the "2-sigma" label. Not a correctness bug per se — just not what most statistical tooling defaults to — and testable thresholds will shift if we ever switch.

**Why deferred:** The detector is new, and the 2σ threshold itself is a tuning parameter that will likely change once real user data shows false-positive rates. Swapping population → sample should be bundled with threshold re-calibration rather than done in isolation.

**Fix shape:** Change `variance = sum((a - mean) ** 2 for a in amounts) / n` to `/ (n - 1)` (guarded by the existing `n >= 5` check so `n - 1 >= 4`). Update any tests that assert specific stddev-dependent values. Consider calling out in `detect_anomalies` docstring whether the threshold is population-σ or sample-σ to prevent re-drift.

**Surfaced in:** Story 8.1 code review (2026-04-18)

---

### TD-036 — `_SEVERITY_PRIORITY` duplicates `_SEV_MAP` across triage node + insight_service [LOW]

**Where:** [backend/app/agents/triage/node.py:25](backend/app/agents/triage/node.py#L25), [backend/app/services/insight_service.py:21](backend/app/services/insight_service.py#L21)

**Problem:** Two near-identical severity-priority maps live in different modules. `triage/node.py` exposes `_SEVERITY_PRIORITY = {"critical": 0, "warning": 1, "info": 2}` for the worst-per-category reduction. `insight_service.py` exposes `_SEV_MAP = {"critical": 0, "warning": 1, "info": 2, "high": 0, "medium": 1, "low": 2}` for pagination-cursor comparisons. Any future severity tweak (add a new bucket, renumber priorities) has to be made in both places or behavior will drift between the triage reducer and the feed sort.

**Why deferred:** Pure refactor with zero user-visible payoff. Worth doing opportunistically the next time severity is touched.

**Fix shape:** Hoist a single `SEVERITY_PRIORITY` constant into a shared module (options: `app/core/severity.py`, or alongside `Insight` in `app/models/insight.py`) plus a `LEGACY_SEVERITY_PRIORITY` containing the pre-8.3 high/medium/low buckets. `triage/node.py` imports `SEVERITY_PRIORITY`; `insight_service.py` builds `_SEV_MAP = {**SEVERITY_PRIORITY, **LEGACY_SEVERITY_PRIORITY}`. Delete the local copies.

**Surfaced in:** Story 8.3 code review (2026-04-18)

---

### TD-037 — Triage failure path does not append `"triage"` to `completed_nodes` [LOW]

**Where:** [backend/app/agents/triage/node.py:119-133](backend/app/agents/triage/node.py#L119-L133)

**Problem:** The triage node's success path sets `step="triage"` AND appends `"triage"` to `completed_nodes`. The failure path sets `step="triage"` but does NOT append to `completed_nodes` and does NOT set `failed_node`. Downstream code that inspects `completed_nodes` to decide whether triage ran (or that inspects `failed_node` to detect who failed) gets inconsistent signals: the step marker says "triage ran last", but the completion list says "triage never ran" and the failed-node slot is empty. Contrast with `education_node`, which sets `failed_node="education"` on its failure branch.

**Why deferred:** No caller currently reads `completed_nodes` to decide downstream behavior — LangGraph's own graph traversal drives control flow, not this list. Behaviorally invisible today; cost is observability/debugging clarity, not correctness.

**Fix shape:** Pick one contract and apply consistently:
1. **"Ran, regardless of outcome"** — always append `"triage"` to `completed_nodes` after the scoring try-block exits, set `failed_node="triage"` on the error branch. Matches `education_node`'s failure contract.
2. **"Success-only membership"** — leave `completed_nodes` behavior as-is but ALSO set `failed_node="triage"` on error, so there's a single source of truth for "which node broke".

Option 1 is the less-surprising contract across the pipeline.

**Surfaced in:** Story 8.3 code review (2026-04-18)

---

### TD-038 — Inverted `FinancialProfile` period silently treated as 1 month of income [LOW]

**Where:** [backend/app/agents/triage/node.py:45](backend/app/agents/triage/node.py#L45)

**Problem:** `_estimate_monthly_income_kopiykas` computes `months = max(1.0, (period_end - period_start).days / 30.0)`. If `period_end < period_start` (data corruption, manual DB edit, clock skew during backfill, etc.), `days` is negative and the `max(1.0, ...)` clamp silently treats `total_income` as one month's worth. A user with `total_income=600_000_00` (600 kUAH accrued across many months) and an inverted 1-day period would suddenly look like they earn 600 kUAH/month — shifting every single pattern finding into the `info` bucket via the income-relative branch. The resulting severity-scoring is wildly wrong with no observable signal.

**Why deferred:** `build_or_update_profile` always sets `period_end >= period_start` under normal flow, so the inversion is a defense-in-depth concern, not an active bug. Cheap to harden but out of Story 8.3's scope.

**Fix shape:**
1. Short-term: wrap the date delta in `abs(...)` or explicitly bail with `return None` when `period_end < period_start`.
2. Medium-term: add a CHECK constraint on `financial_profiles` (`period_end >= period_start`) via Alembic migration; backfill any existing violators (likely zero in practice).
3. Add one unit test for the triage node with an inverted-period profile asserting it falls back to absolute thresholds.

**Surfaced in:** Story 8.3 code review (2026-04-18)

---

### TD-039 — Runtime multi-provider LLM failover not implemented [MEDIUM]

**Where:** [backend/app/agents/llm.py](backend/app/agents/llm.py), [_bmad-output/planning-artifacts/architecture.md](_bmad-output/planning-artifacts/architecture.md) — "Bedrock Migration & AgentCore Architecture" § Provider Strategy

**Problem:** `LLM_PROVIDER` is static per deployment. A Bedrock-region outage or throttling incident surfaces as pipeline / chat failures with no automatic fallback to Anthropic or OpenAI, even though `llm.py` supports all three providers. The MVP posture is deliberate (doubling the error surface + observability cost is not justified before real availability data exists), but if the chat / pipeline availability SLO (see AI Safety Architecture § Observability & Alarms) is breached in prod, runtime failover becomes load-bearing.

**Why deferred:** Story 9.5 scope deliberately excluded failover — the architecture commits to "MVP: none." Implementing it cleanly requires: (1) per-provider health probes, (2) circuit-breaker state shared across ECS tasks (likely via Redis — extends the existing `backend/app/agents/circuit_breaker.py`), (3) per-turn fallback semantics for chat that don't break AgentCore session continuity, (4) tests that actually exercise provider degradation. Easier to build once we have production telemetry showing where it matters.

**Fix shape:**
1. Extend `circuit_breaker.py` to track per-provider error rate and open-circuit state in Redis (cross-task visibility).
2. In `llm.py`, wrap the active provider with a circuit-aware dispatcher that falls over to a declared secondary when the circuit opens.
3. For the Chat Agent on AgentCore: failover is NOT per-turn — the whole session pins to its start-time provider (switching mid-session reshapes memory semantics). Decide whether degraded sessions are forcibly ended (`CHAT_REFUSED` with `reason=provider_degraded`) or continue on the impaired provider.
4. Add dashboards + alarms for circuit-open events (reuse the existing safety-observability pipeline).
5. Update the regression suite in `backend/tests/agents/providers/` with a fault-injection mode.

**Surfaced in:** Sprint change proposal 2026-04-18 architecture review

---

### TD-040 — Persistent cross-session chat memory [MEDIUM]

**Where:** [_bmad-output/planning-artifacts/architecture.md](_bmad-output/planning-artifacts/architecture.md) — "AI Safety Architecture" § Memory & Session Bounds, FR66

**Problem:** Epic 10 ships chat with durable per-session history (viewable, resumable, deletable) but no cross-session *context carry-over* — each new session starts with a fresh context window. FR66 ("chat maintains cross-session memory per user") is satisfied by history, not by persistent memory. Users starting a second session don't benefit from the agent "remembering" prior clarifications / preferences / named entities — they have to restate context.

**Why deferred:** Persistent per-user memory amplifies every safety concern in the section above: (1) prompt-injection payloads persist and re-fire across sessions, (2) canary-leak blast radius grows, (3) PII redaction decisions from one session must be re-validated in another, (4) deletion semantics under consent revoke get harder (delete history AND derived memory), (5) AgentCore's memory primitives need a policy layer on top. None of this is impossible; it is materially more complex than the read-only history that Epic 10 already ships.

**Fix shape:**
1. Pick the memory representation: (a) summarized prior-session digest re-prepended at new-session start, (b) AgentCore-native long-term memory, or (c) external vector store keyed by `user_id`. Option (a) is the cheapest first step.
2. Extend the red-team corpus in `backend/tests/ai_safety/` with cross-session attacks (payload planted in session 1 → re-fires in session 2) before enabling memory in prod.
3. Extend consent-revoke cascade to also delete derived memory artifacts, not only `chat_sessions` / `chat_messages`.
4. Extend canary detection to cover memory output, not just per-turn output.
5. Tune the Observability & Alarms thresholds to distinguish per-session vs cross-session block-rate anomalies.

**Surfaced in:** Sprint change proposal 2026-04-18 architecture review

---

### TD-041 — Chat subscription gate pending payments epic [LOW]

**Where:** [_bmad-output/planning-artifacts/prd.md](_bmad-output/planning-artifacts/prd.md) — FR72, [_bmad-output/planning-artifacts/epics.md](_bmad-output/planning-artifacts/epics.md) — Epic 10 "Does NOT depend on: Payments/subscription"

**Problem:** FR72 commits to shipping chat ungated at initial launch and adding a subscription gate as a follow-up "once freemium payments integration lands." No story or epic currently owns this follow-up. If chat reaches commercial launch before the payments epic is scoped, the gate will be retro-fitted under time pressure rather than designed in.

**Why deferred:** Intentional. The payments epic itself is still unscoped, and gating chat before there is a paywall to gate it against makes no sense. The tech debt is purely organizational — we need a ticket so the follow-up isn't lost when the payments epic eventually lands.

**Fix shape:**
1. When the payments epic is scoped, add a story covering the chat subscription gate: FastAPI middleware that checks subscription tier on `POST /chat/messages` endpoints; 402 or similar on free-tier over-quota; frontend surface with upgrade CTA.
2. Decide the free-tier allowance at product level (e.g., first N messages / first N sessions / first month free). Not a tech decision.
3. Update FR72 wording to reference the new story instead of this TD entry.
4. Close this TD entry.

**Surfaced in:** Implementation Readiness assessment 2026-04-19

---

### TD-043 — Upload summary warnings list is count-only, not itemized [LOW]

**Where:** [frontend/src/features/upload/components/UploadSummaryCard.tsx:119-126](../frontend/src/features/upload/components/UploadSummaryCard.tsx#L119-L126)

**Problem:** Rejected rows render as an expandable `<details>` listing row number + reason, but the warnings list (currently only `sign_convention_mismatch`) surfaces as a single "N rows imported with warnings" sentence. A user with one flagged row in a 500-row file cannot locate it. Story 11.5 AC #6 wording implies per-row visibility for `warnings` as well as `rejected_rows`.

**Why deferred:** Warnings today are a single soft-signal rule with low-severity practical impact; the cosmetic parity with the rejections block wasn't worth blocking the story. Revisit if additional warning types are added (e.g. Story 11.6 mojibake warnings) or if users report confusion.

**Fix shape:**
1. Mirror the `<details>`/`<ul>` structure used for `rejectedRows`, reusing `reasonLabel`.
2. Add i18n strings `warningsRow`, `warningReason_sign_convention_mismatch` (en + uk).
3. Extend the card's Vitest coverage with a warnings-list case.

**Surfaced in:** Story 11-5-post-parse-validation-layer code review (2026-04-20)

---

### TD-044 — Rejection/warning reason strings are hand-mirrored between backend and frontend [LOW]

**Where:** [backend/app/services/parse_validator.py:68,74,82,88](../backend/app/services/parse_validator.py#L68) ↔ [frontend/src/features/upload/components/UploadSummaryCard.tsx:23-28](../frontend/src/features/upload/components/UploadSummaryCard.tsx#L23-L28)

**Problem:** Reason codes (`date_out_of_range`, `zero_or_null_amount`, `no_identifying_info`, `sign_convention_mismatch`) live as Python string literals on the backend and as a hard-coded `Set` on the frontend. Any new reason silently falls back to `rejectedReason_unknown` in the UI until someone remembers to update `REJECTION_REASON_KEYS` and both locale files. This will drift as Stories 11.6 (`mojibake_detected`) and 11.7 (schema-detection surfacing) add reasons.

**Why deferred:** Story 11.5 shipped only four reasons, all mapped by hand — the drift cost today is zero. Cost grows as Epic 11 adds more reasons.

**Fix shape:**
1. Centralize reasons in a single backend enum (e.g. `ValidationReason` `StrEnum`).
2. Either (a) expose the enum in the OpenAPI schema and codegen a TypeScript union, or (b) publish a JSON constants file consumed by both sides.
3. Replace the frontend `REJECTION_REASON_KEYS` Set with the generated type, and enforce exhaustive `reasonLabel` mapping via TS.
4. Delete the per-locale `rejectedReason_unknown` fallback once exhaustiveness is enforced at build time.

**Surfaced in:** Story 11-5-post-parse-validation-layer code review (2026-04-20)

---

### TD-045 — Pooled mojibake rate dilutes single-row corruption [MEDIUM]

**Where:** [backend/app/services/format_detector.py:80-92](../backend/app/services/format_detector.py#L80-L92)

**Problem:** `detect_mojibake()` divides total U+FFFD count by *total chars across all descriptions*. One fully-garbled row (100% `\ufffd`) inside 500 clean rows rounds to ~0.2% and never trips the 5% threshold, so targeted encoding corruption on a single merchant name goes undetected even though that description will be unusable for categorization downstream.

**Why deferred:** AC #2 wording ("across transaction description fields") supports the pooled calculation, so Story 11.6 passes as-specified. Story 11.6 review surfaced this as a signal-loss risk, not a bug.

**Fix shape:**
1. Alongside the pooled rate, track `rows_with_any_replacement_char: int` (count rows with ≥1 `\ufffd`).
2. Optionally return `max_per_row_rate: float` so an isolated ≥5% row also trips the flag.
3. Update `ParseAndStoreResult` + observability events to include the new signal; leave the pooled rate in place for backwards compatibility.

**Surfaced in:** Story 11-6-encoding-detection-with-mojibake-flagging code review (2026-04-20)

---

### TD-046 — `parser.decode_fallback` log lacks upload/user correlation [MEDIUM]

**Where:** [backend/app/agents/ingestion/parsers/monobank.py:72-75](../backend/app/agents/ingestion/parsers/monobank.py#L72-L75), [backend/app/agents/ingestion/parsers/privatbank.py:59-62](../backend/app/agents/ingestion/parsers/privatbank.py#L59-L62), [backend/app/agents/ingestion/parsers/generic.py:72-75](../backend/app/agents/ingestion/parsers/generic.py#L72-L75)

**Problem:** When a parser falls back from the detected encoding to UTF-8 with `errors="replace"`, it logs `parser.decode_fallback` with only `{encoding, parser}`. No `upload_id` or `user_id`. In production, triaging which upload tripped a decode fallback requires correlating timestamps — an SRE papercut, and a real gap if fallback rate ever spikes.

**Why deferred:** `AbstractParser.parse(file_bytes, encoding, delimiter)` has no upload context in its signature. Threading it through requires either an API change or a `contextvars.ContextVar`-based pattern — both larger than Story 11.6's scope.

**Fix shape:**
1. Add a `contextvars.ContextVar[UploadContext]` set in `_parse_and_build_records` before calling `parser.parse()`.
2. Read it inside the fallback `except` block and include `upload_id`/`user_id` in the `extra=` dict.
3. Alternative: move the fallback warn up one level to `_parse_and_build_records` by letting the parsers surface a `decode_fallback_used: bool` on `ParseResult`.

**Surfaced in:** Story 11-6-encoding-detection-with-mojibake-flagging code review (2026-04-20)

---

### TD-047 — `_decode_content()` helper lacks `errors="replace"` safety net [LOW]

**Where:** [backend/app/services/format_detector.py:107-109](../backend/app/services/format_detector.py#L107-L109)

**Problem:** `_decode_content(file_bytes, encoding)` calls `file_bytes.decode(encoding)` with no error-handling flag. Safe *today* because the only caller (`detect_format`) wraps it in `try/except (UnicodeDecodeError, LookupError)` at lines 182-187. But the helper is attractive nuisance — any future caller (or a refactor that inlines it elsewhere) silently inherits the un-safe version and can raise mid-pipeline.

**Why deferred:** Purely defensive; no current caller is unsafe. Story 11.6 opted to leave the helper untouched rather than change a shared utility.

**Fix shape:**
1. Either inline `_decode_content` into its single caller and delete the helper, OR
2. Add `errors="replace"` inside the helper (changing all callers' behaviour — verify `detect_format` is still happy with replacement chars in its sniff pass).

**Surfaced in:** Story 11-6-encoding-detection-with-mojibake-flagging code review (2026-04-20)

---

### TD-048 — Self-transfer pair detection across multi-statement uploads [MEDIUM]

**Where:** Would live in a new service between [backend/app/agents/categorization/node.py](../backend/app/agents/categorization/node.py) and the financial-profile aggregation layer. Currently affects any user who uploads both their Monobank card statement AND their FOP account statement.

**Problem:** A single economic event (user moves money from their FOP account to their personal card) appears as two rows:
  - PE statement: `-10,000 UAH "Переказ між власними рахунками..."` (outbound leg)
  - Card statement: `+10,000 UAH "З гривневого рахунку ФОП"` (inbound leg)

Both are correctly classified `kind=transfer` (post-Story-11.4), so neither inflates spending or savings. But the Transfers breakdown in the UI double-lists the same event, which is cosmetic noise. More importantly, if a future Pattern Detection layer aggregates transfer volume, it will over-count by a factor of 2 per self-transfer pair.

**Why deferred:** Not a categorization-layer concern — per-row classification is correct. Belongs in a matching/aggregation layer that sees multiple rows at once. Out of Epic 11 scope.

**Fix shape:**
1. In a future pattern-detection or profile-aggregation service, implement pairing logic: for every `kind=transfer` outbound row, look for an inbound `kind=transfer` row within ±10 minutes, absolute amount consistent with FX conversion (within 1% tolerance after applying the transaction's rate), and matching currency pair.
2. When a pair is recognized, annotate both rows with a shared `self_transfer_pair_id` (UUID) and surface them as a single movement in the Transfers breakdown UI.
3. Unpaired transfer rows (e.g., card-only uploader with no FOP statement) continue to display individually.
4. Cross-bank pairing (Monobank → PrivatBank) is out of scope initially — too much variance in descriptions.

**Surfaced in:** Architect review 2026-04-21 (Epic 11 PE-statement discussion).

---

### TD-049 — Counterparty-aware categorization for PE account statements [HIGH]

**Where:** Will require extensions to [backend/app/agents/categorization/node.py](../backend/app/agents/categorization/node.py) prompt contract, the `bank_format_registry` mapping schema (tech spec §2.4), and a new user-IBAN registry storage. Affects classification correctness for all FOP users who upload their PE account statement.

**Problem:** The Ukrainian PE (sole-proprietor) account statement has a fundamentally different signal structure than the card statement:
  - PE statement has: **counterparty name, counterparty EDRPOU (tax ID), counterparty IBAN** — but NO MCC.
  - Card statement has: MCC — but no counterparty fields.

The current categorization pipeline assumes MCC + description and cannot use counterparty signals. This makes several categorizations incorrect on PE statements:
  - Real business income (`+175,800 "Оплата за послуги..." from Company with non-zero EDRPOU`) looks structurally identical to a P2P receipt because the pipeline doesn't know EDRPOU distinguishes legal entities from individuals.
  - Self-transfers to the user's own card (`-10,000 "Переказ між власними рахунками..."` with the user's own IBAN as counterparty) can't be deterministically detected without comparing counterparty IBAN to the user's known IBANs.
  - Tax payments to the State Treasury have a distinctive EDRPOU pattern that would deterministically map to `category=government`.

Without this, gs-091 through gs-094 in the golden set cannot pass — they require counterparty-driven classification that the current pipeline can't perform.

**Why deferred:** Requires multiple coordinated changes: (a) Story 11.7 must ship AI-assisted schema detection first (so counterparty columns get mapped); (b) `bank_format_registry` schema must accept counterparty column mappings (additive to tech spec §2.4); (c) the categorization node must receive counterparty fields in its input; (d) a user-IBAN registry must exist so the system can recognize "user's own IBAN." Large scope, worth a dedicated story post-Story-11.7.

**Fix shape:**
1. Extend `bank_format_registry.detected_mapping` JSON shape to include optional `counterparty_name_column`, `counterparty_tax_id_column`, `counterparty_account_column`, `counterparty_account_currency_column` fields.
2. Extend the categorization pipeline's transaction DTO to carry counterparty fields when available.
3. Add a `user_iban_registry` table (per-user, many IBANs): `{id, user_id, iban_encrypted, label, first_seen_upload_id, created_at}`. **IBAN values MUST be encrypted at rest** (follow Story 5.1 encryption pattern — application-level AES using the same KMS key). IBANs are PII under GDPR and Ukrainian financial-data protection rules.
4. Populate `user_iban_registry` from both directions:
   - Card uploads: extract the user's own card IBAN from statement metadata (if present in the parser output).
   - PE uploads: any counterparty IBAN matching the user's name is a candidate for the registry.
5. Extend the categorization prompt to receive counterparty fields when present, with new disambiguation rules:
   - `counterparty_iban` ∈ `user_iban_registry` → `transfers/transfer` (self-transfer)
   - `counterparty_tax_id` matches State Treasury / tax authority patterns → `government/spending` (outbound) or `other/income` (inbound refund, rare)
   - `counterparty_tax_id` is a 10-digit RNOKPP (individual tax ID) → treat as P2P
   - `counterparty_tax_id` is an 8-digit EDRPOU (legal entity) → `other/income` (inbound) OR classify by description (outbound)
6. Add 5–10 golden-set rows covering PE-statement patterns (gs-091 through gs-094 seeded 2026-04-21; expand as real PE-statement variants are encountered).
7. Extend the harness to segregate `edge_case_tag = "pe_statement"` rows from the card-pipeline accuracy metric until this TD lands.

**Surfaced in:** Architect review 2026-04-21 (Epic 11 PE-statement discussion). Blocks gs-091–gs-094 harness coverage.

---

### TD-050 — UX hint: prompt user to upload all account statements when card-only upload detected [MEDIUM]

**Where:** Frontend upload flow + Teaching Feed card types + Epic 4 financial-profile surfaces. No existing file location.

**Problem:** Card-only uploaders have an incomplete financial picture, and the system currently has no mechanism to tell them so. Specifically:
  - Their Savings Ratio component of the Health Score is unreliable because the real income signal (`Оплата за послуги...` on the PE statement) is invisible. The card statement's `З гривневого рахунку ФОП` is a self-transfer, not income — post-Story-11.4 it will be correctly classified as `transfers/transfer`, which means a card-only FOP user's income will appear as zero, and their Savings Ratio will display "Not enough data yet."
  - Multi-card users see the outbound leg of a self-transfer on one card and the inbound leg on the other; without both uploads, the inbound looks like unexplained income.
  - The system currently has no user-facing signal that the picture is partial.

**Why deferred:** Product/UX work, not categorization. Needs design before implementation.

**Fix shape:**
1. **Detection heuristics:**
   - Upload from a single Monobank card statement AND ≥ N `З гривневого рахунку ФОП` / `From UAH account` / similar inbound self-transfers present → user is likely an FOP who also has a PE statement.
   - User has multiple uploads in the same month but ≥ M unreconciled inbound self-transfer-pattern transactions → user likely has another card/account whose statement hasn't been uploaded.
   - Health Score's Savings Ratio component renders "Not enough data yet" because `sum(kind=income)==0` → surface an upload prompt.
2. **Surfaces:**
   - Inline banner on the upload-completion screen: "Do you have a business (FOP) account? Upload its statement for accurate income and tax tracking."
   - Teaching Feed `uploadPrompt` card type (new) surfaced when detection fires, linking back to the upload flow.
   - Settings / data-quality panel showing "Accounts you've uploaded: 1 of ~2 likely" with guidance.
3. **Copy (UA + EN) needed.**
4. **Dismissal logic** — don't nag. Once dismissed per upload-id, don't re-surface for the same upload.

**Surfaced in:** Architect review 2026-04-21 (Epic 11 PE-statement discussion).

---

## Resolved

### TD-042 — Epic 11 categorization gate cleared with margin [RESOLVED 2026-04-21]

**Resolved by:** Story 11.4 (description pre-pass + Prompt Rule 4).

**Stable measurement (Haiku, post-Story-11.4):** `category_accuracy=0.956` (86/90), `kind_accuracy=1.000` (90/90), `joint_accuracy=0.956` on the main 90-row set after filtering 4 `edge_case_tag="pe_statement"` rows. Both axes cleared the 0.92 noise-margin gate with meaningful headroom (+0.036 on category, +0.080 on kind above the 0.92 floor). `pe_statement_accuracy=1.000` (4/4) as a non-gating secondary signal — those rows remain gated by TD-049.

**Methodology:** Single-run gate at 0.92 (not 0.90) to build margin above the 0.90 statutory threshold given ±3-row variance on a 90-row fixture. See [20260421T130309013273Z-haiku.json](../backend/tests/fixtures/categorization_golden_set/runs/20260421T130309013273Z-haiku.json) for the authoritative run report.

**Residual 4 mismatches (non-blocking, out of Story 11.4 scope):**
  - gs-027: education → government (MCC 4829 ambiguity around government-adjacent education payment)
  - gs-061, gs-068: subscriptions → shopping (subscriptions-vs-shopping boundary)
  - gs-086: transport → shopping (large-outlier transport purchase misclassified)

Any follow-up on these would be a new scoped story; no new TD entry warranted yet.

### TD-026 — Celery beat scheduler is not deployed; `beat_schedule` never fires [HIGH]

Resolved by Story 7.9 (2026-04-17) — `backend/Dockerfile.beat`, CI build+push+deploy in `.github/workflows/deploy-backend.yml`, dedicated `aws_ecs_service.beat` (`desired_count = 1`) in `infra/terraform/modules/ecs/main.tf`, and a `beat` service in `docker-compose.yml`. Operator runbook now documents how to verify beat is running and the file-based scheduler-store trade-off. Verification of the first production 02:00 UTC firing happens post-deploy (watch `/ecs/kopiika-prod-beat` CloudWatch logs and the `flagged_topic_clusters` table).
