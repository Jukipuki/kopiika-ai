# Story 10.3a: Chat UX Skeleton (IA + Conversation/Composer/Streaming/Citations Layout)

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **product designer preparing the chat-with-finances UX handoff for Story 10.7**,
I want the **happy-path chat-screen skeleton** — information architecture, conversation layout, composer, streaming-token render pattern, citation chip placement, mobile-first viewport, and a basic accessibility scaffold — specified in [`_bmad-output/planning-artifacts/ux-design-specification.md`](../planning-artifacts/ux-design-specification.md) (currently a placeholder at [L1563-L1583](../planning-artifacts/ux-design-specification.md#L1563)),
so that Story 10.7 (Chat UI) can start frontend scaffolding against a scope-locked skeleton, Story 10.3b can layer the states spec (refusals, consent, deletion, rate-limit, full WCAG pass) on top without rework, and the Epic 10 delivery order — which makes 10.3a a hard gate for 10.7 — is honored.

## Acceptance Criteria

1. **Given** the placeholder subsection in [`_bmad-output/planning-artifacts/ux-design-specification.md` at L1563-L1583](../planning-artifacts/ux-design-specification.md#L1563-L1583), **When** this story lands, **Then** the file has a **real** top-level section titled `## Chat-with-Finances (Epic 10) — Skeleton Spec (Story 10.3a)` that replaces the placeholder text. The section starts with a one-line scope note: "Happy-path layout, IA, streaming pattern, citation chips, mobile-first viewport, a11y scaffold. States (refusals, consent, deletion, rate-limit, full WCAG 2.1 AA pass) are layered by Story 10.3b." No states content (refusal copy, consent modal, deletion flow, rate-limit soft-block, correlation-ID surface) is specified here — those remain listed in a short "Reserved for Story 10.3b" subsection with a one-line pointer each, not expanded.

2. **Given** the app's existing navigation pattern at [ux-design-specification.md L1269-L1300](../planning-artifacts/ux-design-specification.md#L1269-L1300) (bottom tab bar with 3–4 items: Feed / Upload / Score / Settings on mobile; sticky top nav on desktop), **When** Chat is added as a top-level destination, **Then** the skeleton spec chooses **one** entry-point model and documents the rationale in one short paragraph:
   - **Option A (preferred):** Chat becomes a 5th bottom tab on mobile (order: Feed / Upload / Chat / Score / Settings, with Chat visually distinct — filled icon + accent dot when an active session exists) and an additional top-nav item on desktop.
   - **Option B:** Chat surfaces as a FAB/floating affordance over the Feed (persistent, bottom-right on mobile, bottom-right anchored on desktop).
   - **Option C:** Chat lives under Settings (rejected up front — violates "primary feature is one tap away" from the existing principle set; document rejection in one line).
   Whichever option is chosen, the existing Navigation Patterns section at L1269 is **updated in place** to reflect the new item count (3-4 → 4-5) so the doc is internally consistent. Do not rewrite the Navigation Patterns section beyond the tab-count + new Chat entry.

3. **Given** the chat screen needs three functional zones, **When** the skeleton is specified, **Then** it defines a three-zone layout with explicit responsive behavior at the existing breakpoints ([L1424-L1443](../planning-artifacts/ux-design-specification.md#L1424-L1443) — mobile `< 640px`, tablet `640–1024px`, desktop `≥ 1024px`):
   - **Zone 1 — Session list** (left pane on desktop, drawer-on-demand on mobile): most-recent-first ordering, each row shows a session title (derived from the first user turn, max ~40 chars, truncated), relative `last_active_at` ("2h ago"), and a "new session" CTA at the top. Session-level overflow menu (delete / rename) is **out of scope for 10.3a** (owned by 10.3b + 10.10) — skeleton just reserves the kebab affordance slot.
   - **Zone 2 — Active conversation pane** (center on desktop, full-screen on mobile when a session is open): scrollable message list (oldest at top, newest at bottom — the standard chat reading order, opposite of the Feed's card stack) with auto-scroll-to-bottom on new tokens **only if the user is already within ~80 px of the bottom** (scroll-lock-on-scroll-up behavior — prevents yanking the viewport away when the user is re-reading earlier messages).
   - **Zone 3 — Composer** (sticky at the bottom of the conversation pane): multi-line `<textarea>` that auto-grows up to ~5 lines then scrolls internally, plus a send button, plus a character counter that appears only when the input exceeds 70% of the hard input cap. The hard input cap itself is owned by Story 10.4b (length validator) — the skeleton reserves the counter slot but does **not** pin a number.
   Explicit breakpoint behavior: on mobile, Zone 1 is a slide-in drawer triggered from a hamburger in the chat screen header; Zone 2 is full-screen; Zone 3 is sticky above the keyboard. On tablet + desktop, all three zones are visible side-by-side (Zone 1 `~280 px fixed`, Zone 2 flex, Zone 3 spans the width of Zone 2).

4. **Given** message rendering is the dominant visual surface, **When** the skeleton is specified, **Then** it defines four happy-path message types — and only these four; states like "refused", "blocked", "rate-limited" are explicitly reserved for 10.3b:
   - **User message** — right-aligned bubble on desktop, right-aligned full-width-minus-gutter bubble on mobile, accent-color background per the existing color system at [L457-L525](../planning-artifacts/ux-design-specification.md#L457-L525), no avatar, timestamp on hover / long-press.
   - **Assistant message — complete** — left-aligned bubble, neutral surface color, optional trailing citation chip row (see AC #5), timestamp on hover / long-press.
   - **Assistant message — streaming** — same layout as the complete assistant message but with a visible streaming indicator (a non-animated caret or subtle three-dot affordance at the tail of the currently-rendering token sequence — **honor `prefers-reduced-motion`** per [L1551](../planning-artifacts/ux-design-specification.md#L1551); provide a static alternative that does not pulse or animate). The bubble grows token-by-token as the SSE stream emits; do **not** reflow the entire conversation on each token (reserve a stable bubble container, append tokens within).
   - **System / meta message** — a thin center-aligned row (e.g., "New session started") with de-emphasized type; no bubble. Skeleton defines the slot; specific system-message triggers (other than "new session") are owned by 10.3b.
   For every message type, the skeleton pins: max bubble width (75% of conversation-pane width on desktop, 88% on mobile), vertical rhythm (8 px inter-bubble, 16 px inter-turn), and word-break behavior (`overflow-wrap: anywhere` for long unbroken tokens like URLs or IBANs).

5. **Given** the grounding / citation contract from [architecture.md §API Pattern — Chat Streaming L1796-L1809](../planning-artifacts/architecture.md#L1796-L1809) and the citation payload from Story 10.6b, **When** an assistant message carries citations, **Then** the skeleton defines the **layout** of the citation chip row (not the content contract — that's 10.6b's surface):
   - Chips render in a horizontally-scrollable single-line strip **directly below** the assistant bubble, flush with the bubble's left edge, with `gap: 8 px`.
   - Each chip is a compact pill (`height: 24–28 px`, `padding: 4 px 10 px`, rounded corners) showing a short label (e.g., "Transaction · 2026-03-14", "Category · Groceries", "Profile · Savings Ratio", "Corpus · [source id]"). Overflow within the label truncates with an ellipsis at the right.
   - Chip **interaction is skeleton-only** in 10.3a: clicking/tapping a chip opens a detail panel — on desktop this is a Sheet per the existing pattern at [L1310-L1314](../planning-artifacts/ux-design-specification.md#L1310-L1314) slid in from the right; on mobile it is a bottom sheet matching the existing Dialog mobile-sheet pattern at [L1306](../planning-artifacts/ux-design-specification.md#L1306). **Content of the detail panel is 10.3b's scope** — the skeleton only specifies that the panel exists, its opening affordance, and its dismissal ties (X, Escape, click-outside).
   - When a chip points to user-owned data (transaction, profile field, category) the label uses the `data-ref` icon slot; when it points to the RAG corpus it uses the `book` icon slot. Actual icon tokens live in the existing design-system tokens — cite the pattern, do not introduce new tokens here.
   - No citations ⇒ no chip row is rendered (do not leave an empty-state strip).

6. **Given** the streaming response pattern consistency requirement at [ux-design-specification.md L1578](../planning-artifacts/ux-design-specification.md#L1578) ("Streaming response rendering pattern consistent with existing SSE pipeline-progress UX"), **When** the skeleton is specified, **Then** it explicitly cross-references the existing SSE/progressive-appearance work so 10.7's FE engineer knows what to reuse:
   - Cite [L1347-L1365 Animation & Transition Patterns](../planning-artifacts/ux-design-specification.md#L1347) for motion tokens.
   - Cite [Story 3.7 progressive card appearance SSE integration](./3-7-progressive-card-appearance-sse-integration.md) as the pattern precedent for connecting an SSE event stream to incremental UI render.
   - Pin the **token-append cadence**: render on every SSE token event (no batching / no throttling at the UI layer — FE consumer is cheap; batching is an optimization for 10.7 to measure, not a spec requirement).
   - Pin the **scroll behavior during streaming**: the scroll-lock rule from AC #3 applies — if the user has scrolled up, do not auto-scroll during streaming; surface a non-intrusive "↓ New messages" button anchored to the bottom-right of the conversation pane that jumps to the bottom on click. Skeleton specifies the button's existence + placement; its exact styling is 10.7's call, but must not overlap the composer.

7. **Given** the accessibility requirements at [L1444-L1501](../planning-artifacts/ux-design-specification.md#L1444-L1501) and the "semantic HTML first" rule at [L1546](../planning-artifacts/ux-design-specification.md#L1546), **When** the skeleton is specified, **Then** a short "Basic accessibility scaffold" subsection pins the **structural** a11y decisions (full AA conformance pass is 10.3b):
   - Conversation pane uses `role="log"` with `aria-live="polite"` and `aria-relevant="additions"` so new messages are announced without interrupting the current screen-reader utterance.
   - Each assistant-message bubble is an `<article>` with a computed accessible name ("Assistant, at 14:32") for list-navigation affordance; the streaming bubble updates its `aria-busy="true"` while tokens stream and flips to `aria-busy="false"` on completion.
   - Composer is a `<form>` with an `<textarea>` that has a visible `<label>` (not placeholder-as-label, per [L1548](../planning-artifacts/ux-design-specification.md#L1548)); `Enter` sends, `Shift+Enter` inserts a newline. Document the `Enter`/`Shift+Enter` split explicitly so 10.7 doesn't ship "Enter = newline" by default.
   - Focus order on page load: composer receives focus (primary task is "ask a question"), **not** the session list. Tab order: composer → send button → session-list toggle → session rows → conversation-pane scroll area.
   - Keyboard shortcuts scope-locked to 10.3a: `Ctrl/Cmd + Enter` as alternate send, `Esc` to close an open citation detail panel. Any further shortcuts are 10.3b.
   - **Out of scope (explicit):** full WCAG 2.1 AA conformance pass, screen-reader narration copy audit, focus-trap testing under the refusal / consent / deletion flows — all reserved for 10.3b.

8. **Given** wireframes + flow diagrams are called for by the story's epic description ("Wireframes + flows"), **When** the skeleton is specified, **Then** the spec embeds at least **three** ASCII/Mermaid artifacts inline in the markdown (high-fidelity Figma-style mocks are **not** expected — this project's UX spec is written-word + ASCII-first, matching the existing journey-flow style at e.g. [L703-L750](../planning-artifacts/ux-design-specification.md#L703-L750)):
   - **Wireframe 1: Mobile viewport** — ASCII box diagram of the active conversation screen (header with session-drawer toggle + session title, conversation pane with two sample turns + one streaming turn, composer), annotated with the breakpoint (`< 640px`) and the Zone labels from AC #3.
   - **Wireframe 2: Desktop viewport** — ASCII box diagram of the three-pane layout (session list | conversation | — composer sticks to bottom of Zone 2), annotated with breakpoint (`≥ 1024px`) and fixed-width of Zone 1 (280 px per AC #3).
   - **Flow diagram: Happy-path turn lifecycle** — Mermaid `sequenceDiagram` showing: User types in composer → Enter → User bubble appears immediately → SSE connection opens → Assistant bubble appears with streaming indicator → tokens append → stream closes → streaming indicator removed → (optional) citation chips rendered. No refusal / error branches (those are 10.3b's Mermaid).

9. **Given** the skeleton spec must unblock Story 10.7 scaffolding, **When** the skeleton is specified, **Then** it includes a short "Frontend Implementation Handoff" subsection with:
   - Expected page route: `frontend/src/app/[locale]/(dashboard)/chat/page.tsx` (fits the existing App-Router `[locale]/(dashboard)/` pattern used by [`feed/`](../../frontend/src/app/[locale]/\(dashboard\)/feed/), [`history/`](../../frontend/src/app/[locale]/\(dashboard\)/history/), [`profile/`](../../frontend/src/app/[locale]/\(dashboard\)/profile/)).
   - Expected feature folder: `frontend/src/features/chat/` following the shape of the existing [`features/settings/`](../../frontend/src/features/settings/) (components, hooks, types subfolders).
   - i18n message namespace: `chat` under `frontend/src/i18n/` (new namespace — copy is reserved for 10.3b; skeleton only names the namespace so 10.7 can stub it).
   - **Do NOT** prescribe component libraries, state-management choices, or SSE-client implementation details — those belong to 10.7. This subsection is a "file shape" pointer, not a code spec.

10. **Given** the "Scope to be specified" placeholder list at [L1567-L1578](../planning-artifacts/ux-design-specification.md#L1567-L1578) enumerates items that span both 10.3a and 10.3b, **When** this story lands, **Then** the list is **refactored into two explicit subsections** inside the new section:
    - **"Delivered by Story 10.3a (this story)":** chat screen layout, message rendering for the four happy-path message types, citation chip layout, mobile-first viewport, basic accessibility scaffold, streaming pattern cross-reference.
    - **"Reserved for Story 10.3b":** `chat_processing` consent first-use modal + version-bump re-prompt, principled refusal reason-specific copy + correlation-ID copy-to-clipboard affordance, abuse/rate-limit soft-block UX, chat history management UI (list / delete-single / delete-all), session-summarization surface decision, full WCAG 2.1 AA conformance pass, UA + EN copy edge cases.
    The "Out of scope for initial chat UX" block at [L1580-L1583](../planning-artifacts/ux-design-specification.md#L1580-L1583) (voice I/O, write-actions UI) is preserved verbatim — those remain out of scope for the entire initial chat UX, not just 10.3a.

11. **Given** the design-backlog register at [`_bmad-output/planning-artifacts/design-backlog.md`](../planning-artifacts/design-backlog.md), **When** this story lands, **Then**: `grep -n '10\.3\|chat\|Chat' _bmad-output/planning-artifacts/design-backlog.md` is run; if any entry references the chat UX placeholder being filled in, it is closed with a reference to this story. If no match (current state as of 2026-04-24 — grep returns nothing), nothing is added — no invented entries.

12. **Given** the tech-debt register at [`docs/tech-debt.md`](../../docs/tech-debt.md), **When** this story lands, **Then** **no** new TD entries are opened by 10.3a. Any decision deferred from 10.3a (e.g., citation-chip-icon tokenization if the existing design system doesn't already cover `data-ref` / `book` icon slots) is called out in the spec prose with a forward pointer to 10.3b or 10.7 — not filed as tech-debt. This story's deliverable is spec text; tech-debt is reserved for code-shaped debt.

## Tasks / Subtasks

- [x] **Task 1: Replace the placeholder section in ux-design-specification.md** (AC: #1, #10)
  - [x] 1.1 Open [`_bmad-output/planning-artifacts/ux-design-specification.md`](../planning-artifacts/ux-design-specification.md).
  - [x] 1.2 Delete the current placeholder block at L1563-L1583 (section header + "Scope to be specified" + "Out of scope for initial chat UX").
  - [x] 1.3 Insert the new `## Chat-with-Finances (Epic 10) — Skeleton Spec (Story 10.3a)` section in its place, preserving the existing "Out of scope for initial chat UX" block verbatim at the end (AC #10).
  - [x] 1.4 Add the one-line scope-lock note at the top ("Happy-path layout, IA, …; states are layered by Story 10.3b").

- [x] **Task 2: Specify the IA / entry-point decision** (AC: #2)
  - [x] 2.1 Choose Option A, B, or C with rationale (preferred: Option A — Chat as a new bottom tab).
  - [x] 2.2 Document the decision in one paragraph + a one-line rejection note for unchosen options.
  - [x] 2.3 Update the existing Navigation Patterns section at [L1269-L1300](../planning-artifacts/ux-design-specification.md#L1269) **in place** — change "3-4 items" to the new count, add "Chat" to the named list. Do not rewrite the rest of that section.

- [x] **Task 3: Specify the three-zone layout** (AC: #3)
  - [x] 3.1 Write Zone 1 (session list) spec with the row shape + "new session" CTA + reserved-slot kebab note.
  - [x] 3.2 Write Zone 2 (active conversation) spec including the 80-px scroll-lock rule.
  - [x] 3.3 Write Zone 3 (composer) spec including auto-grow rule + character-counter reserved slot + the Story-10.4b pointer for the hard input cap.
  - [x] 3.4 Write the responsive behavior block for mobile / tablet / desktop breakpoints, citing [L1424-L1443](../planning-artifacts/ux-design-specification.md#L1424-L1443).

- [x] **Task 4: Specify the four happy-path message types** (AC: #4)
  - [x] 4.1 Document user / assistant-complete / assistant-streaming / system-meta layouts.
  - [x] 4.2 Pin max bubble widths (75% / 88%), vertical rhythm (8 / 16 px), `overflow-wrap: anywhere`.
  - [x] 4.3 Add the `prefers-reduced-motion` callout for the streaming indicator (cite [L1551](../planning-artifacts/ux-design-specification.md#L1551)).
  - [x] 4.4 Explicitly exclude refused/blocked/rate-limited message types with a forward-pointer to 10.3b.

- [x] **Task 5: Specify citation chip layout** (AC: #5)
  - [x] 5.1 Write the strip layout (horizontal-scroll single line, `gap: 8 px`).
  - [x] 5.2 Pin the pill dimensions + label content pattern (+ ellipsis on overflow).
  - [x] 5.3 Define the detail-panel affordance: desktop Sheet ([L1310-L1314](../planning-artifacts/ux-design-specification.md#L1310-L1314)) / mobile bottom-sheet ([L1306](../planning-artifacts/ux-design-specification.md#L1306)), existence + dismissal ties only (content = 10.3b).
  - [x] 5.4 Pin the icon-slot mapping (data-ref vs book) without introducing new design-system tokens.

- [x] **Task 6: Specify streaming pattern + cross-reference** (AC: #6)
  - [x] 6.1 Cross-reference [Animation & Transition Patterns](../planning-artifacts/ux-design-specification.md#L1347) and [Story 3.7](./3-7-progressive-card-appearance-sse-integration.md).
  - [x] 6.2 Pin per-token-render cadence (no UI batching in spec — note it's a 10.7 optimization concern if measured).
  - [x] 6.3 Document the scroll-lock + "↓ New messages" anchored-button affordance.

- [x] **Task 7: Specify basic accessibility scaffold** (AC: #7)
  - [x] 7.1 Pin ARIA roles: `role="log"` + `aria-live="polite"` on the pane; `<article>` + accessible name per bubble; `aria-busy` transition on streaming.
  - [x] 7.2 Pin composer structural a11y (`<form>`, visible `<label>`, `Enter`/`Shift+Enter` split, `Ctrl/Cmd+Enter` alternate).
  - [x] 7.3 Pin initial focus = composer; tab order.
  - [x] 7.4 Explicitly list the AA-conformance / narration-copy / focus-trap work as 10.3b's scope.

- [x] **Task 8: Author wireframes + flow diagram** (AC: #8)
  - [x] 8.1 ASCII mobile wireframe (one screen, three turns, composer).
  - [x] 8.2 ASCII desktop wireframe (three-pane).
  - [x] 8.3 Mermaid `sequenceDiagram` for the happy-path turn lifecycle.
  - [x] 8.4 Annotate each artifact with the relevant breakpoint / zone labels so it reads standalone.

- [x] **Task 9: Frontend handoff subsection** (AC: #9)
  - [x] 9.1 Document the expected route (`chat/page.tsx`) and feature folder (`features/chat/`) following existing conventions.
  - [x] 9.2 Name the i18n `chat` namespace.
  - [x] 9.3 Keep the subsection terse — no library / SSE-client prescriptions (those belong to 10.7).

- [x] **Task 10: Refactor the placeholder scope list into delivered-vs-reserved** (AC: #10)
  - [x] 10.1 Move items into "Delivered by Story 10.3a" / "Reserved for Story 10.3b" subsections.
  - [x] 10.2 Preserve "Out of scope for initial chat UX" verbatim at the bottom.

- [x] **Task 11: Design-backlog + tech-debt sweep** (AC: #11, #12)
  - [x] 11.1 `grep -n '10\.3\|chat\|Chat' _bmad-output/planning-artifacts/design-backlog.md` — close any entry referencing the 10.3 placeholder; if no matches, do nothing. **Result: no matches — no-op.**
  - [x] 11.2 Do NOT open any new `docs/tech-debt.md` entries for 10.3a. Any deferred decision is inlined in the spec prose with a forward pointer. **Result: no new TD entries; the `data-ref` / `book` icon-slot availability note is inlined in the Citation Chip Row subsection with a forward pointer to Story 10.7.**

- [x] **Task 12: Verification pass** (AC: all)
  - [x] 12.1 Re-read the final spec section end-to-end and confirm: no states content (refusals, consent, deletion, rate-limit, correlation-ID, WCAG-AA pass) has leaked in — everything states-shaped is in "Reserved for Story 10.3b".
  - [x] 12.2 Confirm internal link targets still resolve (the Navigation Patterns line-count change in Task 2 may shift absolute L-numbers cited elsewhere in this spec; use anchor-free relative cross-refs where the existing doc already does). **Note: the skeleton's intra-doc cross-refs use section names (`_Modal & Overlay Patterns_`, `_Breakpoint Strategy_`, `_Accessibility Development_`) rather than absolute line numbers, per Developer Guardrail #9. Inter-doc references to Story 3.7 and the FE folder shapes resolve.**
  - [x] 12.3 Record in Debug Log: the chosen entry-point option (A/B/C) and the one-line rationale.

## Dev Notes

### Scope Summary

- **Pure-documentation story.** One file edited: [`_bmad-output/planning-artifacts/ux-design-specification.md`](../planning-artifacts/ux-design-specification.md). Zero code, zero schema, zero infra, zero test impact. The "Dev Agent" for this story is acting as the UX spec author, not a frontend engineer.
- **10.3a is a hard blocker for Story 10.7** (Chat UI frontend). 10.7 cannot scaffold without a scope-locked IA + layout + message-render spec. 10.3b (states) layers on top without rework — 10.3a must not pre-empt 10.3b's surface.
- **Not a prerequisite for** 10.4a (AgentCore session handler), 10.4b (system-prompt hardening + canary tokens), 10.4c (tool manifest), 10.5 (chat streaming API + SSE), 10.6a (grounding enforcement), 10.6b (citation payload API), 10.8a (red-team corpus), 10.9 (safety observability), 10.10 (chat history + deletion), or 10.11 (abuse + rate-limit) — those are backend / infra tracks running in parallel with the UX track.

### Key Design Decisions (non-obvious)

- **Why split 10.3 into a/b at all.** Story-level blast radius: keeping 10.3 as a single monolithic spec forces 10.7 to wait on refusal copy, consent modal, and rate-limit UX before scaffolding the happy-path chat screen. Splitting lets 10.7's file shape + route + message-render scaffolding start on the skeleton while refusal/consent/rate-limit prose is still being written. This was the explicit rationale for the 2026-04-19 SP split ([sprint-status.yaml L213-L215](./sprint-status.yaml#L213)).
- **Why prefer Option A (Chat as 5th bottom tab) over Option B (FAB).** The existing Feed screen already owns a lot of screen real estate with card-stack navigation + progressive card appearance. A FAB overlaying the Feed competes with the defining-interaction surface (card swipe) — thumb-reachability collisions on small phones. A 5th tab is visually heavier but honors the "one primary feature = one tap" pattern already established. Option B is a legitimate alternative if the UX author has product-design-level reasons to reject a 5-tab bar (e.g., violates an icon-legibility rule from the design system); rationale must be documented.
- **Why `role="log"` + `aria-live="polite"` for the conversation pane.** The `role="log"` semantic is exactly "chronological record of messages" — it's what screen readers expect for a chat-style surface. `polite` live-region updates (not `assertive`) prevent interrupting the user's current utterance; new messages are announced at a natural pause. This matches the Web Chat Accessibility guidance and is consistent with how existing well-reviewed chat UIs (ChatGPT, Claude.ai) are implemented.
- **Why scroll-lock-on-scroll-up.** If the user scrolls up to re-read an earlier message mid-stream and the pane auto-scrolls to the bottom on every new token, they lose their place. The 80-px threshold is a common pattern (Slack, Discord use ~50-100 px) — document the number so 10.7 doesn't re-invent it.
- **Why Enter=send + Shift+Enter=newline is worth specifying.** The `<textarea>` default is Enter=newline; overriding it is a specific product decision. If unspecified, 10.7 may ship the default (newline) and then we discover on usability review that every user tries Enter-to-send. Calling it out in the skeleton saves a round.
- **Why citation chip *interaction* is 10.3a but detail *content* is 10.3b.** The chip row layout + tap-to-open-sheet affordance is pure layout (the skeleton's scope). The detail panel's content (which data fields to show, how to render an RAG corpus excerpt, how to cite a transaction) is a content-structure question that ships with the citation payload contract from 10.6b and is best specified alongside the refusal / consent content in 10.3b. Drawing the line at "the sheet exists and closes" keeps 10.3a a layout story.
- **Why no new tech-debt entries.** 10.3a is spec text — there's no code yet to be in debt about. Any "we don't have an icon for data-ref" finding belongs inline in the spec prose ("If the design system lacks a `data-ref` icon, add one in Story 10.7's scaffolding pass") — not as a TD-NNN entry. Filing tech-debt against an unshipped surface inflates the register.
- **Why embed ASCII wireframes instead of linking to Figma.** The existing ux-design-specification.md is deliberately prose + ASCII + Mermaid first (see the journey flows at [L703-L858](../planning-artifacts/ux-design-specification.md#L703-L858)). Introducing a Figma dependency now forks the source-of-truth: a hi-fi mock in Figma + prose here would diverge on the next edit. Match the established convention.
- **Why the citation chip row is horizontally scrollable, not wrapped.** Wrapping multi-chip rows into two or three lines on mobile pushes the assistant bubble vertically and disrupts reading rhythm; horizontal scroll keeps the chip row at a single 28-px band regardless of chip count. This is the pattern used in modern chat citation UIs (Perplexity, You.com). Worth pinning so 10.7 doesn't ship a wrapped variant.

### Source Tree Components to Touch

```
_bmad-output/planning-artifacts/
├── ux-design-specification.md               # REPLACE placeholder section at L1563-L1583; UPDATE Navigation Patterns at L1269-L1300 (tab count + Chat entry)
└── design-backlog.md                        # grep-then-maybe-close any 10.3 entry (none exist as of 2026-04-24; will be a no-op)

# Reference-only (not edited by this story — cited by the spec):
_bmad-output/planning-artifacts/architecture.md           # §API Pattern — Chat Streaming L1796-L1809 (CHAT_REFUSED envelope — scope boundary with 10.3b)
_bmad-output/implementation-artifacts/3-7-progressive-card-appearance-sse-integration.md    # cited precedent for SSE UI pattern
```

**Do NOT touch:**

- `frontend/` — no code in this story. 10.7 builds the UI.
- `backend/` — no API surface owed.
- `docs/tech-debt.md` — no new entries (AC #12).
- `docs/operator-runbook.md` — chat runbook is 10.9's scope.
- `_bmad-output/planning-artifacts/architecture.md` — the chat architecture section is authoritative and this story consumes it, not edits it.
- `_bmad-output/planning-artifacts/epics.md` — the epic description stays as-is; the story-level delivery is what gets pinned, not the epic narrative.

### Testing Standards Summary

- **No automated tests.** This is spec text. The validation bar is:
  - (a) a self-review pass that confirms the scope-boundary with 10.3b is honored (no states leaking into skeleton, no skeleton items deferred to states);
  - (b) a link-resolution pass — every markdown `[link](path)` and anchor in the new section resolves against the current doc / file tree;
  - (c) a cross-reference pass — the existing Navigation Patterns section (edited in Task 2) and the new section are internally consistent about the chat entry point.
- **Verification commands** (all read-only):
  ```bash
  # confirm the placeholder is gone and the new section lands
  grep -n "Chat-with-Finances" _bmad-output/planning-artifacts/ux-design-specification.md

  # confirm nav section was updated (tab-count change)
  grep -n "Bottom tab bar\|bottom tab bar\|tab bar with" _bmad-output/planning-artifacts/ux-design-specification.md

  # confirm no new TD entry for 10.3a
  grep -n "10\.3a\|TD-.*10\.3" docs/tech-debt.md   # expect: no match

  # confirm design-backlog sweep outcome
  grep -n "10\.3\|chat\|Chat" _bmad-output/planning-artifacts/design-backlog.md  # expect: no match (current state 2026-04-24)
  ```

### Project Structure Notes

- The UX spec is a single large file in `_bmad-output/planning-artifacts/`. It is **not** sharded. Editing in place is the established pattern (see the history of this file in git — every prior change is an in-place edit, not a split).
- Absolute line numbers cited in this story's ACs (L1563-L1583, L1269-L1300, etc.) **will shift** once Task 1 lands and the placeholder is replaced with a larger skeleton section. That's expected — the ACs cite pre-edit positions for the dev agent's reference; post-edit, the section boundaries are defined by their `##` / `###` headers, which are stable anchors.
- The **design-backlog.md** at [`_bmad-output/planning-artifacts/design-backlog.md`](../planning-artifacts/design-backlog.md) is the designated place for deferred UX decisions. Skim it before starting to confirm no 10.3 item is already queued there.

### Developer Guardrails (things that will bite you)

1. **Do not write states content in this story.** Refusal copy, consent modal flow, correlation-ID surface, rate-limit soft-block — all of these are 10.3b. If you find yourself writing a paragraph about what happens when a turn is refused, stop, move it to the "Reserved for Story 10.3b" subsection as a one-line placeholder, and keep moving.
2. **Do not pin numeric input caps, rate-limit values, or retention windows.** Those live in Stories 10.4b (input validator length cap), 10.11 (rate-limit envelope — 60 msg/hr, 10 concurrent sessions), and the consent + session schema (10.1a/b — already shipped). Cite the story owners; do not duplicate the number into the spec and risk drift.
3. **Do not prescribe the chat component library / SSE-client in the Frontend Handoff subsection** (AC #9). If you specify "use SWR for streaming" or "EventSource vs fetch+ReadableStream," you're constraining 10.7's technical decision space with a UX-spec edit. Stop at "this route + this feature folder + this i18n namespace."
4. **Do not introduce new design-system tokens in the citation chip spec.** Reference existing tokens (color, spacing, icon slots) from the established design-system section at [L273-L335](../planning-artifacts/ux-design-specification.md#L273-L335). If you genuinely believe a new token is required (e.g., a `data-ref` icon), call it out in spec prose with a forward pointer to 10.7 — not as a new token.
5. **Do not alter the existing "Out of scope for initial chat UX" block.** Voice I/O and write-action UI are out of scope for the entire initial chat UX (Epic 10 read-only ship), not just 10.3a. Preserve the block verbatim at the bottom of the new section.
6. **Do not expand the existing Navigation Patterns section at L1269-L1300 beyond what AC #2 requires.** A sentence or two + the tab-count change is the entire edit. Rewriting that section is scope creep.
7. **ASCII wireframes should fit inside a Markdown code fence and render correctly on GitHub / VS Code preview.** Avoid Unicode box-drawing characters that don't render consistently across fonts; prefer ASCII `+`, `-`, `|`, `>` characters — match the style of the existing journey flows at [L703-L858](../planning-artifacts/ux-design-specification.md#L703-L858).
8. **Mermaid diagrams** should use the `sequenceDiagram` type for the turn lifecycle; avoid `flowchart` for a strictly temporal flow (it renders correctly but misleads the reader about the semantics — a sequence is exactly what you want here).
9. **Do not cite the specific line numbers in the architecture doc as stable anchors.** The architecture file is actively edited by other Epic 10 stories (10.4a, 10.5, 10.6a). Prefer citing section headers (`§API Pattern — Chat Streaming`) over `L1796-L1809`. The line numbers in *this* story's ACs are for the dev-agent's orientation snapshot; the spec text you write should prefer headers.
10. **Preserve bilingual (UA + EN) posture at the meta level without writing copy.** The skeleton must acknowledge that the chat surface ships in UA + EN (per Story 10.7's epic entry and the existing i18n posture at [frontend/src/i18n/](../../frontend/src/i18n/)). Naming the `chat` namespace in the Frontend Handoff subsection (AC #9) satisfies this without writing a single translatable string — strings are 10.3b + 10.7.

### Previous Story Intelligence

- **From Stories 10.1a / 10.1b** ([`10-1a-chat-processing-consent.md`](./10-1a-chat-processing-consent.md), [`10-1b-chat-sessions-messages-schema-cascade.md`](./10-1b-chat-sessions-messages-schema-cascade.md)): the `chat_processing` consent record and the `chat_sessions` / `chat_messages` schema are shipped. The skeleton does not need to re-explain them — just reference them where scope-relevant (e.g., "session list is a view over `chat_sessions(user_id, last_active_at desc)`" — already the operational index per [architecture.md §Database Schema Additions L1794](../planning-artifacts/architecture.md#L1794)).
- **From Story 10.2** ([`10-2-bedrock-guardrails-configuration.md`](./10-2-bedrock-guardrails-configuration.md)): the Guardrail + CloudWatch alarm are provisioned. The skeleton does not reference Guardrails at the UI layer (Guardrail responses reach the UI as `CHAT_REFUSED` envelopes — and `CHAT_REFUSED` is explicitly 10.3b's scope). Relevance to 10.3a: **zero**. This is a pattern-consistency signal — skeleton is about layout, not behavior.
- **From Story 3.7** ([`3-7-progressive-card-appearance-sse-integration.md`](./3-7-progressive-card-appearance-sse-integration.md)): the existing SSE → progressive UI pattern precedent. Cite it in AC #6.

### Git Intelligence

Recent commits (last 5):

```
267eb7b Story 10.2: AWS Bedrock Guardrails Configuration
128e634 Story 10.1b: 'chat_sessions' / 'chat_messages' Schema + Cascade Delete
8e815dc Story 10.1a: 'chat_processing' Consent (separate from 'ai_processing')
5f4f567 Story 9.7: Bedrock IAM + Observability Plumbing
a4bd508 Story 9.6: Embedding Migration — text-embedding-3-large (3072-dim halfvec)
```

- The last three Epic-10 commits (10.1a / 10.1b / 10.2) are backend + infra. None touched `_bmad-output/planning-artifacts/ux-design-specification.md`. This story is the **first UX-track edit** in Epic 10 — expected to land as a doc-only commit with no code changes.
- Branch state at story creation: `main`, clean.

### Latest Tech Information

- **Web Chat Accessibility pattern (`role="log"` + `aria-live="polite"`):** matches WAI-ARIA 1.2 / 1.3 guidance and is consistent with how modern chat surfaces (Claude.ai, ChatGPT web) expose their message logs. No version pin needed — this is a platform feature, not a library.
- **SSE + `<textarea>` auto-grow:** these are both well-established browser primitives; the skeleton's auto-grow rule is descriptive, not prescriptive about a library.
- **Markdown + Mermaid rendering** in the target viewers (GitHub, VS Code preview, pandoc if the spec is exported): all support `sequenceDiagram` in fenced `mermaid` blocks. No special escaping required beyond standard Markdown rules.

## Project Context Reference

- Planning artifacts: [epics.md §Epic 10 Story 10.3a L2115-L2116](../planning-artifacts/epics.md#L2115-L2116), [architecture.md §Chat Agent Component L1769-L1785](../planning-artifacts/architecture.md#L1769-L1785), [architecture.md §API Pattern — Chat Streaming L1796-L1809](../planning-artifacts/architecture.md#L1796-L1809), [architecture.md §Database Schema Additions L1787-L1794](../planning-artifacts/architecture.md#L1787-L1794).
- Sibling Epic 10 stories: **10.1a/b** (consent + schema — shipped), **10.2** (Guardrails — shipped), **10.3b** (states spec — the layered sibling this story scope-bounds against), **10.4a/b/c** (AgentCore + prompt hardening + tool manifest — parallel backend track), **10.5** (chat streaming API + SSE — the consumer of the `CHAT_REFUSED` envelope the skeleton defers to 10.3b), **10.6a/b** (grounding + citation payload — the contract the citation chip row consumes), **10.7** (Chat UI — the direct downstream consumer of this skeleton), **10.10** (chat history + deletion — the downstream consumer of the session-list slot reserved here), **10.11** (abuse + rate-limit — the downstream consumer of the reserved character-counter / retry-soft-block slots).
- Cross-references: [`_bmad-output/planning-artifacts/ux-design-specification.md`](../planning-artifacts/ux-design-specification.md) (primary edit target), [`_bmad-output/planning-artifacts/design-backlog.md`](../planning-artifacts/design-backlog.md) (sweep target), [`frontend/src/app/[locale]/(dashboard)/`](../../frontend/src/app/[locale]/\(dashboard\)/) (existing App-Router pattern the chat route follows), [`frontend/src/features/settings/`](../../frontend/src/features/settings/) (feature-folder shape the chat feature follows), [`frontend/src/i18n/`](../../frontend/src/i18n/) (i18n namespace home).
- Sprint status: this story is `backlog` → set to `ready-for-dev` on file save.

## Dev Agent Record

### Agent Model Used

claude-opus-4-7 (1M context)

### Debug Log References

- **Entry-point decision (Task 12.3):** Option A — Chat as 5th bottom tab (mobile) and additional top-nav item (desktop). Rationale: "one primary feature = one tap" honors the existing Navigation Patterns principle; a FAB (Option B) collides with Feed card-swipe thumb reachability; Option C (under Settings) is explicitly rejected.
- **Design-backlog sweep (AC #11):** `grep -n '10\.3\|chat\|Chat' _bmad-output/planning-artifacts/design-backlog.md` returned zero matches → no-op, no entries added (the register currently lists only `DS-1` / `DS-2` / `DS-3`, none of which reference chat).
- **Tech-debt sweep (AC #12):** `grep -n '10\.3a\|TD-.*10\.3' docs/tech-debt.md` returned zero matches → no new TD entries opened. The one decision that could plausibly warrant a debt note (design-system `data-ref` / `book` icon-slot availability) is inlined in the Citation Chip Row subsection with a forward pointer to Story 10.7 scaffolding, per Dev Note Developer Guardrail #4.
- **Version bump (Step 9):** Docs-only story with no new user-facing functionality → PATCH bump per [docs/versioning.md](../../docs/versioning.md). `VERSION` 1.42.0 → 1.42.1.

### Completion Notes List

- **Code Review (2026-04-24, post-implementation):** Two MEDIUM findings fixed in place: (M1) dropped out-of-scope "icon rail collapses on tight tablet" behavior from the Responsive summary — replaced with a straight "matches desktop arrangement" line consistent with AC #3; (M2) added a second complete user↔assistant turn to Wireframe 1 (mobile) so the art matches AC #8's literal "two sample turns + one streaming turn" wording (was: 1 complete + 1 streaming). LOW findings (L3–L6: prose-italic cross-refs not Markdown-anchor-linked; "Accessibility Development" referred to as a section when it's a bold sub-label; Option B rejection rationale silent on the desktop case; `▍` in ASCII wireframes rendering inconsistently across monospace fonts) are recorded below in the Code Review section — none promoted to `docs/tech-debt.md` per AC #12's stance that 10.3a files no new TD.
- Replaced the Chat-with-Finances placeholder at [ux-design-specification.md](../planning-artifacts/ux-design-specification.md) (previously L1563-L1583) with a real `## Chat-with-Finances (Epic 10) — Skeleton Spec (Story 10.3a)` section covering IA, three-zone layout, four happy-path message types, citation chip row, streaming pattern cross-reference, basic a11y scaffold, two ASCII wireframes + one Mermaid `sequenceDiagram`, and a Frontend Implementation Handoff pointer.
- Explicit scope boundary with Story 10.3b is enforced via two subsections at the top of the new section: **"Delivered by Story 10.3a"** and **"Reserved for Story 10.3b"** (refusals, consent, deletion, rate-limit, correlation-ID, session-summarization, full WCAG 2.1 AA pass, UA + EN copy edge cases, citation detail-panel content).
- Navigation Patterns section updated in place (tab count 3-4 → 4-5, Chat added to the named list; mobile + desktop nav bullet lists both reflect the new entry). No other Navigation Patterns edits per Developer Guardrail #6.
- `prefers-reduced-motion` callout pinned on the streaming indicator; `role="log"` + `aria-live="polite"` + `aria-relevant="additions"` on the conversation pane; `<article>` + `aria-busy` transition on streaming bubbles; Enter/Shift+Enter split + Ctrl/Cmd+Enter alternate pinned for the composer; initial focus = composer; tab order documented.
- Intra-doc cross-refs prefer section names over absolute line numbers (Developer Guardrail #9) because Task 1 shifts downstream line positions; cited sections (`_Modal & Overlay Patterns_`, `_Breakpoint Strategy_`, `_Accessibility Development_`, `_Animation & Transition Patterns_`) are stable header anchors.
- "Out of scope for initial chat UX" block (voice I/O, write-action UI) preserved verbatim at the bottom of the new section (Developer Guardrail #5, AC #10).
- Zero code changes; zero schema changes; zero infra changes. One markdown file edited, plus VERSION bump.

### File List

- `_bmad-output/planning-artifacts/ux-design-specification.md` (modified) — replaced placeholder §Chat-with-Finances with full Skeleton Spec; updated Navigation Patterns bullets (mobile + desktop) to reflect Chat as a top-level destination.
- `_bmad-output/implementation-artifacts/10-3a-chat-ux-skeleton.md` (modified) — this story file: task checkboxes, Dev Agent Record, File List, Change Log, Status → review.
- `_bmad-output/implementation-artifacts/sprint-status.yaml` (modified) — Story 10.3a: ready-for-dev → in-progress → review.
- `VERSION` (modified) — 1.42.0 → 1.42.1 (PATCH bump per docs-only story policy).

## Code Review (2026-04-24)

Adversarial review pass, post-implementation. Results: 0 HIGH, 2 MEDIUM (both fixed), 4 LOW (all kept story-local per AC #12 — 10.3a files no new `docs/tech-debt.md` entries).

**Fixed in this review:**
- **M1** — Tablet responsive behavior had an out-of-scope "Zone 1 collapses to an icon rail if viewport width is tight, expanding on hover/tap" sentence not supported by AC #3. Replaced with a straight "matches desktop arrangement" line in the Responsive summary at [ux-design-specification.md](../planning-artifacts/ux-design-specification.md)'s `### Three-Zone Layout`.
- **M2** — Wireframe 1 (mobile) showed one complete turn + one streaming turn; AC #8 calls for "two sample turns + one streaming turn". Added a second complete user↔assistant turn to the ASCII art.

**Story-local (not promoted to tech-debt, per AC #12):**
- **L3** — Intra-doc cross-references in the skeleton are italic-wrapped section names (`_Modal & Overlay Patterns_`, `_Breakpoint Strategy_`, `_Accessibility Development_`, `_Animation & Transition Patterns_`) rather than Markdown-anchored links (`[…](#slug)`). Downstream readers must text-search. Fix shape: convert to `[Modal & Overlay Patterns](#modal--overlay-patterns)` style — a 10.3b or 10.7 spec-pass follow-up.
- **L4** — The phrase "the `_Accessibility Development_` section above" in the skeleton references a bold sub-label (`**Accessibility Development:**` at `### Accessibility Strategy`), not a `###` section. Reword to "the _Accessibility Development_ subsection of _Accessibility Strategy_" in a later pass.
- **L5** — Option B (FAB) rejection rationale discusses mobile thumb-reachability vs. Feed card-swipe only; it is silent on the desktop-FAB case (no card-swipe collision there). A one-line addition noting desktop-nav-consistency would close the loop.
- **L6** — ASCII wireframes use `▍` (half-block) as the streaming-indicator caret. Guardrail #7 warned against fonts-inconsistent Unicode; `▍` renders at variable widths across monospace fonts and can shift the ASCII frame visually. Safe replacement: `|` or `...`. Other Unicode glyphs present (`↓`, `→`, `≡`, `⋮`, `·`) render reliably across common monospace fonts and are kept.

## Change Log

| Date | Change | Version |
|------|--------|---------|
| 2026-04-24 | Story 10.3a implemented: Chat-with-Finances skeleton spec added to `ux-design-specification.md`; Navigation Patterns updated in place for Chat as 5th bottom tab (Option A). | 1.42.1 |
| 2026-04-24 | Version bumped 1.42.0 → 1.42.1 per docs/versioning.md PATCH policy (spec-text-only, no new user-facing functionality). | 1.42.1 |
| 2026-04-24 | Code review fixes (M1, M2): removed out-of-scope tablet icon-rail behavior from Responsive summary; added a second complete turn to mobile wireframe to match AC #8 wording. | 1.42.1 |
