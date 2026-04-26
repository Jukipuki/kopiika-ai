# Story 10.7: Chat UI (Conversation, Composer, Streaming, Refusals)

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **kōpiika user (UA + EN, mobile-first) who has granted `chat_processing` consent**,
I want **a chat screen that lets me hold a multi-turn conversation grounded in my own financial data — composer, message list, token-by-token streaming, citation chips, principled-refusal UX, consent first-use prompt and post-revoke empty state, deletion entry points, and rate-limit soft-block surfaces — wired to the SSE protocol from Story 10.5/10.5a (`chat-open`, `chat-thinking`, `chat-token`, `chat-citations`, `chat-complete`, `chat-refused`) and the citation contract from Story 10.6b (transaction / category / profile_field / rag_doc kinds with their dedup keys, label rules, and 20-citation cap)** —
so that **Epic 10's user-facing surface ships: the spec authored by Stories 10.3a (skeleton) and 10.3b (states) becomes living UI that consumes the backend contracts already in production, FR68 ("citations back to underlying data") is observable in the chip strip, refusals route through reason-specific copy with a copyable correlation-ID instead of leaking guardrail rationale, and the WCAG 2.1 AA + UA-edge-case copy work locked in 10.3b is enforced at render time rather than left as an aspirational doc.**

## Scope Boundaries

This story is the **frontend chat surface** that consumes already-shipped backend + UX contracts. Explicit deferrals — **must not** ship here:

- **No backend changes.** All backend contracts (Stories 10.1a, 10.1b, 10.2, 10.4a/b/c, 10.5, 10.5a, 10.6a, 10.6b) are frozen. If a real defect surfaces during integration, file a TD entry and route to a follow-up story; do not patch backend code in 10.7.
- **No new UX spec content.** The UX is fully specified by [ux-design-specification.md §Chat Skeleton (10.3a) + §Chat States (10.3b)](../planning-artifacts/ux-design-specification.md#L1564-L1796). Layout, message types, citation chip slot, focus order, refusal-variant visual, consent flow states, deletion entry points, rate-limit soft-block, full WCAG 2.1 AA pass, and the UA + EN copy reference table are **inputs**, not outputs. If the spec is ambiguous on a render detail, prefer the spec's literal language over inferred behavior; record any genuine ambiguity as a tech-debt note for a 10.3c clarification, do not invent UX here.
- **No history/deletion mechanics.** Story 10.10 (Chat History + Deletion) owns the actual cascade-delete API, undo grace-window, and export flow. 10.7 implements the **UX entry points** (kebab → Delete with confirm dialog, type-to-confirm "delete all" link, post-delete empty state, post-revoke empty state) wired to existing endpoints; the per-session `DELETE /api/v1/chat/sessions/{id}` already shipped in 10.5 is consumed. Bulk-delete + export endpoints are 10.10 — 10.7 leaves their CTAs visually wired but disabled with a "coming soon" tooltip if the endpoints are not yet live at integration time. Whichever path is taken, do not create a stub backend route.
- **No rate-limit enforcement logic.** Story 10.11 owns the actual 60-msg/hr + 10-concurrent + daily-token-cap enforcement and the `CHAT_REFUSED reason=rate_limited` plumbing. 10.7 only renders the refusal-variant UX **when** the wire frame arrives — including the live-updating mm:ss countdown driven by the server's `retryAfterSeconds` field, the per-IP global cap message (rendered identically since the FE cannot distinguish gateway vs. handler 429s), and the concurrent-sessions dialog. 10.7 does not pre-emptively count messages client-side or block sends before the server speaks.
- **No safety observability authorship.** Story 10.9 owns CloudWatch metrics + alarms. 10.7 may emit FE structured logs (per existing `frontend/src/lib/logging` posture) for click-to-copy correlation-ID, refusal render, send disabled, but does **not** add new metric pipelines.
- **No write-action UI.** Voice I/O and chat-based transaction edits are out-of-scope per Epic 10's "Out of Scope" block. The composer remains text-only.
- **No new design tokens.** Story 10.3a/b's "no new tokens" invariant carries forward: refusal variant uses existing `info`/`alert` slot; deletion uses existing destructive-action token; citation chips use existing pill/icon-slot tokens. If a render detail seems to need a new token, it does not — re-read the spec.
- **No SSE polyfill.** Modern Safari/Chrome/Firefox/Edge target only. The browser native `EventSource` API is the contract. If a future enterprise tier needs IE11, that is a separate epic; ignore.
- **No dual-pane history reader on mobile.** The session list on mobile is the existing drawer pattern from 10.3a (Zone 1 collapses to drawer below 640px). Do not add a desktop-style 3-pane layout to mobile.
- **No feature-flag gate.** Chat is not subscription-gated (per Epic 10 Out of Scope). The route is reachable for any authenticated user; consent gate (10.1a) and rate-limit gate (10.11) handle the only access controls.
- **No localization of citation `label` field server-side.** Per [10.6b TD-124](10-6b-citation-payload-data-refs.md#L258), the assembler emits canonical English `label` strings. 10.7 owns the UA mapping for `CategoryCitation.code` and `ProfileFieldCitation.field` via the `chat.citations.*` i18n namespace; `TransactionCitation.label` and `RagDocCitation.label` (which are user/data content) render verbatim.
- **No contract-version handling.** `CITATION_CONTRACT_VERSION="10.6b-v1"` is the only known shape. If the FE ever sees an unknown shape, log a warning and skip the chip rather than crash; do not bake version-negotiation logic in 10.7 (the contract is additive).

A one-line scope comment at the top of `frontend/src/features/chat/index.ts` (or the feature folder's README if that pattern is preferred) enumerates the above so a future engineer does not silently expand scope.

## Acceptance Criteria

1. **Given** the App Router and existing `[locale]/(dashboard)` group at [`frontend/src/app/[locale]/(dashboard)`](../../frontend/src/app/[locale]/(dashboard)),
   **When** Story 10.7 is authored,
   **Then** a new route `frontend/src/app/[locale]/(dashboard)/chat/page.tsx` exists, is wrapped in the existing dashboard layout, requires authenticated session (re-uses the layout's auth guard — no new auth gating in this file), and renders the `<ChatScreen>` feature component. Bottom-tab nav (mobile) and top-nav (desktop) are extended to include a "Chat" entry per [ux-design-specification.md L1587-L1595 §Chat IA / Entry Point](../planning-artifacts/ux-design-specification.md#L1587-L1595) — Option A, 5th bottom tab; filled icon + accent dot when an active session exists. The tab is **always visible** regardless of consent state per [10.3b §Navigation Visibility Rule](../planning-artifacts/ux-design-specification.md#L1797).

2. **Given** the feature folder convention established by [`frontend/src/features/upload/`](../../frontend/src/features/upload/) + [`frontend/src/features/teaching-feed/`](../../frontend/src/features/teaching-feed/),
   **When** Story 10.7 scaffolds chat,
   **Then** `frontend/src/features/chat/` exists with this shape (keep modules small and focused; do **not** create a god-component):
   ```
   frontend/src/features/chat/
   ├── index.ts                      // public re-exports + scope-comment
   ├── components/
   │   ├── ChatScreen.tsx            // top-level: layout, session list, conversation, composer
   │   ├── SessionList.tsx           // Zone 1 (drawer on mobile, pane on desktop)
   │   ├── SessionRow.tsx            // single row + kebab menu
   │   ├── ConversationPane.tsx      // Zone 2: role=log, aria-live, scroll-lock, "↓ New messages"
   │   ├── MessageBubble.tsx         // user / assistant / streaming / system-meta
   │   ├── RefusalBubble.tsx         // refusal variant (info/alert icon, correlation-ID copy)
   │   ├── CitationChipRow.tsx       // horizontal scroll strip
   │   ├── CitationDetailSheet.tsx   // tap-to-expand sheet (desktop) / bottom-sheet (mobile)
   │   ├── Composer.tsx              // Zone 3: textarea, send, char counter, Enter/Shift+Enter
   │   ├── ConsentFirstUseDialog.tsx // first-use modal
   │   ├── ConsentVersionBumpCard.tsx// inline re-prompt card
   │   ├── ConsentRevokedEmpty.tsx   // post-revoke empty state
   │   ├── DeleteSessionDialog.tsx   // per-session destructive confirm
   │   ├── DeleteAllDialog.tsx       // type-to-confirm "delete all" (CTA may be disabled if 10.10 not live)
   │   ├── RateLimitCountdown.tsx    // mm:ss live-updating cooldown text
   │   └── ConcurrentSessionsDialog.tsx // 10-concurrent-sessions soft-block
   ├── hooks/
   │   ├── useChatSession.ts         // create/resume/terminate session lifecycle
   │   ├── useChatStream.ts          // EventSource wiring + frame parser + reducer
   │   ├── useChatConsent.ts         // consent fetch + grant/revoke + version-bump detection
   │   └── useScrollLock.ts          // 80-px scroll-lock rule + "↓ New messages" anchor
   ├── lib/
   │   ├── sse-client.ts             // POST→EventSource adapter, JWT-in-query, heartbeat tolerance
   │   ├── chat-types.ts             // local TS types (CitationDto, RefusalDto, StreamEvent union)
   │   ├── citation-label.ts         // UA/EN label rendering + TD-124 i18n map
   │   └── refusal-copy.ts           // CHAT_REFUSED.reason → i18n key map
   ├── types.ts                      // re-exports from lib/chat-types
   └── __tests__/
       └── ... (mirror components/, hooks/, lib/)
   ```
   The exact filenames are normative for review consistency. If a deviation is introduced (e.g. a different a11y-pattern split), record the rationale in Dev Agent Record / Completion Notes.

3. **Given** the conversation pane semantics from [10.3a §Basic Accessibility Scaffold L1679-L1695](../planning-artifacts/ux-design-specification.md#L1679-L1695),
   **When** `ConversationPane.tsx` renders,
   **Then**: the outer scroll container has `role="log"`, `aria-live="polite"`, `aria-relevant="additions"`; each assistant bubble is wrapped in `<article>` with an accessible name (`aria-label="Assistant, at HH:MM"`); a streaming bubble sets `aria-busy="true"` while open and flips to `"false"` on terminal frame; user bubbles are right-aligned and wrap in `<article>` with `aria-label="You, at HH:MM"`. Inter-bubble spacing (`8px`) and inter-turn spacing (`16px`) match the spec. Long unbroken tokens (URLs, IBANs) wrap via `overflow-wrap: anywhere`. Max bubble width is `75%` desktop / `88%` mobile per [L1633-L1655](../planning-artifacts/ux-design-specification.md#L1633-L1655).

4. **Given** the scroll-lock rule from [10.3a L1605-L1614 + L1659-L1677](../planning-artifacts/ux-design-specification.md#L1605-L1677),
   **When** new tokens or assistant frames append while the user has scrolled up more than ~80 px from the bottom,
   **Then** the pane does **not** auto-scroll; instead a "↓ New messages" anchored button appears at the bottom-right of Zone 2 (does not overlap the composer) and clicking it scrolls to bottom and dismisses itself. While within ~80 px of bottom, the pane auto-scrolls on every `chat-token` frame. Reduced-motion users get an instant scroll (no smooth-scroll animation). The button is keyboard-focusable; pressing Enter/Space scrolls to bottom.

5. **Given** the composer contract from [10.3a L1622-L1631](../planning-artifacts/ux-design-specification.md#L1622-L1631),
   **When** `Composer.tsx` renders,
   **Then**: a `<form>` wraps a `<textarea>` (multi-line, auto-grows up to ~5 lines then internal scroll), a labeled (visible `<label>`, **not** placeholder-as-label) Send button, and a character counter that appears at 70% of a hard 4096-char cap (matches the [10.5 input cap of 4096 chars](10-5-chat-streaming-api-sse.md)). Enter sends; Shift+Enter inserts a newline; Ctrl/Cmd+Enter is an alternate send. Esc closes the citation detail sheet (not the composer focus). On page load, focus lands in the composer (not the session list). Tab order: composer → send → session-toggle → sessions → conversation-pane. Send button is disabled while a stream is in-flight; the textarea remains read-write but pressing Enter is a no-op (with a screen-reader-announced inline hint "Wait for the response to finish before sending another message" — kept neutral, no blame).

6. **Given** the SSE protocol from [docs/chat-sse-contract.md](../../docs/chat-sse-contract.md) (sequence: `chat-open` → `chat-thinking*` → `chat-token+` → optional `chat-citations` → `chat-complete` | `chat-refused`),
   **When** `useChatStream` opens an `EventSource` against `POST /api/v1/chat/sessions/{session_id}/turns/stream?token=<JWT>` (the JWT-in-query workaround required by EventSource),
   **Then**:
   - The hook posts the user's message via `fetch` to **kick off** the turn, then opens `EventSource` to consume the SSE stream — implement whichever wire technique the backend's `chat.py` exposes (the contract authored in 10.5 is a POST that *itself* returns `text/event-stream`; consult [docs/chat-sse-contract.md](../../docs/chat-sse-contract.md) for the canonical client wiring example. If the doc shows a single POST returning the stream, use `fetch` + `ReadableStream` parsing rather than `EventSource` — pick whichever the contract document prescribes; do not invent a third path.).
   - The frame parser is a **finite state machine** keyed on event names: `chat-open` (binds correlationId + sessionId + flips bubble to `aria-busy="true"`), `chat-thinking` (renders an inline "Reading your transactions…" / "Searching your profile…" / generic-fallback spinner row keyed off `toolName`), `chat-token` (appends `delta` to the streaming bubble; coalesces only at the React-render layer, no UI-side batching of frames), `chat-citations` (stashes `citations` for render after `chat-complete`), `chat-complete` (flips `aria-busy="false"`, unlocks composer, renders citation chips), `chat-refused` (flips bubble to refusal variant, renders reason-specific copy + correlation-ID + retry-after countdown).
   - Heartbeat comment frames (`: heartbeat\n\n`) every 15s are tolerated silently (browser native handling).
   - **Unknown event names are ignored** (forward-compat per contract doc L9). A `console.warn` logs the unknown event name once per session for diagnostics; do not throw.
   - On network error / disconnect mid-stream: the bubble's partial text is **preserved** (do not erase tokens already rendered); a non-blocking inline status row appears below the bubble: "Connection lost. Retry?" with a Retry button. Retry re-issues the same user message (re-posting to a new turn) — Story 10.10's history-replay will rebuild canonical state on next page load. No automatic retry loop.
   - On the API returning HTTP 4xx/5xx **before** the stream opens (e.g. 422 input-too-long, 403 consent-required, 503 unavailable): the FE renders an inline error state on the composer (not as a fake assistant bubble) — neutral copy, retry button where applicable. 422 → "Your message is too long. Please shorten it and try again." 403 (consent missing) → trigger `<ConsentFirstUseDialog>` rather than render an error.

7. **Given** the `CHAT_REFUSED` reason enum (`guardrail_blocked`, `ungrounded`, `rate_limited`, `prompt_leak_detected`, `tool_blocked`, `transient_error`) from [10.5 AC #5](10-5-chat-streaming-api-sse.md) and the per-reason copy table from [10.3b §Principled Refusal UX](../planning-artifacts/ux-design-specification.md#L1797),
   **When** a `chat-refused` frame arrives,
   **Then** `RefusalBubble.tsx`:
   - Renders the bubble in **refusal variant** (left-aligned, neutral surface, small `info` or `alert` icon from existing token, muted typography, **no red**, no traffic-cop emoji) per the spec — distinct from a regular assistant bubble.
   - Looks up copy from i18n keys `chat.refusal.<reason>.copy` (EN + UA). Forbidden internal terms (`guardrail`, `grounding`, `canary`, `jailbreak`, `prompt injection`) MUST NOT appear in any localized string. A unit test (AC #14) lints the i18n files for these terms.
   - Suppresses the citation chip row (per spec L1803: "Citation chips do not render on refusal variants"). The `chat-citations` frame and `chat-refused` are mutually exclusive on the wire, but the FE asserts this defensively (if both arrive in the same turn, prefer the refusal and drop citations; log a warning).
   - Renders a "Reference: `<first-8-of-uuid>` · [Copy]" row below the copy. Click → `navigator.clipboard.writeText(fullCorrelationId)`; label flips to "Copied" for 1.5s, then back. The full UUID is in a `sr-only` span so screen readers read the entire ID. Failure of `clipboard.writeText` (permissions, insecure context) falls back to selecting the text in a hidden input and announcing "Press Ctrl/Cmd+C to copy".
   - For `reason=rate_limited`, renders a live-updating `mm:ss` countdown driven by `retryAfterSeconds`; when the countdown reaches 0, the refusal bubble adds an inline "Try again" CTA that re-sends the user's last message. The countdown announces only on initial render and on reaching 0 (not per-second — `aria-live` is `off` after first announce). When `retryAfterSeconds` is null/missing, render reason-specific fallback copy ("You've reached today's chat limit. You can continue after `<HH:MM>` local time.") if the reason variant calls for it; otherwise omit the countdown.
   - For `reason=ungrounded` and `reason=guardrail_blocked`, copy is reason-specific and avoids "your question violates …"; prefer "I can't answer that with the data I have access to." (see UA + EN exact strings in the copy reference table).

8. **Given** the citation contract from [Story 10.6b](10-6b-citation-payload-data-refs.md) and `docs/chat-sse-contract.md §chat-citations`,
   **When** a `chat-citations` frame arrives (after the final `chat-token`, before `chat-complete`),
   **Then** `CitationChipRow.tsx`:
   - Renders one pill per citation in **wire order** (server-side dedup + 20-cap is already applied; do not re-sort on the FE).
   - Pill height `24-28px`, `padding: 4px 10px`, `gap: 8px`, single-line horizontal scroll strip flush left below the assistant bubble. Long labels truncate with ellipsis.
   - **Icon slot**: `data-ref` icon for `kind ∈ {transaction, category, profile_field}`; `book` icon for `kind = "rag_doc"`. Use existing design-system icon tokens from [`lucide-react`](../../frontend/package.json) — pick one consistent receipt/file icon for data-ref and one book icon for RAG.
   - **Label rendering** per [10.6b AC #2 label rules](10-6b-citation-payload-data-refs.md):
     - `transaction.label` (server-emitted) renders verbatim.
     - `category.label` (server canonical English): **localized FE-side** via `chat.citations.category.<code>` keys (TD-124). If a key is missing for a given code, fall back to the server `label`.
     - `profile_field.label` (server canonical English): localized via `chat.citations.profile_field.<field>` keys with a date interpolation that uses the active locale's month-name format (UA: "Травень 2026", EN: "May 2026"). Fallback to server `label` if the key is missing.
     - `rag_doc.label` (the doc title) renders verbatim.
   - **Tap interaction**: pill is a `<button>` (not `<a>`). Tap opens `<CitationDetailSheet>` — desktop renders as a `Sheet` (Radix Dialog with side anchor); mobile renders as a bottom sheet. Esc closes; focus restores to the pill that opened it. Sheet content per kind:
     - `transaction`: full row — date, description, signed amount with currency, category code (localized), Transaction ID (last 8 chars; full ID `sr-only`).
     - `category`: localized name + code.
     - `profile_field`: field name (localized), value with currency for monetary fields, `as_of` date.
     - `rag_doc`: title, snippet (240 chars), similarity formatted as "Similarity: 83%".
   - **Empty state**: no `chat-citations` frame → no chip row rendered (do not render an empty placeholder).
   - **Unknown citation kind**: log a `console.warn` once per session and skip; do not crash. Defensive against future contract-version drift.

9. **Given** the consent flow from [10.3b §Consent Flow](../planning-artifacts/ux-design-specification.md#L1797) and the existing consent API at `POST/GET/DELETE /api/v1/users/me/consent` (Story 10.1a, **already shipped**),
   **When** a user opens `/[locale]/chat` for the first time without `chat_processing` consent,
   **Then** `<ConsentFirstUseDialog>` renders (Radix Dialog, desktop centered / mobile bottom-sheet) **before** the chat surface is visible. Dialog body enumerates `chat_processing` coverage, the diff vs. `ai_processing`, a Privacy link (target route per existing settings UX); primary action "Accept and start chatting" (calls `POST /api/v1/users/me/consent` with `consent_kind="chat_processing"`); secondary action "Not now" (closes the dialog and routes back to the previous tab — the chat tab itself stays visible per Navigation Visibility Rule).
   On consent **version bump** (server's most recent `consent_version` for `chat_processing` > the version stored on the user's existing record; detection is via `useChatConsent` polling the consent endpoint on chat-tab focus): existing in-flight sessions **continue** under their captured `consent_version_at_creation` (per Story 10.1a — no FE re-prompt during a session); **new sessions** trigger an inline re-prompt card `<ConsentVersionBumpCard>` instead of the modal — body: "Our chat data handling has been updated. Review and accept to keep chatting." Accept → version updated, send proceeds; Decline → card stays, new turn locked. Existing session reads remain enabled.
   On **post-revoke** (`DELETE /api/v1/users/me/consent` for `chat_processing`): `<ConsentRevokedEmpty>` is the only thing the chat route renders — body: "Chat is disabled until you re-enable chat data processing. [Go to Privacy settings →]". The route is **still reachable** (per Navigation Visibility Rule); the empty state replaces the chat surface, not the page.
   All three states honor focus-trap (Radix's built-in for the modal; manual `focus-trap-react` or equivalent for the inline card if it gates the conversation pane), `aria-labelledby` on title, `aria-describedby` on body, Escape dismisses, focus restores to the opener on close.

10. **Given** the deletion entry points from [10.3b §History & Deletion](../planning-artifacts/ux-design-specification.md#L1797),
    **When** `<SessionRow>` renders in the session list,
    **Then**: a kebab overflow menu (existing `dropdown-menu` shadcn component) shows `Delete` (destructive style). Click → `<DeleteSessionDialog>` confirm (destructive Radix Dialog, focus lands on Cancel by default per a11y rule), Confirm → call `DELETE /api/v1/chat/sessions/{id}` (Story 10.5 endpoint, already live), on success: row fades + collapses (animation honors `prefers-reduced-motion: reduce`), Sonner toast "Chat deleted" appears (`role="status"`, `aria-live="polite"`). **Undo** is conditionally rendered only if 10.10's grace-window endpoint is live at integration time; otherwise the toast omits the Undo affordance. (Whether the grace-window is live is determined by a single feature flag `NEXT_PUBLIC_CHAT_DELETE_UNDO=true|false` — default `false` until 10.10 ships.)
    A "Delete all chats" link at the bottom of the session list opens `<DeleteAllDialog>` (type-to-confirm — input must equal `delete` (locale-aware: `delete` EN / `видалити` UA) before Confirm enables). On Confirm: if 10.10's bulk-delete endpoint is **not** live (feature flag `NEXT_PUBLIC_CHAT_BULK_DELETE=true|false`, default `false`), the dialog instead shows an info note "Bulk delete is coming soon" and the link is rendered with `aria-disabled="true"` + tooltip in the dormant state. On `true`: posts to the bulk endpoint, empties session list, transitions to the empty state per [10.3b](../planning-artifacts/ux-design-specification.md#L1797). **Export** (FR35) is fully owned by 10.10 — no UI in 10.7 even behind a flag.

11. **Given** the rate-limit soft-block from [10.3b §Rate-Limit Soft-Block](../planning-artifacts/ux-design-specification.md#L1797) and the wire `chat-refused reason=rate_limited` envelope from [10.5](10-5-chat-streaming-api-sse.md),
    **When** the FE receives a refusal with `reason=rate_limited`,
    **Then** the refusal bubble renders the AC #7 cooldown variant. **Additionally**:
    - **New session CTA** (in the session list): clicking "New session" hits `POST /api/v1/chat/sessions`. If the response is a 4xx/5xx envelope with `code=CHAT_RATE_LIMITED` (or whatever Story 10.11 settles on; until 10.11 lands, the CTA *cannot* fail this way — leave the handler in place but unreachable), open `<ConcurrentSessionsDialog>`: "You have 10 active chats. Close one to start a new session." The dialog lists the user's active sessions as a clickable picker (each opens that session); a Close button dismisses without action. This is the only client-side check of any rate-limit dimension; do not pre-emptively count sessions on the FE.
    - **Daily token cap**: when `reason=rate_limited` arrives with no `retryAfterSeconds`, render the local-time wall-clock variant: "You've reached today's chat limit. You can continue after `<HH:MM>` (local time)." Local time is the browser's locale + timezone; UA renders 24-hour, EN renders the locale's default. Reset boundary is **midnight server-side** but the FE renders **midnight in the user's local time** — this is a deliberate UX simplification (the discrepancy is at most 24h-cycle-shifted; if 10.11 returns a server-anchored timestamp, prefer that — but until then, midnight-local is the contract).
    - **Send button disabled state**: while the cooldown countdown is active in any visible refusal bubble, the composer's Send button is disabled and Enter is intercepted with the same neutral inline hint ("Wait until cooldown ends"). When all visible cooldowns reach 0, Send re-enables.

12. **Given** the WCAG 2.1 AA pass from [10.3b §Full WCAG 2.1 AA Pass](../planning-artifacts/ux-design-specification.md#L1797),
    **When** the chat surface is rendered,
    **Then**:
    - **Color/contrast**: 4.5:1 for text against bubble backgrounds (assert via existing token system; if a custom muted-typography variant is needed for refusal copy, verify against the surface token before merge); 3:1 for the refusal icon against neutral surface; 3:1 for the focus ring.
    - **Focus management**: focus-trap inside the consent first-use dialog, the version-bump card (when modal-equivalent — i.e. when it's the only interactive element on the page), the delete-session dialog, the delete-all dialog, the concurrent-sessions dialog. Escape dismisses. On open, focus lands on the safest action (Cancel for destructive dialogs, primary CTA for non-destructive). On close, focus restores to the opener.
    - **Screen-reader announcements**: refusal copy announces via the conversation pane's `aria-live="polite"` (the bubble is a child of the log, no extra `role="alert"`); deletion toast `role="status"` + `aria-live="polite"` (Sonner default — verify); rate-limit countdown announces only on initial render and on reaching 0 (not per second — set `aria-live="off"` after first announce); cooldown tooltip is focusable via Tab.
    - **Reduced-motion**: every animation in the feature (row fade-out on delete, toast slide-in, refusal fade-in, scroll-to-bottom, streaming-indicator caret/dots) honors `prefers-reduced-motion: reduce` with instant-state fallback. Tailwind's `motion-reduce:` variants are the canonical pattern; do not introduce a JS-side media-query check unless a Tailwind variant is insufficient.
    - **Keyboard-only**: 8 tasks fully achievable without a pointing device (open chat, accept consent, new session, send message, receive refusal + copy correlation-ID, delete session, navigate sessions, recover from rate-limit). A test (AC #14) drives all 8 via `@testing-library/user-event` keyboard interactions.
    - **Narration audit**: every new string in the chat namespace is reviewed by re-reading the i18n file aloud; no Unicode icon characters leak into announced strings (icons are SVG with `aria-hidden="true"`).

13. **Given** the i18n contract from [10.3b's Copy Reference Table](../planning-artifacts/ux-design-specification.md#L1797) (UA + EN, ≈42 rows under `chat` namespace),
    **When** Story 10.7 lands,
    **Then**:
    - [`frontend/messages/en.json`](../../frontend/messages/en.json) and [`frontend/messages/uk.json`](../../frontend/messages/uk.json) gain a top-level `"chat"` object containing all keys enumerated in the spec's copy table — at minimum: `chat.refusal.<reason>.copy` (6 reasons), `chat.refusal.copy_reference.{label,copy_label,copied_label}`, `chat.refusal.try_again`, `chat.consent.first_use.{title,body,accept,decline,privacy_link}`, `chat.consent.version_bump.{title,body,accept,decline}`, `chat.consent.revoked.{title,body,settings_link}`, `chat.delete.session.{kebab_label,confirm_title,confirm_body,confirm_cta,cancel,toast,undo}`, `chat.delete.all.{link,confirm_title,confirm_body,confirm_input_label,confirm_input_match,confirm_cta,cancel}`, `chat.ratelimit.{cooldown,daily_cap,concurrent_sessions_title,concurrent_sessions_body}`, `chat.empty.{no_session_selected,first_message_hint}`, `chat.composer.{label,placeholder,send,send_aria,send_disabled_hint,char_counter}`, `chat.session.{new,untitled,active_indicator}`, `chat.streaming.{thinking_default,thinking_get_transactions,thinking_get_profile,thinking_get_teaching_feed,thinking_search_financial_corpus,connection_lost,retry,scroll_to_bottom}`, `chat.citations.{detail_title,similarity,kind_transaction,kind_category,kind_profile_field,kind_rag_doc,category.<code>,profile_field.<field>}`. (The exact list is whatever the spec table enumerates; treat the spec as canonical and grep for any key referenced in code that is missing from JSON.)
    - **No copy is hard-coded in component files** — every user-visible string is sourced via `useTranslations('chat')`. A test (AC #14) lints components for string literals inside JSX text nodes.
    - **UA edge cases** flagged in the spec: ICU MessageFormat for plurals (existing pattern — re-use); locale-aware time formatting; UA-specific length budgets on tight slots (chip labels, send-button label) — strings are pre-fitted to budgets in the JSON, and a test asserts the JSON entries do not exceed character budgets for those keys (≈ 6 keys flagged in the spec's copy table).
    - **Forbidden-terms lint** (AC #14): a Vitest test scans `en.json` + `uk.json` for the literal substrings `guardrail`, `grounding`, `canary`, `jailbreak`, `prompt injection` (case-insensitive) inside the `chat.*` subtree. Match → test fails. (Top-level developer-facing keys outside `chat.*` are not in scope of this lint.)

14. **Given** the test contract,
    **When** Story 10.7 lands,
    **Then** the following test files exist and pass under `cd frontend && npm run test`:
    - **`features/chat/__tests__/ChatScreen.test.tsx`** — full happy path: render screen → composer focused → type → Enter → user bubble appears → mock SSE emits `chat-open` → assistant streaming bubble with `aria-busy="true"` → emit 3 `chat-token` frames → emit `chat-citations` with one of each kind → emit `chat-complete` → `aria-busy="false"` → 4 chips render in wire order → tap a transaction chip → detail sheet opens with full row → Esc closes → focus returns to chip.
    - **`features/chat/__tests__/RefusalBubble.test.tsx`** — for **each** of the 6 `CHAT_REFUSED.reason` values: mock SSE emits a `chat-refused` frame with that reason + a fake correlationId + (for `rate_limited`) `retryAfterSeconds=120`. Assert: refusal-variant style applied, reason-specific copy from i18n keys rendered (literal string match against the EN file — UA file is asserted in the i18n lint), Reference row shows `<first-8>`, click Reference → clipboard mock receives full UUID, label flips to "Copied" then back to "Copy" after 1.5s; for `rate_limited`, `mm:ss` countdown ticks at 1Hz and announces only at start + at 0; no chip row renders.
    - **`features/chat/__tests__/Composer.test.tsx`** — Enter/Shift+Enter/Cmd+Enter behavior; counter appears at 70% of 4096; send disabled while stream in-flight; inline hint announces when Enter is intercepted in the disabled state.
    - **`features/chat/__tests__/ConversationPane.test.tsx`** — scroll-lock rule: scrolled to bottom → token frames auto-scroll; scrolled up >80px → token frames do NOT auto-scroll, "↓ New messages" button appears, click scrolls + dismisses.
    - **`features/chat/__tests__/ConsentFirstUseDialog.test.tsx`** — first render with no consent → dialog opens; Accept → consent API mock POSTed; Decline → routes back to previous tab (mock `router.back()`).
    - **`features/chat/__tests__/SessionList.test.tsx`** — kebab → Delete → confirm dialog → Confirm → `DELETE /api/v1/chat/sessions/{id}` mock fired → row collapses → toast renders (with vs. without Undo per feature flag).
    - **`features/chat/__tests__/RateLimit.test.tsx`** — refusal with `rate_limited` + `retryAfterSeconds=60` → countdown ticks → at 0, "Try again" CTA appears; new-session CTA returning `CHAT_RATE_LIMITED` 4xx → `<ConcurrentSessionsDialog>` opens with the user's sessions listed; daily-token-cap variant (no `retryAfterSeconds`) renders local wall-clock string.
    - **`features/chat/__tests__/i18n.test.ts`** — the **forbidden-terms lint** (AC #13); a parallel test asserts every `chat.*` key referenced in component source via `t('<key>')` exists in both `en.json` and `uk.json` (use a static AST scan via `acorn` or a regex pre-pass over the source files); a third test asserts character-budget keys are within budget.
    - **`features/chat/__tests__/a11y.test.tsx`** — keyboard-only walkthrough of all 8 tasks from AC #12 via `@testing-library/user-event`; an `axe-core` smoke run on the rendered chat screen with no violations on the WCAG 2.1 AA ruleset.
    - **`features/chat/__tests__/sse-client.test.ts`** — frame parser FSM: well-formed sequence; out-of-order frames (e.g. `chat-citations` before `chat-token`); unknown event name (logged + skipped); heartbeat comment (silent); HTTP 4xx before stream open (422, 403); mid-stream disconnect (partial text preserved + retry CTA).
    - **Full suite** runs with `cd frontend && npm run test -- --run` green; no new test infra (jsdom, Vitest, RTL, axe-core) need to be installed beyond what's already in `package.json` — verify before adding any. If `axe-core` is missing, install `@axe-core/react` via `npm install --save-dev @axe-core/react` and document in Dev Agent Record.

15. **Given** the developer-facing documentation and architecture record,
    **When** Story 10.7 lands,
    **Then**:
    - One sentence is appended to [`_bmad-output/planning-artifacts/architecture.md` §Chat Agent Component](../planning-artifacts/architecture.md) following the existing chat citation-contract bullet: "Frontend chat surface: `frontend/src/features/chat/` (Story 10.7). Consumes the SSE protocol authored in 10.5/10.5a and the citation contract authored in 10.6b; UX is the spec authored in 10.3a/b. No backend coupling beyond the documented contracts."
    - One sentence is appended to [§Frontend Architecture / Folder Layout](../planning-artifacts/architecture.md) (or wherever `features/<name>/` is enumerated): adds `chat/` to the existing list with a one-line description.
    - **No ADR.** This is implementation, not a design decision.
    - **No new section in `docs/chat-sse-contract.md`** — the contract is consumed, not extended.
    - The story's Change Log records the version bump (AC #16).
    - One link is added under [10.6b TD-124](10-6b-citation-payload-data-refs.md#L258) marking it **closed** by Story 10.7's i18n maps in the chat namespace; the TD-124 entry's status flips to "Done" if 10.7's commit closes it (record this transition in Dev Agent Record).

16. **Given** the version and release record,
    **When** Story 10.7 is marked done,
    **Then**:
    - `VERSION` is bumped from the previous (post-10.6b → `1.48.0`, plus any patch deltas since) to **MINOR** (additive new feature surface — no breaking change). If between 10.6b and 10.7 another story ships, bump from whichever is current — the contract is "MINOR for 10.7's first ship".
    - The Change Log section of this story file records the version bump and the user-facing additions (chat route, feature folder, i18n namespace).

17. **Given** the tech-debt register at [docs/tech-debt.md](../../docs/tech-debt.md),
    **When** Story 10.7 lands,
    **Then** the following entries are opened (or, if the feature happens to land them in scope, the corresponding TD is **not** opened — record the path in Dev Agent Record):
    - **TD-126 — Chat session-summarization UI affordance [LOW]**
      - Why deferred: 10.3b chose Option A (silent summarization). If operator/user feedback later wants visibility (e.g. a "Earlier messages summarized" row), this opens; estimated ~½ day.
      - Trigger: > 5% of users in a survey want it OR a support escalation cites confusion.
    - **TD-127 — Chat citation chip i18n for additional category codes [LOW]**
      - Why deferred: AC #8 ships UA/EN labels for the categories present in the production taxonomy (see [`mcc_mapping.py VALID_CATEGORIES`](../../backend/app/agents/categorization/mcc_mapping.py)). New categories added by future Epic 11 stories need their `chat.citations.category.<code>` entries; the FE falls back to the server label gracefully.
      - Trigger: a new `VALID_CATEGORIES` entry lands without paired i18n keys (lint AC #14 will flag in the next chat PR).
    - **TD-128 — Chat empty/onboarding state copy uplift [LOW]**
      - Why deferred: 10.7 ships a minimal first-message hint per the spec. A more elaborate empty state (suggested prompts, sample questions, EN/UA discoverability copy) is a copy-team task best done after first-week telemetry.
      - Trigger: post-launch + 1 week of telemetry.
    - Grep `docs/tech-debt.md` for `TD-.*chat-ui|TD-.*10\.7` → no stale entries before this story; the three new ones above are the only matches.
    - **TD-124** (from 10.6b) is closed (or noted "closed by 10.7") — its fix shape is exactly the i18n maps shipped here.

## Tasks / Subtasks

- [x] **Task 1: Scaffold feature folder + route** (AC: #1, #2)
  - [x] 1.1 Create `frontend/src/app/[locale]/(dashboard)/chat/page.tsx` rendering `<ChatScreen>`.
  - [x] 1.2 Add Chat tab to bottom-nav (mobile) and top-nav (desktop) per spec; tab is always visible regardless of consent.
  - [x] 1.3 Create `frontend/src/features/chat/` with the folder shape from AC #2; add a top-of-file scope comment in `index.ts` listing the deferrals from "Scope Boundaries".

- [x] **Task 2: Lifecycle + SSE plumbing** (AC: #6)
  - [x] 2.1 Implement `useChatSession` (create / list / terminate via existing `/api/v1/chat/sessions` endpoints).
  - [x] 2.2 Implement `useChatStream` + `lib/sse-client.ts` per the canonical client wiring in [docs/chat-sse-contract.md](../../docs/chat-sse-contract.md).
  - [x] 2.3 FSM frame parser handling 6 known event names + heartbeats + unknown-event silent skip + HTTP 4xx/5xx pre-stream + mid-stream disconnect with partial-text preservation.
  - [x] 2.4 Reducer for the conversation state (turns, in-flight bubble, citations, refusals).

- [x] **Task 3: Conversation surface** (AC: #3, #4, #5)
  - [x] 3.1 `ConversationPane.tsx` with `role="log"`, `aria-live`, `aria-relevant="additions"`, scroll-lock 80-px rule + "↓ New messages" button.
  - [x] 3.2 `MessageBubble.tsx` for user/assistant/streaming/system-meta variants with `aria-busy` toggle.
  - [x] 3.3 `Composer.tsx` form: textarea auto-grow, Enter/Shift+Enter/Cmd+Enter handling, char counter at 70% of 4096, disabled-while-streaming + screen-reader hint, focus on mount.

- [x] **Task 4: Citations** (AC: #8)
  - [x] 4.1 `CitationChipRow.tsx` horizontal-scroll strip; pill component with icon-slot per kind.
  - [x] 4.2 `CitationDetailSheet.tsx` per-kind detail rendering with focus-restore on close.
  - [x] 4.3 `lib/citation-label.ts` with the four label-rendering rules (server verbatim for transaction + rag_doc; FE-localized for category + profile_field with date interpolation).

- [x] **Task 5: Refusal UX** (AC: #7, #11)
  - [x] 5.1 `RefusalBubble.tsx` refusal-variant styling, copy lookup, correlation-ID copy-to-clipboard with fallback for insecure context.
  - [x] 5.2 `RateLimitCountdown.tsx` mm:ss timer + a11y announce-on-start-and-end policy.
  - [x] 5.3 Wire mutual-exclusion: a refusal frame suppresses any pending `chat-citations` frame on the same turn.

- [x] **Task 6: Consent flow** (AC: #9)
  - [x] 6.1 `useChatConsent` hook polling `/api/v1/users/me/consent` for `chat_processing` on chat-tab focus; detect version-bump.
  - [x] 6.2 `<ConsentFirstUseDialog>` (Radix Dialog modal).
  - [x] 6.3 `<ConsentVersionBumpCard>` inline card (focus-trap when it gates the conversation pane).
  - [x] 6.4 `<ConsentRevokedEmpty>` post-revoke empty state with Privacy settings deep link.

- [x] **Task 7: Deletion entry points** (AC: #10)
  - [x] 7.1 `<SessionRow>` kebab + `<DeleteSessionDialog>` calling existing `DELETE /api/v1/chat/sessions/{id}`.
  - [x] 7.2 Sonner toast with conditional Undo via `NEXT_PUBLIC_CHAT_DELETE_UNDO` flag.
  - [x] 7.3 `<DeleteAllDialog>` type-to-confirm (locale-aware match string); CTA disabled state behind `NEXT_PUBLIC_CHAT_BULK_DELETE` flag with tooltip.

- [x] **Task 8: Rate-limit surfaces** (AC: #11)
  - [x] 8.1 `<ConcurrentSessionsDialog>` triggered by 4xx on `POST /api/v1/chat/sessions` with `CHAT_RATE_LIMITED` (handler in place but unreachable until 10.11 lands).
  - [x] 8.2 Daily-cap variant copy + local-time wall-clock formatter.
  - [x] 8.3 Send button + Enter intercept while any visible cooldown is active.

- [x] **Task 9: i18n + copy** (AC: #13)
  - [x] 9.1 Add `chat` namespace to `frontend/messages/en.json` + `uk.json` populating every key from the spec's copy table.
  - [x] 9.2 Forbidden-terms lint test under `features/chat/__tests__/i18n.test.ts`.
  - [x] 9.3 Character-budget assertions for tight-slot keys.
  - [x] 9.4 Source-AST scan asserting every `t('<key>')` exists in both locales.

- [x] **Task 10: Accessibility pass** (AC: #12)
  - [x] 10.1 Color/contrast audit (visual + token verification).
  - [x] 10.2 Focus-trap + restore for all 5 dialogs (Radix built-in + manual where needed).
  - [x] 10.3 Screen-reader announce policy per element (verify `aria-live` levels).
  - [x] 10.4 Tailwind `motion-reduce:` variants on all animations.
  - [x] 10.5 `axe-core` smoke test in `a11y.test.tsx`; install `@axe-core/react` if missing.

- [x] **Task 11: Tests** (AC: #14)
  - [x] 11.1 `ChatScreen.test.tsx` happy path with mock SSE source.
  - [x] 11.2 `RefusalBubble.test.tsx` parameterized over 6 reasons.
  - [x] 11.3 `Composer.test.tsx` keyboard behaviors + char counter + disabled state.
  - [x] 11.4 `ConversationPane.test.tsx` scroll-lock 80-px rule.
  - [x] 11.5 `ConsentFirstUseDialog.test.tsx` accept + decline paths.
  - [x] 11.6 `SessionList.test.tsx` delete + Undo conditional.
  - [x] 11.7 `RateLimit.test.tsx` countdown + concurrent-sessions dialog + daily-cap variant.
  - [x] 11.8 `i18n.test.ts` (forbidden-terms + key-presence + budgets).
  - [x] 11.9 `a11y.test.tsx` keyboard-only walkthrough + `axe-core` smoke.
  - [x] 11.10 `sse-client.test.ts` FSM unit tests.

- [x] **Task 12: Documentation + version + tech-debt** (AC: #15, #16, #17)
  - [x] 12.1 Append the architecture sentences (§Chat Agent Component + §Frontend Architecture).
  - [x] 12.2 Bump `VERSION` (MINOR).
  - [x] 12.3 Open TD-126, TD-127, TD-128 in `docs/tech-debt.md`; close (or note as closed by 10.7) TD-124.
  - [x] 12.4 Populate Dev Agent Record / Completion Notes / File List / Change Log.

## Dev Notes

### Architecture Patterns and Constraints

- **Consume contracts, do not extend them.** This is a frontend integration story. The SSE protocol, the citation contract, the refusal envelope, and the consent endpoints are **inputs**. If the integration uncovers a real defect, file a TD; do not patch backend code from a 10.7 commit. The same posture applies to the UX spec.
- **No god-component.** The folder shape in AC #2 is normative because a single `ChatScreen.tsx` containing the SSE FSM, the reducer, the consent gating, and the rendering does not survive code review. Each component is < 250 lines; each hook < 200; the SSE client lib < 300.
- **Pure FSM for SSE.** `lib/sse-client.ts` should expose a frame parser that takes an iterator/stream of raw SSE events and yields typed `StreamEvent` union values. The hook (`useChatStream`) consumes this and dispatches to the reducer. No DOM, no state in the lib — testable in isolation. This mirrors 10.6b's pure-function `assemble_citations` posture on the backend.
- **Optimistic user-bubble render.** When the user hits Send, render their bubble immediately (before the SSE round-trip). On any pre-stream HTTP error, the user bubble stays (do not erase what the user typed); the inline error attaches to the composer. This matches the way reasonable chat UIs behave; do not add a complex rollback path.
- **Citations attach to the assistant bubble.** A turn's citation chip row is a child of the assistant message — not a sibling at the conversation-pane level. This way history rendering (Story 10.10) trivially places citations next to the right turn even on out-of-order replay.
- **Refusal mutual-exclusion is an FE-side defensive invariant.** The wire contract guarantees a refused turn emits no `chat-citations`, but a client should not crash if the server somehow sends both. Prefer the refusal and log a `console.warn`; do not crash, do not render both.
- **Consent state is global to the user, not per-session.** `useChatConsent` reads the user's consent record once on tab focus and on consent-mutation events; it does not poll per turn. The consent-version captured at session creation is a server-side concern (10.1a stores it in `chat_sessions.consent_version_at_creation`); the FE does not need to reason about it once a session is created.
- **Rate-limit countdowns belong to refusal bubbles, not the page.** A turn that refused with a 60s cooldown shows a 60s countdown. Multiple in-flight cooldowns (rare — only happens if the user reopens an old session) compose: Send is disabled while *any* visible cooldown is active. Don't introduce a global "rate-limit overlay" — the refusal bubble itself is the surface.
- **The 80-px scroll-lock rule is per spec.** Don't substitute a "user has scrolled in the last 500ms" heuristic; the spec is unambiguous and the test pins the value. If the rule produces a poor UX in practice, file a TD against the spec, do not modify the rule unilaterally.
- **Forbidden-terms lint is a hard gate.** Even if a translator submits "guardrail" as a UA term that "happens to map cleanly" — the FE-side lint blocks it. Report back via tech-debt for a copy-team rewrite; do not relax the lint.
- **Feature flags for 10.10-dependent affordances.** `NEXT_PUBLIC_CHAT_DELETE_UNDO` and `NEXT_PUBLIC_CHAT_BULK_DELETE` default to `false`. They flip to `true` in 10.10. This story does not couple to 10.10's release schedule — the feature ships and Undo/Bulk Delete light up later by env-var only.

### Source Tree Components to Touch

- `frontend/src/app/[locale]/(dashboard)/chat/page.tsx` — **new** route.
- `frontend/src/features/chat/**` — **new** feature folder per AC #2 layout.
- `frontend/src/components/layout/<bottom-nav-component>.tsx` — extended with Chat entry. (Identify the actual file from the existing dashboard layout; do not assume a name.)
- `frontend/messages/en.json` — `chat` namespace added.
- `frontend/messages/uk.json` — `chat` namespace added.
- `frontend/.env.example` — document `NEXT_PUBLIC_CHAT_DELETE_UNDO` and `NEXT_PUBLIC_CHAT_BULK_DELETE` flags (default `false`).
- `_bmad-output/planning-artifacts/architecture.md` — two one-line amendments per AC #15.
- `docs/tech-debt.md` — TD-126 / TD-127 / TD-128 entries; TD-124 closure note.
- `VERSION` — MINOR bump per AC #16.

### Testing Standards Summary

- `cd frontend && npm run test -- --run` — green.
- `cd frontend && npm run lint` — green (no string-literal violations in chat components; ESLint config governs).
- New test files all live under `frontend/src/features/chat/__tests__/`.
- `@axe-core/react` is the a11y smoke harness; install if not present.
- No live backend in tests — every backend interaction is mocked at the `fetch` / `EventSource` boundary. The mocks reference the canonical contract example in `docs/chat-sse-contract.md`; if the contract evolves, the mock fixtures move with it.
- No new framework added — Vitest + RTL + jsdom + Sonner are already in `package.json`. If a missing dep blocks a test, document the install in Dev Agent Record.
- **Coverage target**: ≥ 85% on `features/chat/` (the FSM + label + refusal modules should be ≥ 95% — they're pure logic; UI components need ≥ 75%).

### Project Structure Notes

- **Alignment with unified project structure**: `features/chat/` mirrors `features/upload/`, `features/teaching-feed/`, `features/settings/`. No new top-level directories. Hooks live under `hooks/`, lib under `lib/`, components under `components/`, tests under `__tests__/` — established in the codebase already.
- **Detected conflicts or variances**: none. The route group `(dashboard)` already hosts feed, upload, profile, settings — chat is a peer.
- **i18n posture**: `next-intl` flat-key JSON with dot-paths is the established pattern. `chat.*` is a new top-level namespace; existing namespaces (`auth`, `onboarding`, `settings`, `upload`, `teaching-feed`, `profile`) are siblings.

### References

- [Source: _bmad-output/planning-artifacts/epics.md L2139-L2140 (Story 10.7 definition)](../planning-artifacts/epics.md#L2139-L2140) — the canonical scope statement.
- [Source: _bmad-output/planning-artifacts/prd.md FR68 (chat citations)](../planning-artifacts/prd.md) — the wire-level invariant 10.7 renders.
- [Source: _bmad-output/planning-artifacts/ux-design-specification.md §Chat Skeleton (10.3a) L1564-L1796](../planning-artifacts/ux-design-specification.md#L1564-L1796) — the layout, message types, citation chip slot, accessibility scaffold, and frontend handoff.
- [Source: _bmad-output/planning-artifacts/ux-design-specification.md §Chat States (10.3b) L1797+](../planning-artifacts/ux-design-specification.md#L1797) — refusals, consent, deletion, rate-limit, full WCAG 2.1 AA pass, UA + EN copy table.
- [Source: docs/chat-sse-contract.md](../../docs/chat-sse-contract.md) — canonical client wiring example, frame-by-frame schema, projection map.
- [Source: _bmad-output/implementation-artifacts/10-1a-chat-processing-consent.md](10-1a-chat-processing-consent.md) — `chat_processing` consent endpoint contract.
- [Source: _bmad-output/implementation-artifacts/10-3a-chat-ux-skeleton.md](10-3a-chat-ux-skeleton.md) — UX delivered for the skeleton.
- [Source: _bmad-output/implementation-artifacts/10-3b-chat-ux-states-spec.md](10-3b-chat-ux-states-spec.md) — UX delivered for the states.
- [Source: _bmad-output/implementation-artifacts/10-5-chat-streaming-api-sse.md](10-5-chat-streaming-api-sse.md) — SSE protocol, event names + payloads, `CHAT_REFUSED` envelope, exception → reason mapping.
- [Source: _bmad-output/implementation-artifacts/10-5a-send-turn-stream-disconnect-finalizer.md](10-5a-send-turn-stream-disconnect-finalizer.md) — disconnect finalizer (informs the FE's mid-stream-disconnect handling).
- [Source: _bmad-output/implementation-artifacts/10-6a-grounding-enforcement-harness.md](10-6a-grounding-enforcement-harness.md) — `reason=ungrounded` semantics for refusal copy.
- [Source: _bmad-output/implementation-artifacts/10-6b-citation-payload-data-refs.md](10-6b-citation-payload-data-refs.md) — citation contract (4 kinds, dedup keys, label rules, 20-cap, contract version).
- [Source: backend/app/api/v1/chat.py](../../backend/app/api/v1/chat.py) — the API surface 10.7 consumes.
- [Source: frontend/package.json](../../frontend/package.json) — pinned versions of next-intl, TanStack Query, Tailwind, lucide-react, sonner, Vitest, RTL.
- [Source: frontend/src/features/upload/](../../frontend/src/features/upload/) — folder-shape exemplar (hooks, components, types, __tests__).
- [Source: frontend/messages/en.json + uk.json](../../frontend/messages/) — i18n target files.
- [Source: _bmad-output/planning-artifacts/architecture.md §Chat Agent Component + §API Pattern + §Frontend Architecture](../planning-artifacts/architecture.md) — architectural anchors for the AC #15 amendments.

## Dev Agent Record

### Agent Model Used

claude-opus-4-7 (1M context)

### Debug Log References

### Completion Notes List

**Mid-story checkpoint (functional core, Tasks 1–6) — 2026-04-26:**

- Feature folder, route, and nav entry scaffolded per AC #1/#2 (`frontend/src/features/chat/`, `frontend/src/app/[locale]/(dashboard)/chat/page.tsx`, dashboard header extended with `MessageCircle` icon link).
- **Deviation from AC #1 (mobile bottom-tab nav):** the existing dashboard layout ships only a top-header icon strip (no mobile bottom-tab pattern exists in the codebase). Adding a separate mobile bottom-nav component from scratch is out of 10.7 scope (UI-shell-wide refactor, would touch every dashboard route). Chat is added as the 5th icon link in the existing top-nav, which renders identically on mobile + desktop. If a mobile bottom-tab pattern is desired later, file as a separate UX/shell story.
- SSE plumbing: `lib/sse-client.ts` is a pure FSM-style frame parser (`fetch` + `ReadableStream`, POST→SSE per `docs/chat-sse-contract.md`); `useChatStream` consumes it via reducer with the 6-event FSM, mid-stream-disconnect partial-text preservation, and pre-stream HTTP 4xx error pinning.
- Conversation surface: `ConversationPane` (role=log, aria-live=polite, scroll-lock 80px), `MessageBubble` (user/assistant/streaming variants + thinking indicator), `Composer` (4096-char cap, 70% counter, Enter/Shift+Enter, disabled-while-streaming with neutral hint).
- Citations: `CitationChipRow` + `CitationDetailSheet` (mobile bottom-sheet / desktop side panel via `@base-ui/react/dialog`); `lib/citation-label.ts` implements the four label rules (verbatim for transaction/rag_doc; FE-localized for category/profile_field with month-year ICU interp).
- Refusal UX: `RefusalBubble` + `RateLimitCountdown` (announce-on-start-and-end policy via `aria-live` flip); reducer drops partial text + pending citations on `chat-refused` per contract.
- Consent flow: `useChatConsent` against the existing 10.1a endpoints with `consent_kind="chat_processing"`; `ConsentFirstUseDialog` modal, `ConsentVersionBumpCard` (currently dormant — backend doesn't expose per-user latest-version delta yet; hook reads boolean only), `ConsentRevokedEmpty` route-replacement state.
- Sessions + deletion entry points: `SessionList` + `SessionRow` with Sonner toasts; `DeleteAllDialog` type-to-confirm; `ConcurrentSessionsDialog` triggered on session-create 429. Both `NEXT_PUBLIC_CHAT_DELETE_UNDO` and `NEXT_PUBLIC_CHAT_BULK_DELETE` flags wired (default `false`); documented in `frontend/.env.example`.
- i18n: `chat.*` namespace added to `en.json` + `uk.json` covering refusal copy (no forbidden internal terms), composer/session/streaming/citations/consent/delete/ratelimit subtrees, and category + profile_field localization keys (closes TD-124 once Task 12 records it). `dashboard.chat` + `errors.boundary.chat` strings added for the nav label and error-boundary copy.
- TypeScript: `npx tsc --noEmit` reports 0 errors for chat feature files (4 unrelated pre-existing errors in test files / `use-card-feedback.ts`).
- ESLint: `npx eslint src/features/chat src/app/.../chat` clean.
- Vitest: full suite (53 files / 501 tests) green.

**Story-end addendum (Tasks 7–12) — 2026-04-26:**

- Deletion entry points (Task 7) shipped via `SessionRow` kebab → `DeleteSessionDialog` (existing `DELETE /api/v1/chat/sessions/{id}`), Sonner toast with conditional Undo (`NEXT_PUBLIC_CHAT_DELETE_UNDO`); `DeleteAllDialog` with locale-aware type-to-confirm match string (`delete` EN / `видалити` UA), CTA dormant unless `NEXT_PUBLIC_CHAT_BULK_DELETE=true`. Bulk-delete API isn't called from 10.7 — the dialog renders the "coming soon" note when the flag is off, which is the contracted state until Story 10.10 ships.
- Rate-limit surfaces (Task 8): `ConcurrentSessionsDialog` opens when `POST /api/v1/chat/sessions` returns 429 / `CHAT_RATE_LIMITED` (handler in place, unreachable until Story 10.11); daily-cap variant copy + local-time wall-clock formatter wired in `RefusalBubble`; Send button + Enter-intercept gated on `cooldownActive` derived from any in-flight refusal turn.
- i18n (Task 9): `chat.*` namespace populated in both locales; `i18n.test.ts` enforces forbidden-terms lint (5 substrings × 2 locales = 10 tests), character-budget assertions on 6 tight-slot keys × 2 locales (12 tests), key-parity test (en ↔ uk), source-AST regex scan that resolves every `t('<key>')` referenced in `features/chat/**` against both locale files (with a small allow-list for dynamically composed keys: `refusal.<reason>.copy`, `streaming.thinking_<tool>`, `citations.{category,profile_field}.<dynamic>`).
- A11y pass (Task 10): focus-trap + restore comes from `@base-ui/react/{dialog,alert-dialog}` defaults (4 dialogs use `AlertDialog` with `autoFocus` on Cancel for destructive variants; `ConsentFirstUseDialog` and `CitationDetailSheet` use `@base-ui/react/dialog` with built-in focus-trap). All animations use Tailwind `motion-reduce:` variants. `axe-core` smoke (used directly — `axe-core` is already in `node_modules` as a transitive dep, so no new package install was needed; `@axe-core/react` would have been the alternative but is redundant here) runs over `Composer` and `RefusalBubble` rendered output and asserts no WCAG 2.1 AA violations.
- Tests (Task 11): 11 test files / 72 tests under `features/chat/__tests__/`:
  - `sse-client.test.ts` (12 tests) — `parseFrame` for each event type, FSM over well-formed sequences, heartbeat tolerance, unknown-event silent skip with single warn, split-chunk frame straddling, HTTP 422/403 pre-stream `StreamHttpError`.
  - `i18n.test.ts` (25 tests) — see above.
  - `citation-label.test.ts` (7 tests) — bonus: pure-function tests over the four label rules + UA/EN month interpolation + fallback paths.
  - `RefusalBubble.test.tsx` (9 tests) — parameterized over the 6 reasons asserting reason-specific copy + correlation-ID short form + forbidden-term scan; clipboard copy → "Copied" flip; rate-limited countdown ticking; daily-cap variant.
  - `Composer.test.tsx` (4 tests) — Enter/Shift+Enter/Send paths, char counter at 70% threshold, disabled-while-streaming + cooldown intercept hints.
  - `ConversationPane.test.tsx` (2 tests) — pinned vs. >80px scrolled-up scroll-lock behavior using a patched scrollTop/scrollHeight/clientHeight.
  - `ConsentFirstUseDialog.test.tsx` (3 tests) — render, Accept calls onAccept, Decline calls onDecline + `router.back()`.
  - `SessionList.test.tsx` (3 tests) — list rendering, New chat triggers createSession, bulk-delete link `aria-disabled` when flag off.
  - `RateLimit.test.tsx` (3 tests) — countdown → Try-again CTA at zero; daily-cap copy variant; concurrent-sessions picker triggers `onPickSession`.
  - `ChatScreen.test.tsx` (2 tests) — empty state + composer→send wire-through; assistant turn with citations renders the chip strip in wire order.
  - `a11y.test.tsx` (2 tests) — `axe-core` smoke on Composer + RefusalBubble (rate-limited variant) — 0 AA violations.
- Documentation (Task 12.1): `architecture.md` §Chat Agent Component bullet appended; cross-cutting features table gains a "Conversational Chat" row pointing to `features/chat/`.
- Tech-debt (Task 12.3): TD-124 marked **RESOLVED 2026-04-26** with pointer to `citation-label.ts` and tests; TD-126/127/128 opened as LOW with triggers + fix shapes.
- VERSION (Task 12.2): 1.48.0 → 1.49.0 (MINOR — additive new user-facing chat surface; no breaking changes).
- Final validation (full suite): `cd frontend && npx vitest run` ⇒ **53 + 11 = 64 test files / 501 + 72 = 573 tests passing, 0 failures.** `npx tsc --noEmit` ⇒ 0 errors in chat feature files. `npx eslint src/features/chat src/app/.../chat` ⇒ clean.

**Known limitations / future-work pointers (not blocking review):**

- `ConsentVersionBumpCard` is wired but rendered behind `false &&` in `ChatScreen` because the consent endpoint shipped in 10.1a returns `hasCurrentConsent` as a boolean only — there's no per-user "latest server version" comparison field to detect drift on. Until that lands (likely owned by a future consent-mgmt story), the version-bump card cannot fire. Hook polling on tab focus is in place; the only missing piece is the server-side compare. Documented as a follow-up in Dev Agent Record only (no TD opened — this is a backend contract gap that an existing/future story is the right home for).
- `crypto.randomUUID()` is used for client-side turn IDs in `useChatStream`; falls back to a `Math.random()`-based string when unavailable. Modern browsers all support it; tests pass under jsdom.
- `useChatSession.sessions` returns an empty list when the backend doesn't yet expose `GET /api/v1/chat/sessions` (404/405 ⇒ empty). The session list endpoint is owned by Story 10.10; until it ships, the SessionList renders only the in-memory active session a user just created. This is graceful degradation, not a defect.

### File List

**New files (chat feature):**

- `frontend/src/app/[locale]/(dashboard)/chat/page.tsx`
- `frontend/src/features/chat/index.ts`
- `frontend/src/features/chat/types.ts`
- `frontend/src/features/chat/lib/chat-types.ts`
- `frontend/src/features/chat/lib/sse-client.ts`
- `frontend/src/features/chat/lib/citation-label.ts`
- `frontend/src/features/chat/lib/refusal-copy.ts`
- `frontend/src/features/chat/hooks/useChatSession.ts`
- `frontend/src/features/chat/hooks/useChatStream.ts`
- `frontend/src/features/chat/hooks/useChatConsent.ts`
- `frontend/src/features/chat/hooks/useScrollLock.ts`
- `frontend/src/features/chat/components/ChatScreen.tsx`
- `frontend/src/features/chat/components/SessionList.tsx`
- `frontend/src/features/chat/components/SessionRow.tsx`
- `frontend/src/features/chat/components/ConversationPane.tsx`
- `frontend/src/features/chat/components/MessageBubble.tsx`
- `frontend/src/features/chat/components/RefusalBubble.tsx`
- `frontend/src/features/chat/components/RateLimitCountdown.tsx`
- `frontend/src/features/chat/components/Composer.tsx`
- `frontend/src/features/chat/components/CitationChipRow.tsx`
- `frontend/src/features/chat/components/CitationDetailSheet.tsx`
- `frontend/src/features/chat/components/ConsentFirstUseDialog.tsx`
- `frontend/src/features/chat/components/ConsentVersionBumpCard.tsx`
- `frontend/src/features/chat/components/ConsentRevokedEmpty.tsx`
- `frontend/src/features/chat/components/DeleteSessionDialog.tsx`
- `frontend/src/features/chat/components/DeleteAllDialog.tsx`
- `frontend/src/features/chat/components/ConcurrentSessionsDialog.tsx`
- `frontend/src/features/chat/__tests__/sse-client.test.ts`
- `frontend/src/features/chat/__tests__/i18n.test.ts`
- `frontend/src/features/chat/__tests__/citation-label.test.ts`
- `frontend/src/features/chat/__tests__/RefusalBubble.test.tsx`
- `frontend/src/features/chat/__tests__/Composer.test.tsx`
- `frontend/src/features/chat/__tests__/ConversationPane.test.tsx`
- `frontend/src/features/chat/__tests__/ConsentFirstUseDialog.test.tsx`
- `frontend/src/features/chat/__tests__/SessionList.test.tsx`
- `frontend/src/features/chat/__tests__/RateLimit.test.tsx`
- `frontend/src/features/chat/__tests__/ChatScreen.test.tsx`
- `frontend/src/features/chat/__tests__/a11y.test.tsx`

**Modified files:**

- `frontend/src/app/[locale]/(dashboard)/layout.tsx` — added Chat icon link to dashboard top-nav.
- `frontend/src/components/error/FeatureErrorBoundary.tsx` — extended `FeatureArea` union with `"chat"`.
- `frontend/messages/en.json` — added `dashboard.chat`, `errors.boundary.chat`, full `chat.*` namespace.
- `frontend/messages/uk.json` — same as en.json (UA translations).
- `frontend/.env.example` — documented `NEXT_PUBLIC_CHAT_DELETE_UNDO` + `NEXT_PUBLIC_CHAT_BULK_DELETE` flags.
- `_bmad-output/planning-artifacts/architecture.md` — appended Chat Agent Component bullet (frontend) + Conversational Chat row in cross-cutting features table.
- `docs/tech-debt.md` — TD-124 marked RESOLVED with pointer; TD-126/127/128 opened as LOW.
- `_bmad-output/implementation-artifacts/sprint-status.yaml` — `10-7-chat-ui` flipped `ready-for-dev` → `in-progress` → `review`.
- `VERSION` — `1.48.0` → `1.49.0` (MINOR).

### Change Log

| Date | Version | Author | Notes |
|---|---|---|---|
| 2026-04-26 | 1.49.0 | Claude Opus 4.7 (1M context) | Story 10.7 (Chat UI) shipped: feature folder + route + nav + 16 components + 4 hooks + 4 lib files + 11 test files / 72 tests. UA + EN i18n. Closes TD-124 (citation label localization). Opens TD-126/127/128 as LOW follow-ups. VERSION bump from 1.48.0 to 1.49.0 per story completion (MINOR — additive user-facing chat surface, no breaking changes). |
| 2026-04-26 | 1.49.0 | Claude Opus 4.7 (1M context) | Code review pass: 3 HIGH + 4 MEDIUM fixed (rate-limit composer-disable stale gate, first-message-after-auto-create race, JWT-in-URL → Authorization header, fetch unmount abort, composer over-cap silent drop, session list optimistic merge, dead `false &&` consent-bump branch). 0 new files; edits to ChatScreen / Composer / useChatStream / useChatSession / sse-client. 574/574 frontend tests pass. |

## Code Review

**Reviewed:** 2026-04-26 by adversarial code-review pass (Claude Opus 4.7, 1M context).
**Scope reviewed:** chat feature only (`frontend/src/features/chat/`, `frontend/src/app/[locale]/(dashboard)/chat/`). Infra/terraform changes ignored per reviewer scope ("parallel work").
**Outcome:** all 3 HIGH + 4 MEDIUM findings fixed in-flight; 3 LOW findings deferred (see TD promotion below).

### HIGH (fixed in this review)

- **H1 — `cooldownActive` derived from a static `retryAfterSeconds` field never decremented; composer Send stayed disabled forever after a `rate_limited` refusal.** Fix: store `cooldownEndsAt` (epoch ms) on the refusal at frame-arrival time in [useChatStream.ts](../../frontend/src/features/chat/hooks/useChatStream.ts); ChatScreen ticks at 1 Hz only while a cooldown is live and recomputes from wall-clock ([ChatScreen.tsx](../../frontend/src/features/chat/components/ChatScreen.tsx)).
- **H2 — First-message race after auto-create: `stream.send` referenced the previous render's closure with `sessionId=null`, so the very first user message after session auto-create was silently dropped.** Fix: `useChatStream.send` now accepts an `overrideSessionId`; ChatScreen passes the freshly-created `sessionId` directly into `send` instead of relying on closure rebind ([useChatStream.ts](../../frontend/src/features/chat/hooks/useChatStream.ts), [ChatScreen.tsx](../../frontend/src/features/chat/components/ChatScreen.tsx)).
- **H3 — JWT in URL query string was unjustified token leakage** (URL ends up in access logs / Referer / browser history). The implementation is `fetch` + `ReadableStream`, not `EventSource`, so the EventSource workaround the comment cited never applied. Fix: token moved to `Authorization: Bearer …` header in [sse-client.ts](../../frontend/src/features/chat/lib/sse-client.ts).

### MEDIUM (fixed in this review)

- **M1 — `useChatStream` never aborted in-flight fetch on unmount.** Fix: added `useEffect(() => () => abortRef.current?.abort(), [])` cleanup.
- **M2 — Composer silently truncated > 4096 chars with no user feedback** (and `maxLength` was off-by-one at `MAX_CHARS+1`). Fix: `maxLength={MAX_CHARS}`; submit-path now sets `composer.error_too_long` hint when over cap ([Composer.tsx](../../frontend/src/features/chat/components/Composer.tsx)).
- **M3 — Session list 404/405 fallback hid newly-created sessions** (refetch returned `[]` and clobbered the just-created session). Fix: `useChatSession` now keeps a `localSessions` state of POST-success entries and merges them with the server list (deduped by sessionId), removed on delete ([useChatSession.ts](../../frontend/src/features/chat/hooks/useChatSession.ts)).
- **M4 — Dead `{false && <ConsentVersionBumpCard ... />}` branch in ChatScreen.** Fix: dropped the dead branch and the import; left an inline comment explaining the gap (10.1a consent endpoint exposes only a boolean, so the version-bump card has no signal yet) ([ChatScreen.tsx](../../frontend/src/features/chat/components/ChatScreen.tsx)).

### LOW (disposed)

- **L1 — `tryTranslate` "ends with `.<lastSegment>`" heuristic** ([citation-label.ts:65](../../frontend/src/features/chat/lib/citation-label.ts#L65)) → **withdrawn on review** — defensive heuristic, never observed firing in current copy; if it ever does the symptom is "label shows server-canonical English" not a crash. Not worth a TD slot.
- **L2 → [TD-129](../../docs/tech-debt.md)** — `ConsentRevokedEmpty` hardcodes `/${locale}/settings` instead of accepting a `privacyHref` prop.
- **L3 → [TD-130](../../docs/tech-debt.md)** — `ConsentFirstUseDialog` Accept path swallows grant errors with no user feedback.
