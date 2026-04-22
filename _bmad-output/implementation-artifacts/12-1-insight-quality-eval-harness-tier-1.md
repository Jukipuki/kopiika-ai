# Story 12.1: Insight-Quality Eval Harness — Tier 1 (Deterministic Assertions on Golden Fixtures)

Status: ready-for-dev

<!-- Drafted 2026-04-22 by Winston (Architect) following the user's request to open Epic 12.
     This is a lightweight draft. If the team prefers the full SM workflow shape
     (matching Story 11.11's depth), run validate-create-story before starting dev. -->

## Story

As a **backend engineer**,
I want a reproducible CI harness that runs `education_node` against a curated fixture set and asserts deterministic shape constraints on the emitted cards,
so that regressions in insight quality (like the 97%-transfers tautology that motivated Story 11.11) are caught before merge instead of via user UAT.

## Context

Coverage for insight-output quality is currently ad-hoc: a handful of happy-path unit tests in [backend/tests/agents/test_education.py](backend/tests/agents/test_education.py) plus three scenario tests added by Story 11.11. Upstream quality is covered by Story 11.1's categorization golden-set and Story 9.3's RAG retrieval eval — but neither composes into an insight-output contract. This story lays the foundation: a reusable, CI-gated harness that tests the *shape and structural constraints* of the emitted card stream.

Deliberately scoped to **tier 1 — deterministic rule-based assertions** (card counts, card_types present/absent, keyword presence/absence, severity distribution, crash-free execution). LLM-as-judge scoring on qualitative axes is a separate future story (12.2), gated on calibration (12.3). Keeping tier 1 deterministic means: fast CI runs (no LLM invocation in this harness — responses are stubbed/recorded), no judge-drift risk, and no per-run token cost. It catches the highest-value class of regressions (Story 11.11's whole class) without any of the ambiguity of qualitative scoring.

Epic 12 scope boundary applies: this harness does NOT cover RAG retrieval quality (Epic 9 Story 9.3), categorization accuracy (Story 11.1), or chat behaviour (Epic 10). It covers `education_node` output-shape only.

## Acceptance Criteria

1. **Given** a new directory `backend/tests/agents/education/eval/`, **When** the harness is added, **Then** it contains: a `fixtures/` subdirectory (JSON files), a `runner.py` module (invokes `education_node` with a fixture as input), an `assertions.py` module (DSL for fixture-level assertions), and a `test_eval.py` pytest entry point that parameterises over all fixtures.

2. **Given** any fixture JSON file, **When** loaded, **Then** it matches a documented schema with fields: `name` (str), `description` (str, one-line rationale), `locale` (`en`|`uk`), `transactions` (list[dict]), `categorized_transactions` (list[dict]), `subscriptions` (list[dict], may be empty), `llm_response` (str — the canned JSON the stubbed LLM returns for this fixture), `assertions` (dict — see AC #4). Missing required fields fail fixture loading with a clear error naming the fixture and missing field.

3. **Given** the harness runs, **When** `education_node` is invoked on a fixture, **Then** the LLM client is stubbed (monkeypatched or via a `FakeLLMClient` injected through a test fixture) to return the fixture's `llm_response` verbatim — no real LLM call is made in this harness. RAG retrieval is stubbed similarly to return a fixed empty-or-canned context.

4. **Given** a fixture's `assertions` block, **When** the runner evaluates it, **Then** the following DSL keys are supported (each optional; presence means "check this"):
   - `exact_card_count: int` — total cards returned must equal this
   - `card_count_range: [min, max]` — total cards within inclusive range
   - `card_types_present: [str]` — every listed `card_type` MUST appear at least once
   - `card_types_absent: [str]` — no card may carry a listed `card_type`
   - `keywords_absent_in_bodies: [str]` — no card's `headline`, `key_metric`, `why_it_matters`, or `deep_dive` may contain any listed substring (case-insensitive)
   - `keywords_present_in_headlines: [[str]]` — outer list is AND, inner list is OR; each outer group must match at least one card's headline via any inner alternative
   - `severity_min_counts: {critical?: int, warning?: int, info?: int}` — each listed severity must appear at least the specified count of times
   - `must_not_crash: bool` (default `true`) — runner catches exceptions; if `true` and the node raises, the fixture fails with the exception captured
   Unknown keys in the assertions block fail the fixture with a clear error listing valid keys.

5. **Given** the initial fixture set delivered with this story, **When** committed, **Then** at least **15** fixtures exist covering:
   - **1 regression** (`regression_11_11_mostly_transfers.json`) — migrates Story 11.11's 97%-transfers scenario; asserts exactly one `structuralCard` with `category='transfers'`, no card body contains "transfer"/"переказ"
   - **3 baseline** — normal spending mixes at small/medium/large volumes (EN × 2, UK × 1)
   - **2 edge** — empty `categorized_transactions`; all non-spending (100% transfers)
   - **2 subscription-heavy** — ≥3 subscriptions detected; asserts `subscriptionAlert` cards present, ordering before LLM cards
   - **2 all-income** — statements containing only income; asserts no "spending" framing leaks into cards
   - **2 single-transaction** — statements with exactly 1 txn (spending / transfer); asserts no crash, sensible minimal output
   - **2 adversarial** — malformed amount (string), unknown category; asserts `must_not_crash`
   - **1 literacy-beginner**, **1 literacy-intermediate** — same input data with different `user_profile.literacy_level`; asserts card counts within range for each (sanity check that adaptive depth doesn't collapse to zero)

6. **Given** the pytest entry point [backend/tests/agents/education/eval/test_eval.py](backend/tests/agents/education/eval/test_eval.py), **When** `pytest` runs, **Then** each fixture is a separately-reported parameterised test case (visible fixture name in pytest output) and the suite exits non-zero if any fixture's assertions fail.

7. **Given** the CI pipeline, **When** a PR touches any file under `backend/app/agents/education/` or `backend/app/agents/state.py`, **Then** the insight-eval harness runs and must pass before merge. Mirror the gating mechanism of Story 11.1's categorization golden-set harness — same CI job style, same merge-block behaviour.

8. **Given** a developer adds or modifies a fixture, **When** they run `pytest backend/tests/agents/education/eval/`, **Then** the run completes in **under 10 seconds** total (all fixtures combined). Rationale: deterministic, no LLM calls, no I/O — must stay fast enough to run on every save during development.

9. **Given** the Story 11.11 scenario tests in [backend/tests/agents/test_education.py](backend/tests/agents/test_education.py) (`test_education_node_mostly_transfers_*`, `test_education_node_moderate_transfers_*`, `test_education_node_transfer_keyword_not_in_llm_cards`), **When** Story 12.1 lands, **Then** these tests are either (a) migrated into the harness as fixtures with equivalent assertions, OR (b) left in place as unit tests and the harness adds **independent** coverage of the same scenarios via new fixtures. The developer picks which; document the choice in Completion Notes. Either way, the 97%-transfers assertion exists in at least one of the two test surfaces.

10. **Given** the harness is complete, **When** a new team member needs to add a fixture, **Then** [backend/tests/agents/education/eval/README.md](backend/tests/agents/education/eval/README.md) documents: (i) fixture JSON schema with every field explained, (ii) the assertions DSL with one example per key, (iii) step-by-step "how to add a fixture", (iv) an explicit note that this is **tier 1 deterministic** and does NOT measure qualitative insight quality (Story 12.2 owns that), (v) a note about how to update the stubbed `llm_response` when prompt templates change.

## Tasks / Subtasks

- [ ] **Task 1**: Scaffold directory, runner, assertion DSL (AC #1, #2, #4)
  - [ ] 1.1 Create `backend/tests/agents/education/eval/` with `__init__.py`, `runner.py`, `assertions.py`, `fixtures/` subdir
  - [ ] 1.2 Implement `load_fixture(path: Path) -> Fixture` with schema validation
  - [ ] 1.3 Implement each assertion helper as a pure function; aggregate errors rather than short-circuiting (so one failing fixture shows all its violations at once)

- [ ] **Task 2**: LLM + RAG stubbing (AC #3)
  - [ ] 2.1 Add a `FakeLLMClient` with a `.invoke(prompt) -> str` method that returns the fixture's canned `llm_response`
  - [ ] 2.2 Patch `app.agents.llm.get_llm_client` and `get_fallback_llm_client` within the harness's pytest fixture scope
  - [ ] 2.3 Stub `app.rag.retriever.retrieve_relevant_docs` to return `[]` (empty context) unless a fixture opts into a canned context via an optional `rag_context` field — keep this opt-in to keep default fixtures small

- [ ] **Task 3**: Initial fixture set (AC #5)
  - [ ] 3.1 Write `regression_11_11_mostly_transfers.json` mirroring Story 11.11's AC #9 scenario; this is the canary fixture
  - [ ] 3.2 Write 3 baseline + 2 edge + 2 subscription + 2 all-income + 2 single-txn + 2 adversarial + 2 literacy fixtures = 14; add one more baseline for 15 total
  - [ ] 3.3 For each fixture, record the canned `llm_response` by running the real pipeline once locally (seed fixed), capturing the raw LLM output, and pasting it verbatim. Document this recording step in the README (Task 6)

- [ ] **Task 4**: Pytest parameterisation + speed budget (AC #6, #8)
  - [ ] 4.1 Parameterise the single test function over all fixture files using `pytest.mark.parametrize` + a `pytest_generate_tests` hook for clean fixture-name reporting
  - [ ] 4.2 Verify full-suite run stays under 10 seconds locally; if not, profile and remove waste (likely suspects: redundant imports, real RAG calls slipping through)

- [ ] **Task 5**: CI gate wiring (AC #7)
  - [ ] 5.1 Add the new test path to the existing CI config alongside Story 11.1's categorization harness (same workflow file; same "required check" classification in branch protection)
  - [ ] 5.2 Add path-filter so the harness runs on PRs touching `backend/app/agents/education/**` or `backend/app/agents/state.py` (mirrors categorization harness path-filter style)

- [ ] **Task 6**: README (AC #10)
  - [ ] 6.1 Document fixture schema with annotated example
  - [ ] 6.2 Document each assertion DSL key with a minimal working example
  - [ ] 6.3 Document "how to add a fixture" end-to-end
  - [ ] 6.4 Add explicit tier-1-scope disclaimer and pointer to Story 12.2 for qualitative scoring

- [ ] **Task 7**: Reconcile with Story 11.11 scenario tests (AC #9)
  - [ ] 7.1 Developer chooses migrate-vs-keep for each 11.11 test; document choice in Completion Notes
  - [ ] 7.2 Ensure at least one test surface (harness OR unit test) still asserts the 97%-transfers regression

- [ ] **Task 8**: Mark Story 12.1 `done` in [sprint-status.yaml](_bmad-output/implementation-artifacts/sprint-status.yaml) after code review.

## Dev Notes

### Why stubbed LLM instead of real LLM calls

This harness tests the *wiring and output contract* of `education_node`: did it call the right aggregators, did it assemble subscription + structural + LLM cards in the correct order, did it short-circuit correctly on degenerate inputs, etc. The LLM's generative quality is Story 12.2's problem. Stubbing keeps:
- **CI cost**: zero tokens per run → zero dollars
- **CI speed**: <10s vs. minutes
- **Determinism**: same input → same output every time → no flakes

When prompt templates change, fixtures' canned `llm_response` may need re-recording. That's acceptable maintenance cost and is documented in the README.

### Why 15 fixtures and not 5 or 50

Fewer than ~10 misses important coverage (literacy levels, adversarial inputs, edge cases). More than ~20 becomes a maintenance burden that disincentivises additions. 15 is a pragmatic sweet spot that leaves room to grow as new regression scenarios are discovered — **every future insight-output bug should earn a new fixture** before its fix merges (documented policy in the README).

### Why rule-based now, not LLM-judge

LLM-as-judge has a silent-failure mode: the judge can learn to agree with the author's stated prompt goals rather than catch real problems. Without human calibration it produces comforting but meaningless scores. Tier 1 deterministic assertions have no such failure mode — an assertion either passes or fails, and a failure is always real. Once the tier-1 foundation is in place, Story 12.2 layers the judge on top; Story 12.3 calibrates it. Skipping 12.1 and going straight to 12.2 would give us a fancy-looking system that silently misses the Story 11.11 regression class.

### Relation to other harnesses

- **Story 11.1 — categorization golden-set**: upstream of this harness. A fixture in 12.1 assumes `categorized_transactions` is already correct; if categorization quality regresses, 11.1's harness catches it.
- **Story 9.3 — RAG retrieval eval** (Epic 9): orthogonal. This harness stubs RAG with empty or canned context; the RAG harness validates retrieval quality independently. Composition coverage (both simultaneously) is deferred to Epic 12 Phase 2.
- **Story 12.2 — LLM-as-judge**: will invoke the real LLM on a subset of these same fixtures (or a separate curated set) and score qualitative axes. Advisory until 12.3 calibrates it.

### References

- [Story 11.11 — Exclude transfers from insight generation](_bmad-output/implementation-artifacts/11-11-exclude-transfers-from-insight-generation.md) — source of the flagship regression fixture
- [backend/app/agents/education/node.py](backend/app/agents/education/node.py) — system under test
- [backend/tests/agents/test_education.py](backend/tests/agents/test_education.py) — existing unit tests (scenario tests from 11.11 land here initially)
- [Story 11.1 — Golden-Set Evaluation Harness for Categorization](_bmad-output/implementation-artifacts/11-1-golden-set-evaluation-harness-for-categorization.md) — CI gate pattern to mirror

## Out of Scope

- **LLM-as-judge scoring** — Story 12.2
- **Human-label calibration** — Story 12.3
- **End-to-end pipeline tests** (ingestion → categorization → education composition) — Epic 12 Phase 2 revisit after Epics 9 + 10
- **RAG retrieval eval** — Epic 9 Story 9.3
- **Chat-quality eval** — Epic 10

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List
