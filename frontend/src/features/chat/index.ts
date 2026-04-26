// Story 10.7 — Chat UI feature surface.
//
// Scope boundaries (per story doc — do NOT silently expand):
//   - No backend changes. Backend contracts (10.1a, 10.1b, 10.2, 10.4a/b/c,
//     10.5, 10.5a, 10.6a, 10.6b) are frozen; defects → TD entry.
//   - No new UX spec content. UX is fully specified by 10.3a/10.3b.
//   - No history/deletion mechanics — Story 10.10 owns the bulk-delete API,
//     undo grace-window, export. UI here renders entry points only.
//   - No rate-limit enforcement logic — Story 10.11 owns that. UI renders
//     refusal-variant copy/countdown only.
//   - No safety observability authorship — Story 10.9 owns metrics/alarms.
//   - No write-action UI; composer is text-only.
//   - No new design tokens.
//   - No SSE polyfill; modern browsers only.
//   - No dual-pane history reader on mobile; reuse existing drawer pattern.
//   - No feature-flag gate on the route; chat is not subscription-gated.
//   - No localization of citation `label` server-side — UA mapping for
//     CategoryCitation.code + ProfileFieldCitation.field lives in
//     `chat.citations.*` namespace; transaction/rag_doc labels render verbatim.
//   - No contract-version handling — the citation contract is additive;
//     unknown shapes log a warn and skip.

export { ChatScreen } from "./components/ChatScreen";
