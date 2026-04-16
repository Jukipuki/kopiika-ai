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
