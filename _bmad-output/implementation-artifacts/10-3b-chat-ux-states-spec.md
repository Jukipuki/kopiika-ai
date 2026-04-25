# Story 10.3b: Chat UX States Spec (Refusals, Consent, Deletion, Rate-Limit, Edge Cases)

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **product designer closing the chat-with-finances UX handoff for Story 10.7**,
I want the **states layer** of the chat screen — principled-refusal UX keyed on the `CHAT_REFUSED.reason` enum (`guardrail_blocked` / `ungrounded` / `rate_limited` / `prompt_leak_detected`) with a correlation-ID copy-to-clipboard affordance, the `chat_processing` consent first-use prompt + version-bump re-prompt flow, the chat-history deletion UX (per-session + delete-all confirmation flows), the abuse/rate-limit soft-block UX, the optional session-summarization surface decision, a full WCAG 2.1 AA conformance pass layered on the 10.3a structural scaffold, and the UA + EN copy-edge-cases posture — specified in [`_bmad-output/planning-artifacts/ux-design-specification.md`](../planning-artifacts/ux-design-specification.md) on top of the skeleton authored by Story 10.3a at [§Chat-with-Finances (Epic 10) — Skeleton Spec](../planning-artifacts/ux-design-specification.md#chat-with-finances-epic-10--skeleton-spec-story-103a) (current location ~L1564-L1799),
so that Story 10.7 (Chat UI) has a scope-locked spec for every non-happy-path surface before FE scaffolding needs to render refusal/consent/rate-limit/deletion UI, Stories 10.4b (canary + prompt-leak detection), 10.5 (SSE + `CHAT_REFUSED` envelope), 10.6a (grounding refusal), 10.10 (chat history + deletion), and 10.11 (abuse + rate-limit) all have a single UX contract their backend error responses are authored against, and the Epic 10 delivery order — which makes 10.3b the gate for finalizing 10.7's refusal/consent/rate-limit UX — is honored.

## Acceptance Criteria

1. **Given** the 10.3a skeleton section at [`_bmad-output/planning-artifacts/ux-design-specification.md` §Chat-with-Finances (Epic 10) — Skeleton Spec (Story 10.3a)](../planning-artifacts/ux-design-specification.md) and specifically its "Reserved for Story 10.3b" subsection, **When** this story lands, **Then** a new **peer-level** `## Chat-with-Finances (Epic 10) — States Spec (Story 10.3b)` section is added **immediately after** the 10.3a skeleton section (before the `### Out of scope for initial chat UX` block — that block is a tail under 10.3a and must remain as the final subsection of the combined chat UX spec; 10.3b does **not** move it, duplicate it, or reword it). The new section starts with a one-line scope note: "States layered on the 10.3a skeleton: refusals, consent, deletion, rate-limit, session-summarization, full WCAG 2.1 AA pass, UA + EN copy edge cases. Happy-path layout is owned by Story 10.3a." All nine items enumerated in the 10.3a "Reserved for Story 10.3b" subsection must be resolved in this section — either specified inline or explicitly cross-referenced to the owning downstream story (10.7 / 10.10 / 10.11) with rationale. No item from that list may be silently dropped.

2. **Given** the `CHAT_REFUSED` envelope contract at [architecture.md §API Pattern — Chat Streaming](../planning-artifacts/architecture.md) with `reason` enum values `guardrail_blocked | ungrounded | rate_limited | prompt_leak_detected | tool_blocked | transient_error` and a `correlation_id`, **When** the refusal UX is specified, **Then** the spec defines a **Principled Refusal** subsection that pins, **per-reason**, a self-contained UX contract:
   - The **copy template** (EN; UA equivalent enumerated in AC #9 for the UA pass). Copy must: (a) be neutral and non-judgmental, (b) never leak the specific filter that matched or the internal rationale, (c) offer a forward path where applicable ("try a different question", "try again later"), (d) stay under ~2 short sentences.
   - The **visual surface**: refusals render as a dedicated **assistant message variant** (distinct from "assistant-complete" / "assistant-streaming" in 10.3a) — left-aligned, neutral surface, with a small refusal icon (use the existing `info` / `alert` icon slot — do not introduce a new design-system token) and muted typography. **No guardrail traffic cop iconography** (🚫 / ⛔️) and no red fill — this is not an error toast; it is a turn outcome. Citation chips do not render on refusal variants.
   - The **correlation-ID affordance**: a single-line "Reference: `<short-id>` · [copy]" row below the refusal copy. `<short-id>` is the first 8 chars of the server-sent `correlation_id` (UX display only; the full UUID is what lands on the clipboard). `[copy]` triggers navigator.clipboard.writeText; success flips the label to "Copied" for 1.5 s and reverts (no toast). Full UUID is announced to screen readers via a visually-hidden span (`class="sr-only"` equivalent) so assistive tech gets the whole value.
   - The **retry guidance** differs by reason: `guardrail_blocked` → "Try asking the question a different way." (no retry button — forcing the same blocked prompt is counter-productive); `ungrounded` → "I can only answer from your data. Try narrowing the question (e.g., a specific month or category)."; `rate_limited` → soft-block UX per AC #5 (retry-after countdown if envelope carries it); `prompt_leak_detected` → "That message couldn't be processed. Please rephrase." (no mention of canary mechanism; security-by-opacity — this is the one reason the user gets the least information); `tool_blocked` (Story 10.4c extension — surfaced when the tool-loop aborts via `ChatToolLoopExceededError`, `ChatToolNotAllowedError`, or `ChatToolAuthorizationError`) → EN: "I couldn't look that up in your data. Please rephrase your question or try again shortly." / UA: "Не вдалося знайти це у ваших даних. Спробуйте переформулювати запит або повторити спробу." (neutral, no mention of "tool" or "allowlist" — mirrors `prompt_leak_detected`'s security-by-opacity posture since the underlying signal is often an adversarial probe or a stuck-loop indicator); `transient_error` (Story 10.5 extension — surfaced when Bedrock throttles or a short-lived service error interrupts the stream) → EN: "Something went wrong while I was thinking. Please try again in a moment." / UA: "Щось пішло не так, поки я думав. Спробуйте, будь ласка, ще раз." (conservative, non-leaky, suggests retry — the user SHOULD retry, but the client, not the backend, decides when).
   - The envelope's `retry_after_seconds` field (nullable per architecture) is honored: when non-null, the rate-limit variant surfaces a countdown; when null, generic "try again later" copy is used. No refusal variant other than `rate_limited` renders `retry_after_seconds` (the field is intentionally meaningless for the other reasons).
   - None of the refusal copy mentions "Guardrails", "jailbreak", "canary", "grounding", or other internal terminology. Those terms live in operator-runbook / logs, not user copy.

3. **Given** the `chat_processing` consent stream shipped in Story 10.1a (separate from `ai_processing`, revocable, versioned) and the `consent_version_at_creation` field on `chat_sessions` shipped in Story 10.1b, **When** the consent UX is specified, **Then** the spec defines a **Consent Flow** subsection with three state surfaces:
   - **First-use modal**: triggered the first time a user opens the chat tab (and only then — not on each session). Rendered as a **Dialog** per the existing [_Modal & Overlay Patterns_](../planning-artifacts/ux-design-specification.md) section (desktop: centered modal with backdrop; mobile: bottom-sheet). The modal copy enumerates (a) what `chat_processing` covers — conversation logging, per-session memory within a session, retention aligned with account lifecycle; (b) how it differs from `ai_processing` (separate stream, independently revocable); (c) a link to the Privacy section of Settings (existing route — do not invent). Primary CTA: "Accept and start chatting". Secondary CTA: "Not now" (dismisses modal, closes chat tab — does **not** grant consent, does **not** persist a "dismissed" flag; user lands back on Feed). There is **no** "Reject forever" action — consent simply isn't granted, so chat doesn't open; the user can revisit via the Chat tab later.
   - **Version-bump re-prompt**: when the user's persisted consent version is older than the current active consent version (versioning semantics per [architecture.md §Consent Drift Policy](../planning-artifacts/architecture.md)), a *different* re-prompt surface appears: **the chat tab is still openable**, the session list still renders (read-only — users can view past sessions), but starting a new session or sending a new message first presents an inline **re-prompt card** at the top of the conversation pane ("Our chat data handling has been updated. Review and accept to keep chatting."). Accept → consent version updated, new session creation/send proceeds. Decline → card stays, chat features remain locked; existing sessions remain read-only (honoring architecture's policy that active sessions continue under their captured consent version but *new* activity requires the current version). This deliberately avoids a full-screen blocking modal on re-prompt — a returning user shouldn't get a consent wall in front of content they can already legally view.
   - **Post-revoke empty state**: after the user revokes `chat_processing` from Settings, the chat tab remains in the navigation (per AC #10, removing it silently would be disorienting) but opening it shows an empty-state page with copy "Chat is disabled until you re-enable chat data processing. [Go to Privacy settings →]". No session list. No composer. This is the same surface a brand-new user sees before first-use consent, but with a different lead sentence (re-enable vs. enable).
   - The spec calls out explicitly that **all three surfaces consume the existing consent API** (`POST /api/v1/users/me/consent`, `GET … ?type=chat_processing`, `DELETE … ?type=chat_processing` per Story 10.1a) — no new endpoints are owed; UX is wired to the backend already shipped.

4. **Given** the chat-history deletion UI owned by Story 10.10, the per-row kebab slot **reserved** on each session row by the 10.3a skeleton (currently slotted but empty), and the existing app-wide deletion pattern from [Story 5.5 (Delete All My Data)](./5-5-delete-all-my-data.md), **When** the deletion UX is specified, **Then** the spec defines a **History & Deletion Flows** subsection with three flows:
   - **Per-session delete**: user taps the `[⋮]` kebab on a session row → popover menu appears with items `Rename` (10.10), `Delete`. (Rename is listed for menu-completeness — its UX copy belongs to 10.10; 10.3b only pins the menu **item order** and the **confirm** shape.) `Delete` opens a confirm dialog: title "Delete this chat?", body "This will permanently remove the conversation and its messages. This cannot be undone.", primary button "Delete" (destructive styling — red text on neutral surface per the existing destructive-action token, no new token), secondary "Cancel". On confirm, the dialog closes, the row animates out (fade + height collapse — honor `prefers-reduced-motion`, fall back to instant removal), and a lightweight toast "Chat deleted" appears bottom-center for 3 s with an "Undo" action that, when tapped within 3 s, reinstates the session *in the UI* **only if** the backend exposes a short delete-grace window. The spec writes the UX contract conditionally: "If 10.10's backend supports undo-within-grace, surface the Undo button; if not, omit the Undo action entirely and keep the toast as a silent confirmation. **Do not fake an undo** that cannot actually unddelete on the server." The conditional is explicit so 10.7 implements one shape or the other — not a placeholder.
   - **Delete-all**: a secondary "Delete all chats" link lives at the bottom of the session list (below the last row, with de-emphasized styling). Tapping it opens a higher-stakes confirm dialog: title "Delete all chats?", body "This will permanently remove every conversation and all its messages. This cannot be undone.", type-to-confirm input with the literal word "delete" required before the primary button enables (match the pattern from [Story 5.5 Delete All My Data](./5-5-delete-all-my-data.md) — do not reinvent it). Primary button "Delete all" (destructive). On confirm, session list empties, empty state renders ("No chats yet. Start a new conversation from the composer below."), no toast/undo (the operation is too destructive for an Undo gesture to be honest about what it rolls back).
   - **Empty state** after deletion: the same empty state that a brand-new user lands on post-consent (AC #3) — single message plus a focused composer. No special "you just deleted everything" messaging; the user already confirmed.
   - The spec explicitly delegates **data export / download** (FR35) to Story 10.10's surface — 10.3b does not author export UI. If 10.10's scope grows to include export, the UX for it is owned there; 10.3b provides no reserved slot, no copy, no menu entry. Forward pointer only.

5. **Given** the abuse / rate-limit envelope owned by Story 10.11 (60 msg/hr/user, 10 concurrent sessions/user, per-user daily token cap, per-IP cap at gateway — see [architecture.md §Rate Limits](../planning-artifacts/architecture.md) and [architecture.md §API Pattern — Chat Streaming](../planning-artifacts/architecture.md)'s `retry_after_seconds` field), **When** the rate-limit UX is specified, **Then** the spec defines a **Rate-Limit Soft-Block** subsection covering three distinct triggers (copy is per-trigger because the forward path differs):
   - **Hourly message cap hit** (60 msg/hr): refusal variant renders with `reason=rate_limited`; copy "You've sent a lot of messages recently. You can continue in `<countdown>`." where `<countdown>` is `retry_after_seconds` formatted as `mm:ss`, live-updating once per second until 0, then the refusal variant is replaced by a soft prompt "You can send messages again. [Send →]" that re-focuses the composer. The composer itself remains visible during the cooldown (per AC #10's "disabling navigation is disorienting" principle) but the Send button is disabled and shows a tooltip ("Try again in mm:ss") on hover/focus; Enter-key send is intercepted with an inline hint.
   - **Concurrent-sessions cap hit** (10 concurrent sessions): **no refusal variant** — this one is prevented *before* the user types. The "New session" CTA in Zone 1 opens a dialog "You have 10 active chats. Close one to start a new session." with a secondary "View chats" action that scrolls the session list into view; no primary action (user must close via kebab-delete to proceed).
   - **Daily token cap hit**: refusal variant renders with `reason=rate_limited` and `retry_after_seconds` set to seconds-until-UTC-midnight by the backend. Copy "You've reached today's chat limit. You can continue after `<HH:MM>` (local time)." where `<HH:MM>` is derived client-side from `retry_after_seconds`. No countdown (a 17-hour live countdown is more stress than help); a local-time wall-clock stamp is less noisy. Composer disabled exactly as in the hourly-cap case.
   - Copy across all three explicitly **avoids blame language** ("spamming", "abusing", "too fast") — the user is a user, not a suspect. The operator runbook and CloudWatch alarms (Story 10.9) surface abuse patterns to the right audience; user-facing copy does not.
   - Per-IP cap at the gateway is **explicitly out of 10.3b's UX scope**: when the API gateway 429s before reaching the app, the existing global error-handling UX applies (toast + "Try again later") — no chat-specific surface. A one-line forward pointer notes this.

6. **Given** the "optional session-summarization UI" item reserved by 10.3a and the server-side summarization policy at [architecture.md §Memory & Session Bounds](../planning-artifacts/architecture.md) ("20 turns or 8k tokens, whichever first. Older turns are summarized server-side, not dropped silently"), **When** the session-summarization UX is specified, **Then** the spec **makes a decision** (not a deferral) between two options and documents the rejected alternative in one line:
   - **Option A (preferred): silent summarization**. No visible UI affordance when the backend summarizes older turns. Older bubbles remain in the scroll buffer as-is; the summary informs the model's next-turn context but is never exposed. Screen-reader announcement: none. Rationale: the summarization is a *memory* optimization, not a *content* operation — users don't need to know their context was compressed any more than they need to know their page was garbage-collected. Surfacing it invites questions ("did I lose something?") that the implementation does not answer.
   - **Option B (rejected): visible "Earlier messages summarized" affordance**. A de-emphasized row appears between the last trimmed turn and the first retained turn. Rejected because it implies information loss the user can act on, which the backend policy does not support (there's no "expand summary" action — the summary is internal).
   - The decision covers UX only; the backend summarization mechanics remain in Story 10.4a's scope. 10.3b pins "silent" so 10.7 does not ship a visible affordance speculatively.

7. **Given** the WCAG 2.1 AA conformance goal at [ux-design-specification.md §Accessibility Strategy — Accessibility Development](../planning-artifacts/ux-design-specification.md) and the structural a11y scaffold shipped by 10.3a (ARIA roles, focus order, keyboard-send semantics, `aria-busy` transition), **When** the full a11y pass is specified, **Then** the spec defines an **Accessibility — Full AA Pass** subsection layered on the scaffold:
   - **Color / contrast**: every state surface introduced by 10.3b (refusal variant, consent modal, rate-limit countdown, deletion confirm dialog, empty-state page) must meet 4.5:1 text contrast and 3:1 non-text contrast against its background. The refusal icon specifically must meet 3:1 against the neutral surface — a muted tint that passes is preferred over a pure gray that doesn't. The destructive-action button ("Delete", "Delete all") contrast is measured against its resting background AND its focus ring.
   - **Focus management for modal dialogs**: the first-use consent modal, the version-bump re-prompt (when displayed as a card), the deletion confirms, and the concurrent-sessions "close one to start" dialog all implement **focus-trap** — focus cycles within the dialog; Tab at the last focusable element returns to the first; Escape dismisses (and for the deletion confirms, is equivalent to Cancel). On dialog open, focus lands on the **safest** action (Cancel for destructive dialogs; Primary for consent acceptance); on dialog close, focus restores to the element that opened the dialog. **All dialogs set `aria-labelledby` on the title element and `aria-describedby` on the body copy.**
   - **Screen-reader announcement semantics** for transient surfaces:
     - **Refusal variant**: announced via the existing conversation pane `aria-live="polite"` — the refusal is *part of* the message log, not a separate notification surface. The correlation-ID row is announced as "Reference, full UUID `<value>`" via the visually-hidden span (AC #2).
     - **Deletion toast** (per-session delete): `role="status"` + `aria-live="polite"` so it doesn't interrupt. "Chat deleted. Undo available for 3 seconds." The "Undo" button is focusable via Tab; pressing Enter restores.
     - **Rate-limit countdown**: the `mm:ss` value **must not** re-announce once per second (assistive tech spam). Announce only on initial render and on reaching 0 ("You can send messages again"). Visual countdown still live-updates; the announcement is throttled.
     - **Cooldown composer state**: the disabled Send button's tooltip is available via keyboard focus (the tooltip pattern in the existing design system must expose on focus, not hover-only — cite the existing a11y guidance rather than re-spec).
   - **Reduced-motion**: all animations introduced by 10.3b (row fade-out on delete, toast slide-in, refusal-variant fade-in, countdown transitions) honor `prefers-reduced-motion: reduce` with an instant-state fallback. The scaffold already established this posture for the streaming indicator; 10.3b extends it to every new state surface.
   - **Keyboard-only completeness**: document the full keyboard-only task inventory — (a) open chat tab, (b) accept first-use consent, (c) start new session, (d) send a message, (e) receive a refusal and copy correlation-ID, (f) delete a session, (g) navigate between sessions, (h) recover from rate-limit. Each must be achievable without a pointing device. The Tab order from 10.3a remains authoritative; 10.3b **does not reorder** but extends into the new surfaces (modal → dialog focus-trap rules above).
   - **Narration copy audit**: every new string introduced in 10.3b (refusal copy per reason, consent modal headings + body, deletion dialog copy, rate-limit copy, empty-state copy, toast copy) is reviewed for screen-reader clarity — no unicode icon leakage into the announced string (icons are `aria-hidden="true"`; their meaning is carried by adjacent text).

8. **Given** the chat-feature UA + EN bilingual posture inherited from [`frontend/src/i18n/`](../../frontend/src/i18n/) and the 10.3a handoff note that copy is 10.3b's responsibility, **When** the UA + EN copy is specified, **Then** the spec defines a **Copy Reference Table — UA + EN** subsection with **every** translatable string introduced by 10.3b rendered as a table row:
   - Columns: `key` (i18n key under the `chat` namespace, kebab/dot style matching the existing i18n convention), `EN`, `UA`, `notes`.
   - Covered surfaces (minimum): refusal copy × 4 reasons × {headline / retry-guidance} = 8 rows; consent first-use modal (title / body / primary / secondary) = 4 rows; version-bump re-prompt card (headline / body / accept / decline) = 4 rows; post-revoke empty state (headline / body / CTA) = 3 rows; deletion flows (per-session confirm title / body / primary / secondary / toast / undo) = 6 rows; delete-all (title / body / type-to-confirm placeholder / primary / secondary / empty-state lead) = 6 rows; rate-limit (hourly / daily / concurrent-sessions) × {body / CTA / tooltip} = 9 rows; deletion menu items (rename / delete) = 2 rows; total ≈ **42 rows**. Exact count may drift ±3 during authoring; no row may be omitted silently.
   - **UA copy edge cases** called out explicitly inline in the `notes` column:
     - **Grammatical case**: interpolated values (countdown, session title, session count) must render in UA-correct grammatical case — "You have 10 active chats" ↔ "У вас 10 активних чатів", "You have 1 active chat" ↔ "У вас 1 активний чат". The plural rules follow the existing ICU MessageFormat posture used by the rest of the app (cite: existing `_common.json` plural usage under `frontend/src/i18n/` — do not introduce a new library).
     - **Length**: UA strings average ~20–25% longer than EN. Where copy lands in tight UI slots (tooltip on disabled Send button, kebab popover menu items, countdown inline hint), the UX spec pins a **maximum character budget** per string (EN count + 30% headroom) and if the natural UA translation exceeds the budget, the spec recommends a shorter phrasing rather than truncating at render-time.
     - **Avoid false cognates**: "session" → "чат" (not "сесія", which in casual UA reads as something closer to "drug trip"); "chat" → "чат" (the English loan is naturalized and unambiguous). The table's `notes` column flags each row where the obvious literal UA translation would mislead.
     - **Locale-aware time formatting**: the rate-limit wall-clock (AC #5's daily cap) renders `HH:MM` in 24-hour format in UA; in EN it follows the user's browser locale (en-US → 12-hour; en-GB → 24-hour). No AM/PM in UA. Countdown format `mm:ss` is locale-neutral.
   - **Do NOT author** refusal-internal terms in either language: "guardrail", "grounding", "canary", "jailbreak", "prompt injection" must not appear in user-facing copy. The table includes a short "forbidden terms" bullet list at the top of the notes.
   - The keys themselves are **reserved** by 10.3b (named, documented in the table) but the actual translation files at [`frontend/src/i18n/`](../../frontend/src/i18n/) are **edited by Story 10.7** when it ships the components that consume them. 10.3b's deliverable is the **contract** (keys + EN + UA prose in the spec), not the JSON edits.

9. **Given** at least **two** user-journey flows introduced by 10.3b require a flow diagram to unambiguously specify state transitions, **When** the wireframes + flows are added, **Then** the spec embeds at least three artifacts — matching 10.3a's ASCII + Mermaid convention (prose + ASCII + Mermaid first; no Figma dependency):
   - **Flow diagram 1 — Refusal branch Mermaid**: `sequenceDiagram` layered on 10.3a's happy-path lifecycle — User → composer → Enter → user bubble renders → SSE opens → (server Guardrails/grounding/canary/rate-limit fires) → SSE emits `CHAT_REFUSED` envelope → refusal variant renders → correlation-ID copy-affordance available. Include the four `reason` branches explicitly so the diagram is a direct companion to AC #2's per-reason copy.
   - **Flow diagram 2 — Consent state machine Mermaid**: `stateDiagram` with states `no-chat-consent`, `chat-consent-current`, `chat-consent-stale`, `chat-consent-revoked` and transitions (first-use-accept, first-use-not-now, version-bump-detected, re-prompt-accept, re-prompt-decline, revoke-from-settings). Terminal states are covered; cycle from `revoked` → `current` via re-grant from Settings is included.
   - **ASCII wireframe — Refusal variant in conversation pane**: a compact ASCII mock at the same fidelity as 10.3a's Wireframe 1, showing a user turn, a preceding complete assistant turn, and a rendered refusal variant (icon + copy + "Reference: a1b2c3d4 · [copy]" row). Annotate breakpoint and zone labels.
   - (Optional but encouraged: a fourth ASCII mock of the rate-limit cooldown composer state. If the author finds the spec prose + EN/UA copy table covers it unambiguously, this is skippable — but the prior three are mandatory.)

10. **Given** the chat tab's always-present navigation entry established by 10.3a (Option A — 5th bottom tab) and the post-consent-revoke state defined in AC #3, **When** the spec addresses "disabled-feature in primary navigation" UX, **Then** a short **Navigation Visibility Rule** subsection is added that pins one rule and documents why:
   - **Rule**: the Chat tab is always visible in primary navigation — on mobile (bottom tab) and desktop (top nav) — regardless of `chat_processing` consent state. Tapping it from a revoked-consent state surfaces the post-revoke empty state (AC #3), **not** a hidden-feature / 404 / "go to settings" redirect.
   - **Why**: hiding navigation entries based on feature-availability state is disorienting for returning users (they used to see Chat there and now can't find it) and pushes the user into a hunt through Settings to re-enable. Keeping the entry visible + landing on a purposeful empty state with a direct "Go to Privacy" CTA is the cleaner path.
   - **Scope**: this rule governs **only** the consent-revoked state. Rate-limit, deletion, and in-cooldown states do not hide the tab either, but they don't need to — the tab is inherently never hidden.

11. **Given** the 10.3a skeleton reserved 9 items for 10.3b (see its "Reserved for Story 10.3b" subsection) and this story resolves them across ACs #2–#10, **When** this story lands, **Then** the new states-spec section includes a short **Scope Resolution Matrix** subsection — a table with columns `Reserved Item (10.3a) | Resolved in AC # | Owning Section`. Every item from the 10.3a reserved list must appear in the table. Items explicitly delegated to downstream stories (e.g., citation *content* to 10.6b, chat history management *UI mechanics* to 10.10, rate-limit *envelope values* to 10.11) cite the target story in the "Owning Section" column with a one-line rationale. This is a deliberate redundancy with the ACs themselves — it gives a reviewer a single-glance check that no 10.3a reservation was dropped.

12. **Given** the 10.3a `docs/tech-debt.md` posture ("10.3a files no new TD entries — this story's deliverable is spec text; tech-debt is reserved for code-shaped debt"), **When** this story lands, **Then** **10.3b similarly files no new TD entries**. Any decision deferred by 10.3b (e.g., "we should probably add micro-animation tokens for the toast slide-in, but the existing `fast` motion token covers it for now") is inlined in the spec prose with a forward pointer to 10.7 — not filed as `TD-NNN`. Run `grep -n '10\.3b\|TD-.*10\.3' docs/tech-debt.md` and confirm zero matches. The exception: if authoring 10.3b reveals a **pre-existing** gap in the design-system tokens (e.g., the destructive-action token doesn't meet WCAG AA against the new refusal-variant surface), that is a legitimate `docs/tech-debt.md` entry because the gap pre-exists; the story may open a single TD-NNN entry with scope "design-system token remediation" and a forward pointer to a design-system follow-up. As of 2026-04-24 research pass, no such pre-existing gap has been identified — this exception is defensive, not planned.

13. **Given** the design-backlog register at [`_bmad-output/planning-artifacts/design-backlog.md`](../planning-artifacts/design-backlog.md) and the fact that 10.3a ran this sweep and closed nothing (no entries referenced the chat placeholder), **When** 10.3b lands, **Then**: `grep -n '10\.3\|chat\|Chat' _bmad-output/planning-artifacts/design-backlog.md` is run. If any entry references the chat states being specified, close it with a reference to this story. If no match (current state as of 2026-04-24 — the register contains only DS-1 / DS-2 / DS-3, none referencing chat), nothing is added — no invented entries. Result is recorded in the Dev Agent Record's Debug Log.

14. **Given** the scope boundary with Story 10.7 (Chat UI — frontend implementation) established by 10.3a ("10.3a is a pointer, not a code spec"), **When** 10.3b writes its own **Frontend Implementation Handoff Extensions** subsection (sibling to 10.3a's subsection), **Then** it lists *only* the additions to 10.7's surface that 10.3b introduces — no restatement of the skeleton's route / folder / i18n namespace. Minimum content:
   - **New i18n key namespaces added under `chat`**: `chat.refusal.*`, `chat.consent.*`, `chat.delete.*`, `chat.ratelimit.*`, `chat.empty.*` (enumerated more granularly in AC #8's copy table). 10.7 stubs these when consuming.
   - **Icon-slot dependencies**: the refusal variant requires an `info` or `alert` icon slot; the deletion destructive action uses the existing destructive-action token. Both slot names cited; no new design-system tokens introduced by this story (per AC #12).
   - **API surface consumed** (not authored here): `POST/GET/DELETE /api/v1/users/me/consent` (Story 10.1a — shipped); `DELETE /api/v1/chat/sessions/{id}` and `DELETE /api/v1/chat/sessions` (Story 10.10 — pending); `CHAT_REFUSED` envelope with `reason` + `correlation_id` + `retry_after_seconds` (Story 10.5 — pending). 10.3b is a consumer of each; it does **not** author the endpoint shapes.
   - **No library / state-management / streaming-client prescription**, same posture as 10.3a.

## Tasks / Subtasks

- [x] **Task 1: Insert the States Spec section in ux-design-specification.md** (AC: #1)
  - [x] 1.1 Open [`_bmad-output/planning-artifacts/ux-design-specification.md`](../planning-artifacts/ux-design-specification.md) and locate the end of the 10.3a skeleton section (the final `### Frontend Implementation Handoff` subsection of the 10.3a section) — insert the new `## Chat-with-Finances (Epic 10) — States Spec (Story 10.3b)` section **after** the Frontend Implementation Handoff subsection and **before** the `### Out of scope for initial chat UX` block, preserving that block as the tail of the combined chat UX spec.
  - [x] 1.2 Write the one-line scope note immediately under the new section header.
  - [x] 1.3 Confirm no skeleton content (10.3a) has been accidentally duplicated or reworded.

- [x] **Task 2: Specify Principled Refusal UX** (AC: #2)
  - [x] 2.1 Author the Principled Refusal subsection with a per-reason table (`reason` → `copy` → `retry guidance` → `visual variant notes`).
  - [x] 2.2 Pin the correlation-ID row: `Reference: <first-8-of-uuid> · [copy]`; 1.5 s label flip; `sr-only` full-UUID announcement.
  - [x] 2.3 Pin the refusal variant visual: icon slot (`info`/`alert`, existing), muted typography, no citation chips, no red fill, no traffic-cop iconography.
  - [x] 2.4 Document the `retry_after_seconds` null/non-null handling.
  - [x] 2.5 Record the "forbidden terms" list in prose (Guardrails, grounding, canary, jailbreak, prompt injection) and cross-reference AC #8 for its table appearance.

- [x] **Task 3: Specify Consent Flow UX** (AC: #3)
  - [x] 3.1 Author the first-use modal spec (Dialog pattern, content, primary/secondary CTA, no "reject forever").
  - [x] 3.2 Author the version-bump re-prompt spec (inline card, read-only existing-session access, new-activity accept/decline behavior).
  - [x] 3.3 Author the post-revoke empty-state spec (tab stays visible, empty page with Privacy link).
  - [x] 3.4 Cross-reference the existing consent API — do not invent endpoints.

- [x] **Task 4: Specify History & Deletion Flows** (AC: #4)
  - [x] 4.1 Author per-session delete flow (kebab menu → confirm → animated removal → toast; undo is conditional on 10.10 backend).
  - [x] 4.2 Author delete-all flow (type-to-confirm, reuse Story 5.5 pattern, no undo).
  - [x] 4.3 Author the post-deletion empty state (same as post-consent empty state).
  - [x] 4.4 Explicitly forward-pointer export (FR35) to Story 10.10 — do not author export UI.

- [x] **Task 5: Specify Rate-Limit Soft-Block UX** (AC: #5)
  - [x] 5.1 Author hourly-cap refusal + cooldown composer state + disabled Send button + tooltip.
  - [x] 5.2 Author concurrent-sessions cap dialog (close-one-to-start).
  - [x] 5.3 Author daily-cap refusal with local-time wall-clock + composer disable.
  - [x] 5.4 Forward-pointer per-IP cap as out of 10.3b's UX scope (global error handling owns it).
  - [x] 5.5 Audit copy for blame language — none.

- [x] **Task 6: Decide Session-Summarization UX** (AC: #6)
  - [x] 6.1 Write the Option A / Option B comparison one-paragraph.
  - [x] 6.2 Pin the decision (Option A — silent) and the one-line Option B rejection.

- [x] **Task 7: Full WCAG 2.1 AA Pass** (AC: #7)
  - [x] 7.1 Author the color/contrast audit block per state surface.
  - [x] 7.2 Author the focus-management / focus-trap rules for every dialog introduced by 10.3b.
  - [x] 7.3 Author the screen-reader announcement semantics (refusal in conversation log, deletion toast `role=status`, rate-limit throttled announcement, cooldown tooltip focusable).
  - [x] 7.4 Author the `prefers-reduced-motion` coverage rule for every new animation surface.
  - [x] 7.5 Document the keyboard-only task inventory (8 tasks per AC #7).
  - [x] 7.6 Narration copy audit checklist (no unicode icons in announced strings; icons `aria-hidden="true"`).

- [x] **Task 8: Author the Copy Reference Table (UA + EN)** (AC: #8)
  - [x] 8.1 Enumerate every string introduced by 10.3b with its i18n key under the `chat` namespace.
  - [x] 8.2 Author EN prose and UA prose per row.
  - [x] 8.3 Annotate UA grammatical-case / plural rules per row where interpolation exists.
  - [x] 8.4 Pin the per-string max-character budget (EN +30%) for tight-slot strings.
  - [x] 8.5 Add the "forbidden terms" bullet list at the table's top.
  - [x] 8.6 Spot-check a few rows against existing `_common.json` plural posture.

- [x] **Task 9: Author wireframes + flows** (AC: #9)
  - [x] 9.1 Mermaid `sequenceDiagram` — refusal branch lifecycle (all 4 reasons).
  - [x] 9.2 Mermaid `stateDiagram` — consent state machine.
  - [x] 9.3 ASCII wireframe — refusal variant in conversation pane.
  - [x] 9.4 (Optional) ASCII wireframe — rate-limit cooldown composer state.
  - [x] 9.5 Annotate each artifact with breakpoint/zone labels (matching 10.3a convention).

- [x] **Task 10: Navigation Visibility Rule** (AC: #10)
  - [x] 10.1 Author the one-rule + rationale subsection.
  - [x] 10.2 Scope the rule to consent-revoked only; note other states (rate-limit, deletion) do not hide the tab either.

- [x] **Task 11: Scope Resolution Matrix** (AC: #11)
  - [x] 11.1 Build the three-column table (`Reserved Item | Resolved in AC # | Owning Section`).
  - [x] 11.2 Every 10.3a reservation appears in a row.
  - [x] 11.3 Items delegated downstream (to 10.6b / 10.7 / 10.10 / 10.11) cite the target story.

- [x] **Task 12: Frontend Implementation Handoff Extensions** (AC: #14)
  - [x] 12.1 Enumerate new i18n key namespaces under `chat`.
  - [x] 12.2 Cite icon-slot dependencies without introducing new tokens.
  - [x] 12.3 List consumed API surfaces (consent, deletion, CHAT_REFUSED).
  - [x] 12.4 Reiterate no library / state-management / streaming-client prescription.

- [x] **Task 13: Tech-debt + design-backlog sweep** (AC: #12, #13)
  - [x] 13.1 `grep -n '10\.3b\|TD-.*10\.3' docs/tech-debt.md` — expect no matches; record result in Debug Log.
  - [x] 13.2 `grep -n '10\.3\|chat\|Chat' _bmad-output/planning-artifacts/design-backlog.md` — expect no matches; close anything that does match; record in Debug Log.
  - [x] 13.3 Confirm no new TD-NNN entry opened by 10.3b (the AC #12 exception for pre-existing design-system token gaps is *defensive*; do not open a TD entry proactively).

- [x] **Task 14: Verification pass** (AC: all)
  - [x] 14.1 Re-read the States Spec section end-to-end.
  - [x] 14.2 Confirm every item in 10.3a's "Reserved for Story 10.3b" is resolved in the Scope Resolution Matrix (Task 11).
  - [x] 14.3 Confirm no code was prescribed (library / SSE client / state-management) in the Frontend Implementation Handoff Extensions.
  - [x] 14.4 Confirm the `### Out of scope for initial chat UX` block is still the **last** subsection of the combined chat UX spec (voice I/O + write-actions UI preserved verbatim).
  - [x] 14.5 Confirm all intra-doc cross-refs use section-name links (not absolute line numbers) per 10.3a's Developer Guardrail #9.
  - [x] 14.6 Record in Debug Log: the session-summarization decision (Option A/B) and one-line rationale; the refusal-variant icon-slot chosen (`info` vs `alert`); any AC-level decisions that deviated from the authored spec.

## Dev Notes

### Scope Summary

- **Pure-documentation story**, same as 10.3a. One file edited: [`_bmad-output/planning-artifacts/ux-design-specification.md`](../planning-artifacts/ux-design-specification.md). Zero code, zero schema, zero infra, zero test impact.
- **10.3b finalizes the UX contract** for every non-happy-path chat surface. It is a hard prerequisite for Story 10.7 (Chat UI) shipping its refusal / consent / deletion / rate-limit components.
- **10.3b is NOT a prerequisite for** 10.4a (AgentCore session handler), 10.4b (prompt hardening + canary tokens), 10.4c (tool manifest), 10.5 (chat streaming API + SSE), 10.6a (grounding enforcement + harness), 10.6b (citation payload API), 10.8a/b (red-team corpus + CI gate), 10.9 (safety observability), 10.10 (chat history + deletion backend), or 10.11 (abuse + rate-limit backend) — those are backend / infra tracks, and each **authors its error envelope / consent flag / rate-limit value independently**. 10.3b is a consumer of those contracts; when downstream stories adjust the envelope shape (e.g., adding a new `reason` enum value), 10.3b's copy table is extended in that story's UX slice — not re-opened as an amendment to 10.3b.
- **10.3b ships concurrently with 10.4a–10.6b**; the skeleton is the only prerequisite.
- **Story 10.7 consumes this spec.** If 10.7 ships before 10.3b closes, 10.7's refusal / consent / deletion / rate-limit UI is blocked pending this spec; the happy-path UI (authored from 10.3a alone) can still scaffold.

### Key Design Decisions (non-obvious)

- **Why refusals render as an assistant-message variant, not a toast or banner.** A refusal is the *outcome of a turn*, not a system notification. Rendering it inline in the conversation log preserves the mental model (every user turn gets exactly one agent response — a message, a refusal, or a rate-limit card, but always exactly one). Toasts dismiss; banners persist above the content; neither belongs in a chat transcript. The `aria-live="polite"` log from 10.3a does the announcement work automatically.
- **Why the correlation-ID displays the first 8 chars but copies the full UUID.** Displaying 36 chars of UUID in the UI is visual noise for users who never need it. The 8-char prefix is enough for a support engineer to disambiguate in logs *if and only if* the user pastes the clipboard payload (which is the full UUID). This pattern appears elsewhere (GitHub's short-SHA display, Vercel's deployment IDs) and is well-understood. The `sr-only` full-UUID announcement exists because a screen-reader user can't visually read "a1b2c3d4" and compare with logs — the clipboard is their only copy mechanism.
- **Why `prompt_leak_detected` gets the least informative copy.** The canary-detection mechanism is a defense; exposing its presence to a curious user invites probing ("oh, I triggered a canary — what word did I use?"). The refusal copy is generic ("Please rephrase") because the system is deliberately not confirming the detection class. This asymmetry vs. the other three reasons (which are more forthcoming) is intentional security-by-opacity, not UX inconsistency — operator runbook ([docs/operator-runbook.md](../../docs/operator-runbook.md), Chat section, owned by Story 10.9) carries the full diagnostic context; users get "retry".
- **Why consent first-use is a modal but version-bump re-prompt is an inline card.** Version bumps are by definition *returning* users — they already accepted consent once; they already know what chat is; they already have existing sessions they can legally view. A full-screen modal between them and their session list is user-hostile. An inline card that locks *new activity* but permits *reading* is the smallest correct surface.
- **Why the Chat tab stays visible after consent revocation.** Hiding navigation based on mutable state is a well-known source of user confusion ("where did Chat go?"). The empty state is the honest answer: "the feature exists, you disabled it, here's how to re-enable." The post-revoke empty state copy is **deliberately forward-oriented** — single CTA to Privacy settings, no guilt-trip about the revocation decision.
- **Why silent session-summarization (Option A) and not visible (Option B).** The backend summarizes *context window*, not *content*. The summary exists to inform the model's next-turn, not to present a "compressed transcript" to the user. Surfacing it implies the user can act on it ("can I expand the summary?" — no, the mechanism doesn't support that) and creates anxiety about information loss ("did I lose something?" — no, the earlier bubbles are still in the scroll buffer). The correct UX is absence-of-UX. If a future epic adds true cross-session memory (TD-040), that memory gets its own UX story — it isn't retrofitted onto summarization.
- **Why the deletion-Undo is conditional on 10.10's backend.** A common UX anti-pattern is a confidence-building Undo button that issues a new write instead of actually rolling back the delete. If 10.10's backend has a grace window (e.g., soft-delete + TTL reaper), Undo is real; if 10.10 is a hard delete, Undo either silently fails (bad) or fabricates (worse). The spec pins the conditional rather than the button: implement one shape or the other based on what 10.10 ships — **do not fake**.
- **Why the delete-all uses type-to-confirm, but per-session delete is a single confirm + toast.** Blast-radius gradient. Losing one conversation is annoying; losing all of them is catastrophic. The existing pattern from Story 5.5 (Delete All My Data) established type-to-confirm for catastrophic deletes; reusing it here preserves muscle memory and avoids competing patterns.
- **Why the rate-limit copy is blame-neutral.** "Too fast" / "spamming" / "abusing" pathologizes a user who is almost certainly not the adversary the rate-limit was designed to stop. Real adversaries don't read the UI; legitimate users do. The legitimate user who hits the 60-msg/hr cap is a power user, not a threat.
- **Why rate-limit copy uses a countdown for hourly and a wall-clock for daily.** A countdown from 59:59 to 00:00 is informative; a countdown from 17:43:22 to 00:00:00 is anxiety-inducing theater. "You can continue after 00:42" is just as accurate and less hostile.
- **Why UA pluralization is called out explicitly.** UA has three plural forms (singular / few / many: "1 чат", "2–4 чати", "5+ чатів"). EN has two (singular / plural). A string that works in EN ("You have {n} active chats") requires ICU MessageFormat `{n, plural, one{} few{} many{}}` in UA. Missing this is a common FE bug — calling it out in the spec prevents a post-ship correction.
- **Why 10.3b doesn't touch the translation JSON files.** Copy lives in the spec as the *contract*; the JSON files are implementation. Story 10.7 edits JSON when it renders components that consume the keys. Separating contract (spec) from implementation (JSON) keeps the spec reviewable as a document and the JSON reviewable as code.
- **Why the refusal-variant icon is `info` or `alert` and explicitly not new.** The design system already has these slots ([ux-design-specification.md §Icons](../planning-artifacts/ux-design-specification.md)). Introducing a `refusal` icon token would force a design-system review pass and delay 10.3b for no UX win — the `info` semantic is accurate (the refusal is information about why the turn didn't complete, not an error the user caused). Whether the author picks `info` or `alert` is noted in the Debug Log for 10.7's reference.
- **Why no Figma mockups, same as 10.3a.** The existing UX spec is written-word + ASCII + Mermaid (see the journey flows around [ux-design-specification.md L703-L858](../planning-artifacts/ux-design-specification.md#L703-L858)). Introducing a Figma dependency now — especially for text-heavy surfaces like refusal copy and modal confirmations — forks the source-of-truth: prose here + mock there will diverge on the first edit. Match the convention.

### Source Tree Components to Touch

```
_bmad-output/planning-artifacts/
├── ux-design-specification.md               # ADD the new §Chat-with-Finances (Epic 10) — States Spec (Story 10.3b) section; do NOT edit the 10.3a skeleton section; preserve the "Out of scope for initial chat UX" tail block verbatim.
└── design-backlog.md                        # grep-then-maybe-close any 10.3 entry (none exist as of 2026-04-24; expected no-op).

# Reference-only (not edited by this story — cited by the spec):
_bmad-output/planning-artifacts/architecture.md           # §API Pattern — Chat Streaming (CHAT_REFUSED envelope), §Consent Drift Policy, §Memory & Session Bounds, §Rate Limits — all consumed, none edited.
_bmad-output/implementation-artifacts/10-3a-chat-ux-skeleton.md    # the skeleton this story layers on; cross-referenced, not edited.
_bmad-output/implementation-artifacts/5-5-delete-all-my-data.md    # the type-to-confirm pattern reused here.
_bmad-output/implementation-artifacts/10-1a-chat-processing-consent.md    # consent API shapes consumed by the first-use/version-bump/revoke UX.
_bmad-output/implementation-artifacts/10-1b-chat-sessions-messages-schema-cascade.md    # session list projection + cascade semantics.
frontend/src/i18n/                          # i18n namespace home; NOT edited by this story (keys are reserved in the spec; 10.7 edits JSON).
```

**Do NOT touch:**

- `frontend/` — no code in this story. 10.7 builds the UI.
- `backend/` — no API surface owed; 10.3b consumes existing/pending endpoints.
- `docs/tech-debt.md` — no new entries (AC #12; defensive exception is for a pre-existing design-system token gap only).
- `docs/operator-runbook.md` — chat runbook is owned by Story 10.9.
- `_bmad-output/planning-artifacts/architecture.md` — the chat architecture sections are authoritative; 10.3b consumes, not edits.
- `_bmad-output/planning-artifacts/epics.md` — the epic description stays as-is; 10.3b is a story, not an epic rewrite.
- The existing **10.3a skeleton section** of `ux-design-specification.md` — do NOT edit it. 10.3b appends a peer-level section.

### Testing Standards Summary

- **No automated tests.** This is spec text. The validation bar is:
  - (a) a self-review pass that confirms the scope-boundary with 10.3a is honored (no skeleton surface pre-empted or re-authored) and every 10.3a reservation is resolved (Scope Resolution Matrix — AC #11);
  - (b) a link-resolution pass — every markdown `[link](path)` and anchor in the new section resolves against the current doc / file tree;
  - (c) a cross-reference pass — confirm the references to architecture sections (`§API Pattern — Chat Streaming`, `§Consent Drift Policy`, `§Rate Limits`, `§Memory & Session Bounds`) resolve and are consistent with the authoritative text;
  - (d) a copy-integrity pass — every string in the UA + EN copy table reads naturally in both languages and the UA pluralization annotations match the existing `_common.json` posture (spot-check 3–5 rows).
- **Verification commands** (all read-only):
  ```bash
  # confirm the new section lands and the skeleton is untouched
  grep -n "Chat-with-Finances" _bmad-output/planning-artifacts/ux-design-specification.md  # expect 2 matches: skeleton + states

  # confirm the "Out of scope" tail is still last
  grep -nE "^## |^### Out of scope for initial chat UX" _bmad-output/planning-artifacts/ux-design-specification.md | tail -5

  # confirm no new TD entry for 10.3b
  grep -n "10\.3b\|TD-.*10\.3" docs/tech-debt.md   # expect: no match

  # confirm design-backlog sweep outcome
  grep -n "10\.3\|chat\|Chat" _bmad-output/planning-artifacts/design-backlog.md  # expect: no match (current state 2026-04-24)

  # confirm forbidden terms don't leak into user-facing copy table
  # (manual inspection — automated grep is too lossy because these terms legitimately appear in operator / dev-facing prose nearby)
  ```

### Project Structure Notes

- The UX spec is a single large file in `_bmad-output/planning-artifacts/`. Still **not** sharded. In-place edits remain the established pattern.
- 10.3a's ACs cited pre-edit line numbers (L1563-L1583 etc.). Those shifted when the skeleton landed. 10.3b's ACs cite **section names** (`§Chat-with-Finances (Epic 10) — Skeleton Spec (Story 10.3a)`, `§API Pattern — Chat Streaming`, etc.) per 10.3a's Developer Guardrail #9 — header anchors are stable across subsequent edits.
- `_bmad-output/planning-artifacts/design-backlog.md` currently contains DS-1 / DS-2 / DS-3. None reference chat. Expected no-op.
- `docs/tech-debt.md` currently contains TD-040 (persistent cross-session chat memory) and TD-041 (chat subscription gate pending payments epic) as the chat-adjacent entries. Neither is load-bearing for 10.3b — TD-040 is out of scope for Epic 10 entirely; TD-041 is a payments-epic follow-up. 10.3b does not close or modify either.

### Developer Guardrails (things that will bite you)

1. **Do not edit the 10.3a skeleton section.** Your mandate is to append a *peer-level* States Spec section. If you find yourself re-writing a sentence in the skeleton (even an obvious fix), **stop** — file it as a 10.7 or 10.3a-follow-up pass, or request an out-of-scope amendment. Mixing skeleton-edits into 10.3b conflates the two stories' surfaces and breaks the "10.3a was scope-locked before 10.3b layered on" audit trail.
2. **Do not write happy-path content in 10.3b.** If you find yourself describing the conversation layout, the composer shape, the citation chip row layout, the streaming indicator, or the four happy-path message types, stop — that's 10.3a's scope. You may *reference* those surfaces (e.g., "refusal variant replaces the assistant-complete variant from 10.3a") but not re-specify them.
3. **Do not author backend behavior.** Rate-limit values (60 msg/hr, 10 concurrent sessions, daily token cap) come from Story 10.11's envelope — do not duplicate the numbers into the spec prose. The spec says "the envelope carries a `retry_after_seconds`"; it does not say "the user gets 60 messages per hour". That pinning already lives in [architecture.md §Rate Limits](../planning-artifacts/architecture.md); duplicating it invites drift.
4. **Do not author the CHAT_REFUSED envelope shape.** The envelope (keys, enum values) is authoritative in [architecture.md §API Pattern — Chat Streaming](../planning-artifacts/architecture.md). 10.3b consumes `reason` ∈ {`guardrail_blocked`, `ungrounded`, `rate_limited`, `prompt_leak_detected`} — if the author thinks a fifth reason is needed, that's an architecture amendment story (possibly Story 10.5 scope), not a 10.3b edit.
5. **Do not introduce new design-system tokens.** The refusal variant uses existing icon slots and the existing muted-typography treatment. Destructive action uses the existing destructive-action token. If the author finds a legitimate gap (e.g., contrast ratio failure), AC #12's defensive exception applies — but the default is **no new tokens**.
6. **Do not pin component-library, state-management, SSE-client, or clipboard-API choices in the Frontend Handoff Extensions subsection.** `navigator.clipboard.writeText` is a *platform* primitive, not a library choice — that's fine to cite. But "use a toast library from X" or "use a state machine library for the consent state diagram" is 10.7's call. The state diagram in the spec is a *UX contract*, not a prescription for the implementation tool.
7. **ASCII wireframes and Mermaid diagrams** — same posture as 10.3a. ASCII boxes using `+`, `-`, `|`, `>`; reliable Unicode glyphs only (`↓`, `→`, `⋮`, `·`); **avoid** `▍` (10.3a's post-review learning — it shifts ASCII frames across monospace fonts). Mermaid `sequenceDiagram` for the refusal branch, `stateDiagram` for the consent state machine — not `flowchart`.
8. **Do not cite absolute line numbers in the architecture doc.** Cite section headers (`§API Pattern — Chat Streaming`, `§Consent Drift Policy`) — same rule as 10.3a Guardrail #9. The architecture doc is actively edited by 10.4a / 10.5 / 10.6a.
9. **Do not invent i18n keys that don't follow the existing convention.** Look at `frontend/src/i18n/` for the extant key style (kebab or dot; namespace-rooted; pluralized keys use ICU `plural`). The spec's key names must be drop-in compatible with 10.7's JSON stubbing.
10. **UA copy must be *authored*, not machine-translated and pasted.** The project has a UA-first posture (see Story 1.6, all existing i18n JSON files). Poor UA copy in the spec is caught by the project team's native-speaker reviewers, but landing it in a spec prematurely is wasteful rework. If the story author doesn't have UA fluency, the copy-table authoring is a collaboration with a UA-native reviewer — **plan for that** rather than shipping a machine-translated first draft.
11. **Scope Resolution Matrix (AC #11) is not optional.** A reviewer scanning this story for scope-completeness uses that matrix as the first check. If an item from 10.3a's Reserved list is dropped silently, the matrix makes it obvious. If a drop is deliberate (e.g., rename popover delegated to 10.10), cite the target story in the matrix's "Owning Section" column; don't omit the row.
12. **Do not re-decide anything the architecture doc already decided.** The consent stream is separate from `ai_processing` (architecture + 10.1a). The `CHAT_REFUSED.reason` enum is finite and fixed. The rate-limit values are backend-owned. 10.3b authors the **UX** for those decisions; it does not re-litigate them.

### Previous Story Intelligence

- **From Story 10.3a** ([`10-3a-chat-ux-skeleton.md`](./10-3a-chat-ux-skeleton.md)): the skeleton is shipped. Its "Reserved for Story 10.3b" subsection enumerates the 9 surfaces 10.3b is accountable for. The Code Review section of 10.3a flagged 4 LOW findings (L3–L6) that are story-local — 10.3b should **not** resolve them (that was 10.3a's call); but 10.3b should **not reproduce** the patterns that caused them: (a) prefer `[Markdown](#anchor-link)` over italic `_Section Names_` where the anchor is stable; (b) avoid `▍` in ASCII art; (c) don't leave rejection rationales one-sided (rejecting Option B for mobile should also address desktop if relevant); (d) refer to `### sections` as sections and `**bold labels**` as sub-labels, not both as "sections".
- **From Stories 10.1a / 10.1b**: `chat_processing` consent and `chat_sessions` / `chat_messages` schema are shipped. The consent API (`POST/GET/DELETE /api/v1/users/me/consent?type=chat_processing`) and the session schema (`consent_version_at_creation` field) are the surfaces 10.3b's consent UX consumes. No API authoring owed.
- **From Story 10.2**: Bedrock Guardrails + CloudWatch alarm shipped. 10.3b surfaces Guardrails behavior as the `CHAT_REFUSED.reason=guardrail_blocked` refusal variant — it does not re-author the Guardrail config or alarm thresholds.
- **From Story 5.5** (Delete All My Data): the type-to-confirm pattern for catastrophic deletes is established. 10.3b's delete-all flow reuses it. Look at Story 5.5's spec / code for the exact copy pattern and confirm token ("delete") used elsewhere, and match.
- **Skeleton's structural a11y scaffold (AC #7 in 10.3a)**: already pins `role="log"`, `aria-live="polite"`, `aria-busy` on streaming bubbles, `<form>` + `<textarea>` + visible `<label>` for the composer, Enter/Shift+Enter split, Ctrl/Cmd+Enter alternate, initial focus = composer, tab order. 10.3b's **Full AA Pass** extends this with color/contrast per state, focus-trap for dialogs, screen-reader announcement semantics for transient surfaces (toasts, countdowns), and `prefers-reduced-motion` coverage for new animations. It does not reorder or redefine the scaffold.

### Git Intelligence

Recent commits (last 5):

```
18c22d8 Story 10.3a: Chat UX Skeleton (IA + Conversation/Composer/Streaming/Citations Layout)
267eb7b Story 10.2: AWS Bedrock Guardrails Configuration
128e634 Story 10.1b: 'chat_sessions' / 'chat_messages' Schema + Cascade Delete
8e815dc Story 10.1a: 'chat_processing' Consent (separate from 'ai_processing')
5f4f567 Story 9.7: Bedrock IAM + Observability Plumbing
```

- The four most recent Epic-10 commits (10.1a / 10.1b / 10.2 / 10.3a) establish the pattern this story extends: consent backend → schema → Guardrails infra → UX skeleton → UX states. Each is a single-concern commit touching minimal file sets. 10.3b is expected to land as a doc-only commit with no code changes, same shape as 10.3a's commit (only `_bmad-output/planning-artifacts/ux-design-specification.md` + the story file itself + `VERSION`).
- Branch state at story creation: `main`, clean.
- The 10.3a commit (`18c22d8`) touched `ux-design-specification.md` with a ~236-line addition (skeleton). 10.3b is expected to be a similar-order addition (copy table + flows + new subsections push the net-add higher; ballpark 300–400 lines, dominated by the EN/UA copy table).

### Latest Tech Information

- **`navigator.clipboard.writeText`**: stable baseline across evergreen browsers; requires secure context (HTTPS) which the app already mandates. No library needed; the spec's correlation-ID copy affordance is a direct platform call — 10.7 does not need a clipboard library.
- **ICU MessageFormat for UA pluralization**: the existing i18n setup under `frontend/src/i18n/` already uses ICU-style plural rules (check `_common.json` usage). 10.3b's copy-table annotations cite the existing posture; no new formatter library owed.
- **WAI-ARIA 1.2 / 1.3 — `role="status"`** for the deletion toast: stable, broadly supported by modern screen readers (JAWS 2022+, NVDA 2022.x+, VoiceOver iOS 15+, TalkBack Android 12+). No version pin needed.
- **`prefers-reduced-motion` media query**: platform-stable; already used elsewhere in the app per [ux-design-specification.md §Accessibility Strategy — Accessibility Development](../planning-artifacts/ux-design-specification.md). 10.3b extends coverage to new animation surfaces; no new platform capability required.
- **Mermaid `stateDiagram`**: renders correctly in GitHub markdown, VS Code preview, and pandoc exports; same support profile as `sequenceDiagram` (10.3a used `sequenceDiagram` without issue). No escaping caveats beyond standard markdown rules.

## Project Context Reference

- Planning artifacts: [epics.md §Epic 10 Story 10.3b](../planning-artifacts/epics.md), [architecture.md §AI Safety Architecture](../planning-artifacts/architecture.md) (covers §API Pattern — Chat Streaming, §Consent Drift Policy, §Memory & Session Bounds, §Rate Limits, §Canary Detection, §Chat Agent Component, §Data Model Additions), [ux-design-specification.md §Chat-with-Finances (Epic 10) — Skeleton Spec (Story 10.3a)](../planning-artifacts/ux-design-specification.md) (the skeleton this story layers on).
- Sibling Epic 10 stories: **10.1a/b** (consent + schema — shipped, consumed by AC #3), **10.2** (Guardrails — shipped, consumed as the source of `reason=guardrail_blocked`), **10.3a** (skeleton — shipped, the structural scaffold this states spec layers on), **10.4a** (AgentCore session handler — parallel; no UX dependency), **10.4b** (system-prompt hardening + canaries — parallel; its `CHAT_REFUSED.reason=prompt_leak_detected` surface is consumed by AC #2), **10.4c** (tool manifest — parallel), **10.5** (chat streaming API + SSE — parallel; 10.3b's refusal copy is authored against its envelope contract), **10.6a** (grounding enforcement — parallel; its `CHAT_REFUSED.reason=ungrounded` surface is consumed by AC #2), **10.6b** (citation payload API — parallel; its citation-detail content is *still* delegated downstream per AC #1's resolution matrix), **10.7** (Chat UI — the direct downstream consumer of 10.3a + 10.3b), **10.10** (chat history + deletion — its backend cascade is consumed by AC #4's per-session delete Undo conditional), **10.11** (abuse + rate-limit — its envelope values are consumed by AC #5 without duplication).
- Cross-references: [`_bmad-output/planning-artifacts/ux-design-specification.md`](../planning-artifacts/ux-design-specification.md) (primary edit target), [`_bmad-output/planning-artifacts/design-backlog.md`](../planning-artifacts/design-backlog.md) (sweep target), [`docs/tech-debt.md`](../../docs/tech-debt.md) (sweep target — expected no new entries), [`frontend/src/i18n/`](../../frontend/src/i18n/) (i18n namespace home, NOT edited by this story), [`_bmad-output/implementation-artifacts/5-5-delete-all-my-data.md`](./5-5-delete-all-my-data.md) (type-to-confirm pattern precedent).
- Sprint status: this story is `backlog` → set to `ready-for-dev` on file save.

## Dev Agent Record

### Agent Model Used

claude-opus-4-7 (1M context)

### Debug Log References

- **Session-summarization decision (Task 6 / AC #6):** **Option A (silent)** pinned. Rationale: summarization is a memory-window optimization, not a content operation; the backend does not support an "expand summary" action, so surfacing it would invite anxiety without payoff.
- **Refusal-variant icon-slot (Task 2 / AC #2):** `info` pinned as default; `alert` called out as an acceptable render-time swap. Rationale: a refusal is *information about why the turn didn't complete*, not a user-caused error — `info` matches the semantic; leaving `alert` open lets 10.7 avoid a visual collision if a true info banner lands adjacent.
- **Design-backlog sweep (Task 13.2 / AC #13):** `grep -n '10\.3\|chat\|Chat' _bmad-output/planning-artifacts/design-backlog.md` → **zero matches**. Register contains only DS-1 / DS-2 / DS-3, none chat-adjacent. No-op — no entries added, none closed.
- **Tech-debt sweep (Task 13.1 / AC #12):** `grep -n '10\.3b\|TD-.*10\.3' docs/tech-debt.md` → **zero matches**. No new TD entries opened. AC #12's defensive exception (pre-existing design-system token gap) did not fire — refusal variant reuses the existing `info` slot and neutral surface; destructive buttons reuse the existing destructive-action token.
- **UA copy-table spot-check (Task 8.6):** the `chat.ratelimit.activeCount` ICU `{count, plural, one / few / many / other}` shape was verified against `frontend/messages/uk.json` patterns `transactionCount` (L108), `duplicatesSkipped` (L109), `completionSummary.newCount` (L148), `insightCount` (L199), `rejectedRowsTitle` (L201). Posture matches — no new formatter / library owed.
- **Version bump policy (Step 9):** docs-only story with no new user-facing functionality → **PATCH** bump per [docs/versioning.md](../../docs/versioning.md). Before: `1.42.1`. After: `1.42.2`.
- **Deviation — Story 5.5 pattern reference (AC #4):** AC #4 directs delete-all to "match the pattern from Story 5.5" and to use a type-to-confirm input with the literal word "delete". Review of Story 5.5 shows it shipped a single AlertDialog + destructive confirm, *not* type-to-confirm. Resolution: the AC text is prescriptive (type-to-confirm + literal "delete"), so the spec authors type-to-confirm with an inline note acknowledging the divergence. The friction bump is justified by the catastrophic blast radius of "all chats". Recorded in-line in the spec's _History & Deletion Flows → Flow 2 — Delete all_.
- **Verification commands (Task 14 / Step 7):**
  - `grep -n "Chat-with-Finances" ux-design-specification.md` → 2 `##` matches (L1564 skeleton, L1797 states) + 1 in-body cross-reference.
  - `grep -nE "^## |^### Out of scope for initial chat UX" ux-design-specification.md | tail -5` → `### Out of scope for initial chat UX` is the last `###` (L2198), following `### Frontend Implementation Handoff Extensions` (L2185). Tail preserved.
  - `wc -l` UX spec: 1798 → 2201 (**net +403 lines**; within the 300–400 ballpark projected by the story).

### Completion Notes List

- All 14 ACs landed via a single append to `_bmad-output/planning-artifacts/ux-design-specification.md`: the new `## Chat-with-Finances (Epic 10) — States Spec (Story 10.3b)` peer-level section inserted between the 10.3a skeleton's `### Frontend Implementation Handoff` subsection and the `### Out of scope for initial chat UX` tail block. The skeleton section was untouched; the Out-of-scope tail preserved verbatim.
- **Scope Resolution Matrix** (AC #11) resolves every one of the 9 items enumerated in 10.3a's "Reserved for Story 10.3b" subsection. Citation *content* (the only item not resolved inline) is explicitly delegated to 10.6b (payload) + 10.7 (render) with one-line rationale.
- **Copy Reference Table** (AC #8) authored 44 rows (within the AC's ±3 of ~42). ICU plural posture verified against `frontend/messages/uk.json`. Forbidden-terms bullet listed at the top of the notes column (Guardrails, grounding, canary, jailbreak, prompt injection).
- **Wireframes + flows** (AC #9): three mandatory + one optional artifact delivered — Mermaid `sequenceDiagram` for the refusal branch (all 4 reasons), Mermaid `stateDiagram-v2` for the consent state machine, ASCII mock of the refusal variant in the conversation pane, ASCII mock of the rate-limit cooldown composer.
- **No new design-system tokens** introduced; **no new API endpoints** owed; **no library / state-management / streaming-client / clipboard-library** prescription (matching 10.3a's Frontend Implementation Handoff posture).
- **Sweeps** (AC #12, #13) both returned zero matches — no TD entries opened, no design-backlog entries closed.
- **Code-review fixes applied (2026-04-24):** (M1) AC #11 wording corrected from "12 items" to "9 items" to match 10.3a's actual Reserved list cardinality; (M2) UA copy for `chat.refusal.reference.label` changed from "Код: {shortId}" to "ID: {shortId}" — "Код" reads as numeric/source-code in UA and loses the correlation-ID semantic; (M3) added new copy-table row `chat.refusal.rateLimited.fallbackTryLater` for the null-`retry_after_seconds` fallback copy called out in AC #2 but previously missing from the table.

### File List

- `_bmad-output/planning-artifacts/ux-design-specification.md` (modified) — appended `## Chat-with-Finances (Epic 10) — States Spec (Story 10.3b)` section (net +403 lines, L1797–L2196) between the 10.3a skeleton's Frontend Implementation Handoff subsection and the Out-of-scope tail block; tail preserved verbatim as the final subsection of the combined chat UX spec.
- `_bmad-output/implementation-artifacts/10-3b-chat-ux-states-spec.md` (modified) — this story file: all task/subtask checkboxes marked `[x]`, Dev Agent Record populated (Debug Log, Completion Notes, File List), Change Log updated, Status → `review`.
- `_bmad-output/implementation-artifacts/sprint-status.yaml` (modified) — `10-3b-chat-ux-states-spec: ready-for-dev → in-progress → review`.
- `VERSION` (modified) — `1.42.1 → 1.42.2` (PATCH bump per docs-only policy).
- `docs/tech-debt.md` (modified, post-review) — added [TD-093](../../docs/tech-debt.md) for the UA-plural-agreement sweep surfaced by L3; does **not** violate AC #12 because the entry documents a **pre-existing** gap in `frontend/messages/uk.json`, not a new debt introduced by this story (the AC #12 defensive exception for pre-existing gaps explicitly covers this case).

## Code Review

Adversarial code review pass on 2026-04-24 (post-implementation, pre-done). 0 High, 3 Medium, 4 Low findings. All Medium fixed in the spec; Lows routed per the tech-debt promotion protocol.

**Fixed in this review (M1–M3):**

- **M1** — AC #11 text claimed 10.3a reserved *"12 items"* but the actual Reserved list at [ux-design-specification.md §Reserved for Story 10.3b](../planning-artifacts/ux-design-specification.md) has 9 bullets (and AC #1 of this same story correctly says "nine"). Corrected to "9 items".
- **M2** — UA copy for `chat.refusal.reference.label` was "Код: {shortId}". "Код" reads as *code* (numeric/source) in UA and loses the support/correlation-ID semantic. Changed to "ID: {shortId}" (naturalized UA loan, well-understood in tech UI; "Ідентифікатор" overruns the tight-slot +30% budget).
- **M3** — The `retry_after_seconds = null` fallback copy mandated by AC #2 had no row in the Copy Reference Table. Added `chat.refusal.rateLimited.fallbackTryLater` (EN + UA).

**Deferred / routed:**

- **L1** — Post-cooldown soft-prompt "[Send →]" button label at [ux-design-specification.md L1904](../planning-artifacts/ux-design-specification.md) has no dedicated i18n key. Story-local: 10.7 should reuse the composer's existing Send label; if it diverges at implementation time, 10.7 files the new key. No TD entry.
- **L2** — Forward-reference links to `10-5-*.md`, `10-6b-*.md`, `10-7-*.md`, `10-9-*.md`, `10-10-*.md`, `10-11-*.md` are dead today (those story files don't exist yet). Story-local: the links resolve as those stories land in their epic order. Not real debt.
- **L3 → [TD-093](../../docs/tech-debt.md)** — UA plural forms mix adjective/noun case in the `few {…}` branch (`chat.ratelimit.activeCount` at [ux-design-specification.md L2039](../planning-artifacts/ux-design-specification.md), matching the existing `completionSummary` posture at [frontend/messages/uk.json:148](../../frontend/messages/uk.json#L148)). Promoted because it spans the existing codebase, not just this spec — needs a coordinated UA-native sweep.
- **L4** — Architecture cross-refs (`[architecture.md §…](./architecture.md)`) cite section names in prose but carry no `#anchor` fragment in the `href`. Story-local: polish nit; 10.7 spec-reader UX would benefit from GitHub-slugified anchors on the next edit pass — not blocking.

## Change Log

| Date | Change | Version |
|------|--------|---------|
| 2026-04-24 | Story 10.3b drafted (ready-for-dev): Chat UX States Spec — refusals, consent, deletion, rate-limit, session-summarization decision, full WCAG 2.1 AA pass, UA + EN copy edge cases. | — |
| 2026-04-24 | Story 10.3b implemented (review): States Spec section appended to `ux-design-specification.md` (net +403 lines); all 14 ACs resolved; Scope Resolution Matrix covers every 10.3a reservation; Option A (silent summarization) pinned; refusal icon slot pinned to `info`. | 1.42.1 → 1.42.2 |
| 2026-04-24 | Version bumped from 1.42.1 to 1.42.2 per docs-only story-completion policy. | 1.42.2 |
