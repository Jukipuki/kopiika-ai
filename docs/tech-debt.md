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
