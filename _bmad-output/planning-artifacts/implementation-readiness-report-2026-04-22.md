---
stepsCompleted:
  - step-01-document-discovery
  - step-02-prd-analysis
  - step-03-epic-coverage-validation
  - step-04-ux-alignment
  - step-05-epic-quality-review
  - step-06-final-assessment
overallReadiness: READY
assessor: Winston (Architect)
scope: Single story — 11-11-exclude-transfers-from-insight-generation
documentsInScope:
  - _bmad-output/planning-artifacts/prd.md
  - _bmad-output/planning-artifacts/architecture.md
  - _bmad-output/planning-artifacts/tech-spec-ingestion-categorization.md
  - _bmad-output/planning-artifacts/epics.md
  - _bmad-output/planning-artifacts/ux-design-specification.md
  - _bmad-output/implementation-artifacts/11-11-exclude-transfers-from-insight-generation.md
  - _bmad-output/implementation-artifacts/sprint-status.yaml
---

# Implementation Readiness Assessment Report

**Date:** 2026-04-22
**Project:** kopiika-ai
**Scope:** Story 11-11 — Exclude Transfers from Insight Generation

## Step 1 — Document Discovery

### Inventory
| Type | File | Status |
|---|---|---|
| PRD | `_bmad-output/planning-artifacts/prd.md` | present, single source |
| Architecture | `_bmad-output/planning-artifacts/architecture.md` | present, single source |
| Epic 11 Tech Spec | `_bmad-output/planning-artifacts/tech-spec-ingestion-categorization.md` | present, scoped |
| Epics & Stories | `_bmad-output/planning-artifacts/epics.md` | present, single source |
| UX | `_bmad-output/planning-artifacts/ux-design-specification.md` | present, single source |
| Story (under review) | `_bmad-output/implementation-artifacts/11-11-exclude-transfers-from-insight-generation.md` | drafted |
| Sprint tracker | `_bmad-output/implementation-artifacts/sprint-status.yaml` | 11-11 listed |

### Conflicts / Gaps
- No whole-vs-sharded duplicates.
- No missing required documents.
- Prior IR report (2026-04-19) exists and is unaffected.

## Step 2 — PRD Analysis (scoped)

**Scope note:** Per the requested single-story IR run, PRD extraction is filtered to requirements that bear on insight generation, the Education Agent, the Teaching Feed, and `transaction_kind` semantics. A full FR/NFR sweep is not performed — the last full sweep is captured in `implementation-readiness-report-2026-04-19.md` and remains authoritative for project-wide traceability.

### Functional Requirements — Directly In Scope for Story 11-11

| ID | Requirement (verbatim) | Relationship to Story 11-11 |
|---|---|---|
| FR10 | System can generate personalized financial education content based on categorized transaction data using RAG over a financial literacy knowledge base (Education Agent) | **Primary.** Story 11-11 constrains the *input* to this generator (spending-kind only) and adds a deterministic structural card when transfers dominate. No change to RAG behaviour. |
| FR11 | System can generate education content in the user's selected language (Ukrainian or English) | **Direct.** The 4 prompt templates (EN/UK × beginner/intermediate) all receive the new "no transfer-volume insights" instruction (AC #6); the deterministic structural card has EN + UK copy (Task 2.3). |
| FR14 | Users can view a card-based Teaching Feed displaying AI-generated financial insights | **Indirect.** Feed still renders the same way; a new `card_type='structuralCard'` is produced but rendered via the existing generic card path. |
| FR15 | Each insight card displays a headline fact with progressive disclosure education layers (headline → "why this matters" → deep-dive) | **Shape constraint.** The new structural card must honour this shape — Task 2.3 pre-renders `headline`, `key_metric`, `why_it_matters`, `deep_dive`. ✅ satisfied. |
| FR58 | System can score each insight or pattern finding by financial severity (critical / warning / info) based on UAH impact relative to the user's monthly income | **Shape constraint.** New structural card uses `severity='info'` — appropriate (contextual notice, not actionable alert). ✅ satisfied. |
| FR59 | Teaching Feed displays insight cards sorted by triage severity (critical first, then warning, then info); each card carries a severity badge with colour, icon, and text label | **Interaction.** Story 11-11 specifies final ordering `subscription + structural + llm` (Task 2.5). This is ordering *within* the generator, not a triage-severity re-sort on the client. Need to confirm the client's severity sort doesn't demote the `info`-severity structural card below other `info` LLM cards in an unexpected way — see Step 3 findings. |
| FR60 | System can generate subscription alert cards showing service name, monthly cost, billing frequency, and inactivity status | **Precedent.** `_build_subscription_cards` is the pattern the story mirrors for `_build_mostly_transfers_card`. ✅ aligned. |

### Functional Requirements — Indirectly Relevant
- **FR9** (Categorization Agent classifies transactions): Story 11-11 depends on `transaction_kind` being set by the categorizer (Story 11.2). Task 4 is a belt-and-braces verification that this plumbing holds end-to-end.
- **FR12** (process 200–500 transactions asynchronously): Task 2.6's short-circuit (skip LLM on all-non-spending input) is a small perf win within the 60s budget — no regression risk.

### Non-Functional Requirements — Directly In Scope

| Area | Target | Relationship |
|---|---|---|
| Performance — full pipeline < 60s for 200–500 txns | NFR Performance table | Task 2.6 short-circuits RAG + LLM when spending-only total is zero → strictly faster on degenerate inputs. ✅ neutral-to-positive. |
| Performance — Teaching Feed card render < 500ms | NFR Performance table | No render path change; new card uses existing generic renderer. ✅ no risk. |
| Reliability — Graceful degradation for Education Agent | NFR Reliability | Task 2.7 requires the exception handler to still emit subscription + structural cards on LLM failure — a positive enhancement to existing graceful-degradation guarantees. ✅ improved. |
| Accessibility — severity conveyed through icon + text, not colour | NFR Accessibility | Structural card uses `severity='info'` and a text headline; relies on existing client-side rendering for `info` severity. ✅ neutral. |

### Requirements NOT Explicitly Covered by PRD
- **"Transfers must be excluded from spending-insight generation"** is not an explicit FR. It's an implicit quality requirement of FR10 that was exposed by Epic-11 UAT. This is normal for a quality-fix story; Epic 11 Tech Spec's `transaction_kind`-first-class decision (ADR-0001) is the upstream architectural commitment that makes this fix the natural next step.
- **Localization of deterministic card copy** (Ukrainian translation in Task 2.3) is not called out as a distinct FR but is required by FR11's "education content in the user's selected language" — the story correctly includes both EN and UK copy.

### PRD Completeness Assessment (for Story 11-11 only)
- **Coverage:** Adequate. The story draws authority from FR10, FR11, FR14, FR15, FR58, FR59, FR60 and the Story 11.2 precedent — sufficient to justify the work without a new FR.
- **Gap flag:** If the team wants explicit PRD traceability for "insight-quality guardrails against tautological cards", a lightweight addendum could be added as `FR10a: System excludes non-spending transaction kinds (transfer, income, savings) from aggregated inputs to the Education Agent; when non-spending kinds dominate activity, system emits a single deterministic structural card acknowledging this context.` This is optional — the story is executable without it.
- **Ambiguity risk:** Low. AC #1–#9 are concrete, testable, and fully specify inputs/outputs including edge cases (empty spending, all-transfer, default-to-spending on missing kind).

## Step 3 — Epic Coverage Validation (scoped)

### Coverage Matrix for Story 11-11

| FR | PRD Requirement (paraphrased) | Epic Coverage in `epics.md` | Story 11-11 Contribution | Status |
|---|---|---|---|---|
| FR10 | Education Agent generates personalized content via RAG | Epic 3 (primary owner) | Constrains input set; adds structural card | ✓ Covered upstream; enhanced |
| FR11 | Education content in UK/EN | Epic 3 | Adds EN + UK copy for structural card; updates all 4 templates | ✓ Covered upstream; enhanced |
| FR14 | Card-based Teaching Feed | Epic 3 | No structural change | ✓ Covered |
| FR15 | Progressive-disclosure shape | Epic 3 | Structural card honours headline/why/deep_dive shape | ✓ Covered |
| FR58 | Severity scoring | Epic 8 (triage) | Structural card uses `severity='info'` | ✓ Covered |
| FR59 | Severity-sorted Teaching Feed | Epic 3/8 | Story fixes generator-side order; client severity sort unchanged | ⚠️ See flag below |
| FR60 | Subscription alert cards | Epic 8 | Pattern mirrored for structural card | ✓ Covered |
| FR73 | `transaction_kind` first-class (ADR-0001) | Epic 11 / Story 11.2 | Consumes this field as source of truth | ✓ Covered (upstream done) |

### Epic Placement Assessment

**Question:** Is Story 11-11 correctly placed in Epic 11 (Ingestion & Categorization Hardening) rather than Epic 3 (AI-Powered Financial Insights)?

**Finding:** Defensible, with documented trade-off.
- **Arguments for Epic 11 (the chosen home):** The story's value proposition is "honour `transaction_kind` downstream" — the same thesis as Story 4.9. Epic 11's tech spec (§11 Out of Scope) explicitly notes *"Multi-leg transfer detection … is an insight-layer concern"*, pre-authorizing insight-layer work derived from Epic 11's data model. Epic 3's retrospective is closed, so adding a follow-up there would require re-opening.
- **Arguments for Epic 3 (the code's physical home):** All changes land in `backend/app/agents/education/` which is FR10's implementation locus. Story 3.9 ("Key Metric Prompt Refinement") set a precedent for post-retrospective quality fixes within Epic 3.
- **Resolution:** Epic 11 placement is consistent with Story 4.9's pattern (consumer-side wiring to `transaction_kind` filed under the producing epic). Story file's Context section names this trade-off explicitly. ✓ Accept.

### Documentation Drift Findings (Not Blockers)

1. **Story 11.11 absent from `epics.md`.** `epics.md` ends Epic 11 at Story 11.9 (line 2469); Stories 11.10 (already `done` per sprint tracker) and 11.11 (the subject of this IR) are not backfilled. Impact: low — sprint tracker + story file are authoritative for dev; epics.md is planning-artifact drift. Recommendation: batch-backfill 11.10 + 11.11 into `epics.md` during Epic 11 retrospective. Flag as **DOC-DRIFT-01**.

2. **Tech spec §10 cross-reference numbering stale.** `tech-spec-ingestion-categorization.md` line 526 still lists "11.10 Deprecate `generic.py`" while sprint-status has re-purposed 11.10 to "counterparty-aware categorization". Story 11.11 is not referenced in the spec's story-to-section table. Impact: low — tech spec is reference, not gate. Recommendation: update during Epic 11 retrospective. Flag as **DOC-DRIFT-02**.

3. **FR10a candidate addendum.** As noted in Step 2, a small PRD addendum capturing "insight-quality guardrails against tautological non-spending cards" would give explicit traceability for Story 11-11. Optional; the story is executable without it.

### FR59 Interaction Flag (to verify during dev-story)

The client-side Teaching Feed sorts by triage severity (FR59). Story 11-11's generator-side ordering is `subscription + structural + llm`, but the structural card is `severity='info'`. If the client re-sorts on severity, an `info` structural card could be pushed below `critical`/`warning` LLM cards, defeating the "this card explains the context of what follows" design intent in Dev Notes.

**Recommendation:** Either (a) during Task 2 implementation, confirm the client preserves generator order within the same severity, or (b) add a small `sort_key` / `pinned` flag to force the structural card immediately after subscription alerts regardless of severity. Not a blocker for story start — add as an implementation-time check in Completion Notes.

### Coverage Statistics (for Story 11-11 scope)

- PRD FRs touched by story: **8** (FR10, FR11, FR14, FR15, FR58, FR59, FR60, FR73)
- FRs adequately covered upstream + enhanced here: **7**
- FRs with interaction to verify during dev: **1** (FR59)
- FRs missing coverage: **0**
- Optional PRD addendum: **1** (FR10a — not required)

## Step 4 — UX Alignment (scoped)

### UX Document Status
**Found:** `ux-design-specification.md` (102 KB, 2026-04-19). No sharded version.

### UX ↔ Story 11-11 Touchpoints

| UX Concern | Spec Reference | Story 11-11 Treatment | Alignment |
|---|---|---|---|
| Card stack, swipe navigation, progressive disclosure | UX §Core Interaction Model (lines ~646–681) | New structural card is rendered by the same generic card component (Story `Project Structure Notes`) | ✓ Aligned |
| Severity visual language — coral / amber / sage for high / medium / low + text labels ("High Priority / Worth Checking / Looking Good") | UX lines ~495, ~441, ~611 | Structural card uses `severity='info'` | ⚠️ **Info-tier mapping gap** — see Finding 1 below |
| Triage ordering ("highest-impact first"); first card is always highest-impact | UX lines ~349, ~673, ~791 | Final order `subscription + structural + llm`; structural (`info`) sits between subscription (`critical`/`warning`) and LLM cards of mixed severity | ⚠️ **Ordering tension** — see Finding 2 below |
| Motivate, never shame | UX lines ~117, ~232 | "Your statement is mostly transfers" + "Insights below focus only on the remaining spending" is informational, non-judgmental | ✓ Aligned |
| Localization tone (warm, informative, not clinical) | UX §Copy voice + story `Localization block` | Story Dev Notes explicitly calls out matching `profile.healthScore.*` tone in UK copy | ✓ Aligned |
| Accessibility — severity via icon + text, not colour alone | UX §495, NFR Accessibility | Structural card has headline + `key_metric` text + `severity` tier text label → will inherit existing accessible badge rendering | ✓ Aligned (provided info-tier badge exists) |
| New `card_type='structuralCard'` value vs. existing `subscriptionAlert` / `spendingInsight` | Architecture line 318 (`card_type varchar(50)`) | Persists cleanly — no schema change (story §Project Structure Notes) | ✓ Aligned |

### Findings

**Finding 1 — Severity tier mapping for `info` is ambiguous in UX spec.**
The UX spec defines three tiers (coral/amber/sage) with labels ("High Priority / Worth Checking / Looking Good"). The existing codebase uses `severity` values `critical`, `warning`, `info` (per FR58). Mapping assumed: `critical→coral`, `warning→amber`, `info→sage`. But "Looking Good" as a label on a "Your statement is mostly transfers" card is semantically wrong — it's a *contextual notice*, not positive feedback.
- **Impact:** Low-to-medium. The structural card will render with the existing sage/"Looking Good" treatment, which may confuse users.
- **Recommendation:** During dev-story, verify the current badge label for `info` in the React component. If it reads "Looking Good" or equivalent positive framing, either (a) add a tiny per-card label override (`severity_label` field) OR (b) accept the mismatch for MVP and log a UX follow-up. Either is acceptable; do NOT expand Story 11-11 scope to add a fourth severity tier. Flag as **UX-FLAG-01**.

**Finding 2 — Ordering tension with FR59 "severity-first" contract.**
UX emphasizes that the *first* card is always the highest-impact. Story 11-11 places an `info`-severity structural card before potentially higher-severity LLM cards (e.g. a `warning`-level subscription-creep insight). This is defensible — structural cards *explain the context of what follows*, and the Dev Notes articulate the rationale — but it creates an ordering contract that the client's severity-sort must respect.
- **Impact:** Medium. If the client re-sorts by `severity` alone, the structural card gets demoted and the "frame the feed" intent is lost.
- **Recommendation:** This is the same point already flagged in Step 3 (FR59 Interaction Flag). Two viable fixes:
  1. Add a small `pinned: bool` or `sort_priority: int` field that the client respects, keeping subscription + structural cards above severity-sorted LLM cards (cleanest, low effort).
  2. Keep `severity='info'` but document the client-side sort stability guarantee so generator order wins within equal severities, and accept that a `critical` LLM card may legitimately jump above the structural card (reasonable — the user benefits from seeing urgent LLM cards first).
  - **Suggested resolution:** Option 2 is simpler and arguably more correct — if an LLM produces a `critical` insight, the user should see it above a contextual notice. The structural card is still always *before* other `info` cards (its own severity tier), which preserves the "frame the remainder" intent for the typical case. Record the choice in Completion Notes; no story-scope expansion needed. Flag as **UX-FLAG-02**.

**Finding 3 — UX spec does not enumerate `structuralCard` as a card type.**
The spec lists `InsightCard`, `TriageBadge`, and references `subscriptionAlert` in architecture. `structuralCard` is new vocabulary introduced by this story.
- **Impact:** Low. The shape (`headline` / `key_metric` / `why_it_matters` / `deep_dive`) is identical to `InsightCard`, so the generic renderer works.
- **Recommendation:** Add a one-line note to the UX spec during Epic 11 retro: *"`structuralCard` — contextual notice emitted by deterministic rules (not LLM); renders with InsightCard component, `info` severity."* Not a blocker. Part of **DOC-DRIFT-01**.

### UX ↔ Architecture Alignment
Architecture supports the change with no friction: `card_type` is already `varchar(50)`, generic REST response union handles arbitrary `type` values (architecture line 497, 751), no migration needed, no new frontend component required. ✓

### Warnings
- **UX-FLAG-01:** `info`-tier badge label may read as positive framing ("Looking Good") and mismatch the "mostly transfers" contextual tone. Verify during dev-story.
- **UX-FLAG-02:** Generator-side ordering (`subscription + structural + llm`) must be reconciled with the client's severity sort. Resolve via documented sort-stability guarantee OR a small pin/priority flag.
- Neither warning blocks story start.

## Step 5 — Epic Quality Review (scoped to Story 11-11)

### Story Structure Compliance Checklist

| Check | Result | Notes |
|---|---|---|
| User-centric title (describes outcome, not task) | ✓ | "Exclude transfers (and other non-spending kinds) from insight generation" — reads as a user-visible quality outcome |
| User-value statement (As a… I want… so that…) | ✓ | Grounded in the real UAT regression; `so that` clearly states user benefit |
| Context section with root-cause and rationale | ✓ | Names exact file:line of the bug and upstream dependency (Story 11.2) |
| Acceptance Criteria in Given/When/Then BDD form | ✓ | 9 ACs, all BDD-formatted |
| Each AC is testable | ✓ | See AC-by-AC table below |
| Tasks mapped to ACs | ✓ | Each task cites AC numbers; no orphan tasks |
| File-level references with line numbers | ✓ | Links to [`node.py:20-52`], [`node.py:84-122`], [`node.py:125-226`], [`prompts.py`], [`state.py:9`], prior stories |
| Story is independently completable within its epic | ✓ | Depends only on already-`done` Stories 11.2 and 11.3 |
| No forward dependencies (no "wait for future story") | ✓ | No references to unbuilt work |
| Change blast radius documented | ✓ | "Two files: `node.py`, `prompts.py`. No schema, no migration, no API, no FE." |
| Dev Notes justify non-obvious decisions | ✓ | Threshold choice (70%), kind-filtering vs. sign-filtering, ordering rationale, localization block |

### Acceptance-Criterion Quality (AC-by-AC)

| AC | Testable? | Specificity | Comment |
|---|---|---|---|
| #1 — kind filter in `_build_spending_summary` | ✓ | High | Explicit "only entries with `transaction_kind == 'spending'` contribute" |
| #2 — excluded-kinds footer format | ✓ | High | Deterministic ordering `income → savings → transfer`; zero-totals omitted; whole block omitted when empty |
| #3 — mostly-transfers card (>70%) | ✓ | High | Card shape, severity, category, card_type, ordering (after subscription, before LLM) all specified |
| #4 — LLM still runs on spending-only summary | ✓ | High | Negative AC — allows LLM to return zero cards legitimately |
| #5 — no structural card at ≤70% | ✓ | High | Negative threshold AC; paired with AC #3 for strict `>` |
| #6 — prompt updates in all 4 templates | ✓ | High | Exact EN + UK wording provided |
| #7 — `transaction_kind` is the source of truth | ✓ | High | Explicitly forbids inference from category/sign/MCC; defines default behaviour for missing key |
| #8 — empty or all-non-spending input | ✓ | High | Crash-safety + LLM short-circuit both specified |
| #9 — regression fixture assertion | ✓ | High | Integration test with keyword-absence assertion ("no card except structural may contain the word 'transfer'/'переказ'") |

**Verdict:** ACs are exemplary — concrete, enumerated, testable, and cover both happy path and edge cases (empty, all-non-spending, legacy-caller-missing-kind, exact-threshold boundary).

### Task Sizing & Ordering

- **9 tasks**, each small (1–3 bullets of sub-work). Total story fits comfortably in a single dev-story session.
- Task ordering is sensible: helpers first (T1, T2), then prompts (T3), then plumbing verification (T4), then tests (T5–T7), then regression fix-ups (T8), then tracker update (T9).
- **Test coverage strategy is sound:** unit tests for each new helper + separate integration test for the 97%-transfer regression + a third test to verify the "no transfer keyword in LLM cards" assertion mechanism.

### Dependency Analysis

- **Upstream dependencies (all satisfied):**
  - Story 11.2 (`transaction_kind` schema + categorization output) — `done`
  - Story 11.3 (enriched prompt emits `transaction_kind`) — `done`
- **No forward dependencies.**
- **No database/migration work required.**
- **No API changes.** No frontend changes required (generic card renderer handles `structuralCard`; verify during dev).

### Findings by Severity

#### 🔴 Critical Violations
- **None.**

#### 🟠 Major Issues
- **None.**

#### 🟡 Minor Concerns

1. **New `card_type='structuralCard'` vocabulary introduced without a central definition.** This value is not enumerated in architecture.md's card-type list nor UX spec. The story's Project Structure Notes acknowledges this and commits to a 1-line spot-check during dev, which is proportionate. Recommendation: add enum/union documentation during Epic 11 retro. Tracked as part of **DOC-DRIFT-01**.

2. **Severity-tier label mismatch (UX-FLAG-01 from Step 4).** `severity='info'` is the correct code-level value but carries UX semantics ("Looking Good" / sage) that don't fit a neutral contextual notice. Proportionate mitigation noted in Step 4. Not a story-scope change.

3. **Generator-side ordering vs. client severity sort (UX-FLAG-02 from Step 4).** Already covered; resolution recommended in Completion Notes.

4. **Task 4 is not a code-change task (belt-and-braces verification only).** Could be a sub-bullet under Task 1 rather than its own task. Cosmetic; does not affect executability.

5. **Localization decisiveness (cosmetic).** Task 1.6's "Number of transactions (analyzed): N" vs. keeping the existing label is left as a judgment call for the dev — fine, the story explicitly says to document the choice in Completion Notes.

### Best Practices Compliance
- [x] Story delivers user value (feed quality, no tautological cards)
- [x] Story is independently completable within its epic
- [x] No forward dependencies
- [x] Database tables: N/A (no schema work)
- [x] Clear, testable acceptance criteria
- [x] Traceability to FRs maintained (FR10, FR11, FR14, FR15, FR58, FR59, FR60, FR73)

## Summary and Recommendations

### Overall Readiness Status: **READY**

Story 11-11 is ready to hand to a dev-story run without further planning work. The story file is well-structured, the ACs are concrete and testable, dependencies are satisfied, blast radius is small (two production files + one test file, no schema/migration/API/FE work), and the upstream architectural commitment (`transaction_kind` as first-class, ADR-0001) is already landed via Stories 11.2 and 11.3.

### Critical Issues Requiring Immediate Action
- **None.** No 🔴 Critical or 🟠 Major findings across any of the 5 review dimensions (PRD, Epic Coverage, UX, Architecture, Story Quality).

### Warnings to Resolve During Dev-Story (not blockers)

| ID | Finding | Where | Suggested Disposition |
|---|---|---|---|
| **UX-FLAG-01** | `severity='info'` may render with positive framing ("Looking Good" / sage) that doesn't fit a neutral contextual notice | Step 4 | Inspect the frontend badge label during dev; either add a per-card label override OR accept for MVP and log a UX follow-up. Do NOT expand Story 11-11 scope. |
| **UX-FLAG-02** | Generator-side order (`subscription + structural + llm`) can conflict with client severity-sort; structural (`info`) could be demoted below `critical` LLM cards | Steps 3 & 4 | Recommend accepting sort-stability within equal severities (Option 2 in Step 4) — a `critical` LLM card legitimately jumps ahead; structural stays above other `info` cards. Record choice in Completion Notes. |
| **DOC-DRIFT-01** | `epics.md` not backfilled with Stories 11.10 + 11.11 | Step 3 | Batch-fix during Epic 11 retrospective. |
| **DOC-DRIFT-02** | `tech-spec-ingestion-categorization.md` §10 cross-reference table has stale story numbering and no 11.11 entry | Step 3 | Batch-fix during Epic 11 retrospective. |
| **FR10a (optional)** | Insight-quality guardrails against tautological non-spending cards not explicitly in PRD | Step 2 | Optional. Story is executable without it. Add as a PRD v-next refinement if the team values explicit traceability. |

### Recommended Next Steps
1. **Hand off to dev-story** — the story is ready. No additional planning round needed.
2. **During implementation**, resolve UX-FLAG-01 and UX-FLAG-02 via Completion Notes as described above — both are ~15-minute decisions, not scope expansions.
3. **At Epic 11 retrospective**, batch-resolve DOC-DRIFT-01 and DOC-DRIFT-02 (single `epics.md` addendum + tech-spec table refresh covering Stories 11.10 + 11.11).
4. **Optional:** add FR10a to a future PRD update if the team wants explicit traceability for insight-quality guardrails; skip for MVP.

### Final Note
This scoped assessment found **5 non-blocking findings** across **3 categories** (UX rendering details, documentation drift, optional PRD addendum) and **zero critical or major issues**. Story 11-11 may proceed to implementation as-is. The findings above are useful polish items, not prerequisites.
