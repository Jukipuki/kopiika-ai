# Story 11.4: Description Pre-Pass (Cash-Action Override) + Prompt Rule 4 (Self-Transfer Detection)

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As the **system**,
I want a narrow description-based pre-pass that overrides the MCC pass for cash-action narration, plus a prompt-level rule that distinguishes self-transfers from P2P transfers,
So that the two residual failure clusters from Story 11.3a (cash-withdrawal-at-till and ambiguous MCC-4829 self-transfers) close, and `category_accuracy` clears the 0.92 gate with margin above the 0.90 statutory threshold.

**Depends on:** Story 11.3a (prompt disambiguation rules + MCC table extensions). Uses the golden-set harness authored in Story 11.1 and the two-axis prompt contract from Story 11.3.

**Context:** Story 11.3a's post-fix harness reported `category_accuracy=0.878` (79/90) and `kind_accuracy=0.978` — below the 0.90 gate despite a brief touch at 0.900 that was at noise-boundary. The residual 11 failures cluster into two patterns that prompt iteration cannot close:

1. **Cash-action narration + food/retail MCC** (`gs-051`, `gs-055`): the MCC pass deterministically routes MCC 5499 to `groceries` BEFORE the prompt can apply the cash-action disambiguation rule. Architectural fix required — description must override MCC.
2. **Self-transfer with no personal name** (`gs-001`, `gs-002`): the LLM defaults to `transfers_p2p` because the description ("Переказ на картку" / "Transfer to card") has no person-name signal; the prompt needs a rule telling it that absence-of-name is itself a signal.

Additionally, the golden set was relabeled during review — `gs-016` and `gs-017` moved from `other/income` to `transfers/transfer` because the "ФОП" / "UAH account" markers indicate a self-transfer from the user's own PE account, not income. Prompt Rule 4 must classify these correctly or the relabels regress.

PE-statement rows (`gs-091`–`gs-094`, `edge_case_tag = "pe_statement"`) were added during the same review. They cannot be correctly classified by the current pipeline (require Story 11.7 + TD-049) and must be segregated from this story's accuracy metric.

## Acceptance Criteria

1. **Given** the ingestion pipeline stage order **When** Story 11.4 lands **Then** a new description-based pre-pass function runs **BEFORE** the MCC pass loop in `categorization_node` (i.e., before the `for txn in transactions: get_mcc_category(...)` loop at [node.py:289](../../backend/app/agents/categorization/node.py#L289)). Pre-pass lives in a new helper module `backend/app/agents/categorization/pre_pass.py` (or a new function in `node.py` — implementer's choice) and is invoked as the first step of per-transaction classification.

2. **Given** Pre-pass Rule A — cash-action narration override **When** a transaction's description matches the case-insensitive regex `r"\b(cash\s+withdrawal|видача\s+готівки|отримання\s+готівки)\b"` (UA + EN locale coverage) **Then** the pre-pass emits `{"transaction_id": txn["id"], "category": "atm_cash", "confidence_score": 0.95, "transaction_kind": "spending", "flagged": False, "uncategorized_reason": None}` and the transaction is appended to `categorized` — the MCC pass and LLM pass are BOTH skipped for this row. Closes `gs-051` and `gs-055`.

3. **Given** Pre-pass Rule A is specified **When** the implementer considers adding more pre-pass rules **Then** they do NOT — rule count is capped at 1 for this story. Additional pre-pass rules require a demonstrated failure cluster in a later harness run; speculative rules are rejected at code review.

4. **Given** Prompt Rule 4 — self-transfer detection (LIVES IN THE PROMPT, not the pre-pass) **When** `_build_prompt` in `node.py` is extended **Then** it includes a new disambiguation rule paragraph after the existing Rules 1–3 from Story 11.3a:

   > **Rule 4: Self-transfer between own accounts (MCC 4829, no personal name).**
   > When MCC is 4829 AND the description contains ONLY generic account/card/currency language ("Переказ на картку", "Transfer to card", "На гривневий рахунок", "To USD account", "З <color> картки", "From <currency> account", "Конвертація валют", "Переказ між власними рахунками") AND the description does NOT contain any of: a personal full name (Cyrillic or Latin first+last/patronymic), a business marker (ФОП, FOP, LIQPAY*, TOV, LLC), a fund/charity marker («...», named fund), a deposit/investment marker ("депозит", "deposit", "вклад", "investment") → `transfers`, `kind=transfer`. This is the default for MCC 4829 debits that survive the other rules — NOT `transfers_p2p` (which requires a personal name).

5. **Given** Prompt Rule 4 few-shots **When** the prompt is rendered **Then** the few-shot block includes at least three concrete examples:
   - `"Переказ на картку" -50000.00 UAH (MCC 4829)` → `transfers`, `transfer`, `0.9`
   - `"З Білої картки" +1125.10 UAH (MCC 4829)` → `transfers`, `transfer`, `0.9` (inbound leg; card-color reference is a Monobank self-transfer marker)
   - `"Конвертація UAH → USD" -50000.00 UAH (MCC 4829)` → `transfers`, `transfer`, `0.95`

6. **Given** Prompt Rule 4 is in place **When** the harness runs against `gs-016`, `gs-017`, `gs-001`, `gs-002` **Then** all four classify as `transfers/transfer`. Do NOT revert the `gs-016`/`gs-017` relabels (committed 2026-04-21); those labels are correct and this rule must classify them consistently.

7. **Given** the golden-set harness at [test_golden_set.py](../../backend/tests/agents/categorization/test_golden_set.py) **When** it computes per-axis accuracy **Then** it filters rows where `edge_case_tag == "pe_statement"` OUT of the main `category_accuracy` / `kind_accuracy` / `joint_accuracy` metrics. The filter happens inside the harness, not in the fixture. A secondary `pe_statement_accuracy` metric may be emitted in the run report for tracking but does NOT gate the story (those rows require Story 11.7 + TD-049 to classify correctly).

8. **Given** the filtered metric is evaluated on Haiku **When** the harness runs post-11.4 **Then** both `category_accuracy >= 0.92` AND `kind_accuracy >= 0.92` on the non-PE rows (90 main rows after filtering 4 PE rows from the 94-row fixture). Margin above 0.90 is required to account for ±3-row noise on a 90-row main set. The Sonnet test is NOT re-run — Haiku-vs-Sonnet decision is locked per Story 11.3 retrospective.

9. **Given** the post-11.4 harness result **When** the story is closed **Then** the Dev Agent Record captures:
   - Per-axis accuracy on the filtered 86-row set, delta vs. Story 11.3a's 0.878 baseline, tokens, elapsed
   - Separate pe_statement_accuracy value (for future tracking; expected to be near-zero until Story 11.7 lands)
   - If gate cleared: the `@pytest.mark.xfail` on the Haiku test is removed; TD-042 is moved to `## Resolved` in [docs/tech-debt.md](../../docs/tech-debt.md) with the stable measurement recorded
   - If gate missed: the residual failure cluster is enumerated (row IDs + pattern), TD-042 is updated with the specifics, and a follow-up story is proposed (do NOT add rules in 11.4 for patterns that aren't in the current failure set)

10. **Given** existing unit tests **When** Story 11.4's changes land **Then** new tests are added:
    - In a new file `backend/tests/agents/categorization/test_pre_pass.py`: test_cash_withdrawal_en_matches, test_cash_withdrawal_ua_matches, test_otrymannya_gotivky_matches, test_non_cash_action_description_does_not_match, test_cash_action_with_food_mcc_still_overrides (confirms MCC pass bypass), test_pre_pass_output_shape (category=atm_cash, kind=spending, confidence=0.95).
    - In `test_enriched_prompt.py`: test_prompt_includes_self_transfer_rule (asserts Rule 4 text appears), test_prompt_includes_card_color_few_shot (asserts "З <color> картки" example is present).
    - All existing tests continue to pass.

## Tasks / Subtasks

- [x] Task 1: Implement Pre-pass Rule A (cash-action override) (AC: #1, #2, #3)
  - [x] 1.1 Create `backend/app/agents/categorization/pre_pass.py` (new file) with a single function:
    ```python
    import re
    from typing import Optional

    _CASH_ACTION_RE = re.compile(
        r"\b(cash\s+withdrawal|видача\s+готівки|отримання\s+готівки)\b",
        re.IGNORECASE,
    )

    def classify_pre_pass(txn: dict) -> Optional[dict]:
        """Return a categorized result dict if a pre-pass rule matches, else None.

        Pre-pass runs BEFORE the MCC pass. When it matches, the MCC pass and LLM
        pass are both skipped — the pre-pass result is authoritative.

        Rule A (cash-action narration): description names a cash-withdrawal action
        → atm_cash regardless of MCC. Cashback-at-till commonly arrives with
        food/retail MCCs (5499, 5411); the narrative overrides.
        """
        description = (txn.get("description") or "").strip()
        if _CASH_ACTION_RE.search(description):
            return {
                "transaction_id": txn["id"],
                "category": "atm_cash",
                "confidence_score": 0.95,
                "transaction_kind": "spending",
                "flagged": False,
                "uncategorized_reason": None,
            }
        return None
    ```
  - [x] 1.2 In `backend/app/agents/categorization/node.py` `categorization_node` (around line 288, before the MCC loop):
    - Import `classify_pre_pass` from `pre_pass.py`.
    - Insert a new pass BEFORE the MCC loop:
      ```python
      # Pass 0: Description pre-pass — overrides MCC for cash-action narration
      remaining_after_pre_pass: list[dict] = []
      for txn in transactions:
          pre_result = classify_pre_pass(txn)
          if pre_result is not None:
              categorized.append(pre_result)
          else:
              remaining_after_pre_pass.append(txn)
      transactions = remaining_after_pre_pass
      ```
    - The MCC loop at the existing line 289 now iterates over the pre-pass remainder.
  - [x] 1.3 Do NOT add any other pre-pass rules in this story.

- [x] Task 2: Implement Prompt Rule 4 (self-transfer detection) (AC: #4, #5, #6)
  - [x] 2.1 In `_build_prompt` in `node.py`, locate the `Disambiguation rules (surfaced by Story 11.3 golden-set measurement):` block added in Story 11.3a. Append Rule 4 verbatim per AC #4. Preserve Rules 1–3 unchanged.
  - [x] 2.2 In the same function, locate the few-shot examples block. Append a new "Self-transfer vs P2P (Rule 4):" subsection with the three examples from AC #5 formatted the same way as other few-shots. Approximate total few-shots after this story: ~18.
  - [x] 2.3 Verify with a dry-run print that the prompt for a test batch is well under Haiku's context limit (combined input should be ≲ 4K tokens for a 50-txn batch after this addition). Post-11.4 harness used 6311 tokens for a 47-txn single-batch call — well within context.

- [x] Task 3: Extend the harness to filter PE-statement rows (AC: #7)
  - [x] 3.1 In `backend/tests/agents/categorization/test_golden_set.py`, in the accuracy computation section (after results are mapped):
    - Before summing `category_correct` / `kind_correct` / `joint_correct`, partition the golden rows:
      ```python
      pe_rows = [r for r in golden_rows if r["edge_case_tag"] == "pe_statement"]
      main_rows = [r for r in golden_rows if r["edge_case_tag"] != "pe_statement"]
      ```
    - Compute main accuracy against `main_rows` only; keep the existing axis/denominator math but scope to `main_rows`.
    - Optionally compute `pe_statement_accuracy` against `pe_rows` and include it in the run report (nice-to-have; do NOT assert on it).
  - [x] 3.2 Assert `category_accuracy >= 0.92 AND kind_accuracy >= 0.92` on `main_rows` (bumped from 0.90 per AC #8).
  - [x] 3.3 Update the run-report JSON shape to include `main_total`, `pe_total`, and optional `pe_statement_accuracy` for auditability.
  - [x] 3.4 Keep the `@pytest.mark.xfail` decorator in place initially; remove it in Task 6 only if the gate clears. (N/A — Haiku test had no xfail to begin with; the decorator was on Sonnet only and is preserved.)

- [x] Task 4: Unit tests (AC: #10)
  - [x] 4.1 Create `backend/tests/agents/categorization/test_pre_pass.py`:
    - `test_cash_withdrawal_en_matches` — `{"id": "x", "description": "Cash withdrawal Близенько", "amount": -100000, "mcc": 5499}` → result has `category="atm_cash"`, `transaction_kind="spending"`, `confidence_score=0.95`.
    - `test_cash_withdrawal_ua_matches` — same with description "Видача готівки Близенько" → same expectation.
    - `test_otrymannya_gotivky_matches` — description "Отримання готівки в АТБ" → same expectation.
    - `test_non_cash_action_description_does_not_match` — description "Сільпо" with MCC 5411 → `classify_pre_pass` returns `None`.
    - `test_cash_action_with_food_mcc_still_overrides` — explicitly asserts that a `Cash withdrawal X` transaction with MCC 5411 (normally `groceries`) still routes to `atm_cash` via the pre-pass.
    - `test_pre_pass_output_shape` — checks all six output fields (`transaction_id`, `category`, `confidence_score`, `transaction_kind`, `flagged`, `uncategorized_reason`) are present with correct values.
  - [x] 4.2 Extend `test_enriched_prompt.py` with:
    - `test_prompt_includes_self_transfer_rule` — `_build_prompt([...])` output contains the Rule 4 marker text (e.g., `"no personal full name"` or `"Переказ між власними рахунками"`).
    - `test_prompt_includes_card_color_few_shot` — output contains `"З Білої картки"` (or a neutral fragment like `"З "` + `" картки"` if implementers use a different card color in the few-shot).
  - [x] 4.3 Run full categorization suite (`pytest tests/agents/categorization/ tests/agents/test_categorization.py -v`) — confirm all pass. (70 passed.)

- [x] Task 5: Re-run golden-set harness on Haiku (AC: #8, #9)
  - [x] 5.1 `cd backend && python -m pytest tests/agents/categorization/test_golden_set.py::test_golden_set_accuracy -v -s -m integration`.
  - [x] 5.2 Capture the run report from `backend/tests/fixtures/categorization_golden_set/runs/<timestamp>-haiku.json`. → `runs/20260421T130309013273Z-haiku.json`.
  - [x] 5.3 Compare filtered main-rows accuracy to Story 11.3a's 0.878 baseline. Record delta in Dev Agent Record. (Δ category_accuracy = +0.078; Δ kind_accuracy = +0.022.)
  - [x] 5.4 Verify: `gs-051` now classifies as `atm_cash/spending` (Rule A); `gs-001`, `gs-002`, `gs-016`, `gs-017` classify as `transfers/transfer` (Rule 4). (All six targets absent from the mismatches list.)

- [x] Task 6: Close or update TD-042 (AC: #9)
  - [x] 6.1 **If gate cleared (both axes ≥ 0.92):** remove the `@pytest.mark.xfail` on the Haiku harness test. Move TD-042 from `## Open` to `## Resolved` in `docs/tech-debt.md`, replacing the reopen note with a resolution entry that records the stable Haiku measurement + the 0.92 margin methodology. (Haiku test never had an xfail — the decorator was on Sonnet only, which remains correct. TD-042 moved to Resolved with the stable measurement.)
  - [ ] 6.2 **If gate missed:** keep the xfail. Update TD-042's "Problem" section in-place with the specific residual cluster (row IDs + description patterns). Do NOT add speculative rules; propose a follow-up story if a new architectural fix is needed. (N/A — gate cleared.)
  - [x] 6.3 Update `sprint-status.yaml`: flip `11-4-description-pattern-pre-pass-conditional` from `backlog` → `review` per BMad workflow. The code-review step (not the dev) flips `review` → `done` after adversarial review passes.

## Dev Notes

### Architectural Decision — Pre-Pass Must Run Before MCC Pass

The central architectural fix in this story is the **stage order**: the cash-action pre-pass runs BEFORE the MCC pass, not between MCC and LLM. Story 11.3a tried to fix this cluster with a prompt rule, but the MCC pass fires first and deterministically routes `gs-051` / `gs-055` to `groceries` — the LLM never sees them. Only a pre-pass can override.

This is narrow by design. Only one rule lives in the pre-pass: cash-action narration (which has a clear, reliable textual marker). Any future pre-pass rule must be justified by a demonstrated failure cluster that prompt/MCC approaches cannot handle.

Why this is NOT the general "description-pattern pre-pass rules engine" described in tech spec §3.5 of earlier plans: that proposal included broader regex rules (self-transfer, deposit top-up, Cyrillic-name P2P) that are better handled in the LLM prompt where context (MCC, amount sign) can shape the decision. The pre-pass is reserved for cases where MCC correctness must be overridden — which is rare.

### Pre-Pass Regex Rationale

`r"\b(cash\s+withdrawal|видача\s+готівки|отримання\s+готівки)\b"`:
- Word boundaries (`\b`) prevent false matches like "cashwithdrawalFund" (paranoid but cheap).
- `\s+` handles both single-space and multi-space variants.
- `re.IGNORECASE` for "Cash Withdrawal" / "CASH WITHDRAWAL" export variants.
- Three phrases cover observed Monobank narration variants:
  - `cash withdrawal` — EN export
  - `видача готівки` — UA export
  - `отримання готівки` — alternative UA phrasing seen in some receipts
- Does NOT include `готівка`, `cash`, or `withdrawal` alone — too many false positives (e.g., merchant name "Готівка Маркет" or cashback programs).

### Prompt Rule 4 — Why It Belongs in the Prompt, Not the Pre-Pass

The self-transfer determination depends on multiple signals (MCC, description pattern, absence of personal name markers) and interacts with other disambiguation rules (charity jar, FOP+merchant, deposit). Encoding all of that in deterministic regex rules creates maintenance burden and edge-case misfires. The LLM, with the explicit rule text + few-shots, handles the interaction gracefully because it already has the context (MCC, signed amount) in the prompt.

The one thing the prompt cannot currently do is override the MCC pass — that's why cash-action goes pre-pass while self-transfer stays in-prompt.

### Gate Methodology — Why 0.92, Not 0.90

A 94-row fixture (90 main after filtering 4 PE rows) has ±3-row noise at the boundary:
- 0.900 = 81/90 → 1 row off from 80/90 (0.888)
- 0.930 = 84/90 → 3-row margin from 0.90

Story 11.3a passed 0.900 once (81/90), then measured 0.878 (79/90) after a review-pass — same pipeline, small prompt tweak, 2-row difference. That's noise. Requiring 0.92 on a single run creates real margin above the 0.90 statutory threshold.

Alternative: require 3 consecutive runs ≥ 0.90. Not implemented in this story — pick one methodology per retrospective decision.

### PE-Row Filter — Why It's a Harness Concern, Not a Fixture Concern

`gs-091`–`gs-094` are in the fixture because they ARE valid ground truth — they describe real PE-statement semantics. Removing them from the fixture would lose test coverage and mask future regressions. Filtering at the harness level gives us:
- Current story measures card-pipeline accuracy cleanly (90 main rows out of a 94-row fixture).
- PE rows stay in the fixture, waiting for Story 11.7 + TD-049 to land.
- Secondary `pe_statement_accuracy` metric tracks PE-pipeline progress independently.

### Test Isolation

The existing `test_categorization.py` unit tests mock the LLM and should NOT be affected by this story because:
- They construct transactions that DON'T match the pre-pass regex (no cash-action narration).
- Their mocked LLM responses are unchanged (Rule 4 affects the prompt text, not the response contract).

If any existing test happens to use a description like "Cash withdrawal X" in its fixtures (unlikely), it would now be handled by pre-pass instead of reaching the mocked LLM. Grep for such cases and update those specific tests if found.

### References

- Tech spec §3.5 (description-pattern pre-pass, original conditional scope): [tech-spec-ingestion-categorization.md](../_bmad-output/planning-artifacts/tech-spec-ingestion-categorization.md)
- Tech spec §3.3 (LLM prompt contract — Rule 4 lives here): same file
- Story 11.3a retrospective (failure-cluster analysis): [11-3a-categorization-accuracy-follow-up.md](./11-3a-categorization-accuracy-follow-up.md)
- Story 11.3a golden-set run report (baseline to beat): `backend/tests/fixtures/categorization_golden_set/runs/20260421T083421201052Z-haiku.json`
- TD-042 (reopened 2026-04-21): [docs/tech-debt.md](../../docs/tech-debt.md)
- TD-048 (self-transfer pair dedup across uploads — NOT in this story's scope): same file
- TD-049 (counterparty-aware categorization for PE statements — blocks PE-row gating): same file
- Categorization node: [backend/app/agents/categorization/node.py](../../backend/app/agents/categorization/node.py) (especially `categorization_node` at line 275 and `_build_prompt` earlier in the file)
- MCC mapping module: [backend/app/agents/categorization/mcc_mapping.py](../../backend/app/agents/categorization/mcc_mapping.py)
- Golden-set harness: [backend/tests/agents/categorization/test_golden_set.py](../../backend/tests/agents/categorization/test_golden_set.py)
- Golden-set fixture (90 rows with 4 PE rows): [backend/tests/fixtures/categorization_golden_set/golden_set.jsonl](../../backend/tests/fixtures/categorization_golden_set/golden_set.jsonl)

### Anti-Scope

Things this story does NOT do (explicitly out of scope):

- **Does NOT add more pre-pass rules** beyond Rule A. Self-transfer, deposit top-up, P2P — all stay in the LLM prompt. Rule count cap is enforced at code review.
- **Does NOT implement counterparty-aware categorization** — that's TD-049, blocked on Story 11.7.
- **Does NOT dedupe self-transfer pairs across multi-statement uploads** — TD-048.
- **Does NOT add PE-statement parsing** — Story 11.7 (AI-assisted schema detection) will handle that.
- **Does NOT retest Sonnet** — decision locked in Story 11.3 retrospective; Haiku wins.
- **Does NOT touch `llm.py` `max_tokens`** — flagged as a defensive fix in architect review; fold into whatever story next touches `llm.py`.

## Dev Agent Record

### Agent Model Used

Claude Opus 4.7 (1M context) via Claude Code CLI. Pipeline LLM: `claude-haiku-4-5-20251001` (unchanged).

### Debug Log References

Haiku golden-set run report: [backend/tests/fixtures/categorization_golden_set/runs/20260421T130309013273Z-haiku.json](../../backend/tests/fixtures/categorization_golden_set/runs/20260421T130309013273Z-haiku.json). Single batch, 47-txn call, 6311 tokens, 7.64s wall.

### Completion Notes List

- **Gate cleared with margin.** Haiku, filtered 90-row main set (4 PE rows segregated):
  - `category_accuracy = 0.956` (86/90) — Δ +0.078 vs. Story 11.3a baseline 0.878, Δ +0.036 vs. the 0.92 gate.
  - `kind_accuracy = 1.000` (90/90) — Δ +0.022 vs. baseline 0.978, Δ +0.080 vs. the 0.92 gate.
  - `joint_accuracy = 0.956`.
  - `pe_statement_accuracy = 1.000` (4/4) secondary, non-gating. Unexpectedly high; may reflect descriptions that happen to classify correctly under existing rules, not counterparty-aware logic — TD-049 still warranted for durable PE correctness.
- **Target rows all corrected.** `gs-001`, `gs-002`, `gs-016`, `gs-017` (Rule 4 self-transfer) and `gs-051`, `gs-055` (Rule A cash-action pre-pass) are absent from the mismatches list.
- **Residual 4 mismatches (non-blocking, out of Story 11.4 scope):**
  - `gs-027`: education → government (MCC 4829 ambiguity around an education-adjacent payment).
  - `gs-061`, `gs-068`: subscriptions → shopping (subscriptions/shopping boundary).
  - `gs-086`: transport → shopping (large-outlier transport purchase).
- **TD-042 disposition:** Resolved. Path 6.1 taken (gate cleared); moved TD-042 out of `## Open` and replaced its resolved-section stub with a full resolution entry capturing the stable measurement and 0.92 margin methodology. No xfail removal needed — the Haiku test never had one; the Sonnet xfail remains correctly in place per Story 11.3 retrospective.
- **Regression posture:** `tests/agents/categorization/` + `tests/agents/test_categorization.py` → 70/70 pass. Full backend suite had 4 pre-existing failures unrelated to this story (verified by running the same tests on `main` pre-stash: `test_golden_set_edge_case_coverage` — salary_inflow fixture coverage; `test_insight_ready_events_emitted_per_insight` + `test_job_complete_payload_has_null_date_range_when_no_transactions` + `test_happy_path_publishes_progress_events` — SSE/pipeline-result wiring from Stories 11.5/11.6). No new regressions from Story 11.4.

### File List

**New:**
- `backend/app/agents/categorization/pre_pass.py`
- `backend/tests/agents/categorization/test_pre_pass.py` — unit coverage for the pre-pass regex; integration-shaped `test_categorization_node_bypasses_mcc_pass_for_cash_action` locks the pre-pass-BEFORE-MCC ordering; `test_pre_pass_confidence_is_above_default_threshold` locks the confidence invariant (added during code review).

**Modified:**
- `backend/app/agents/categorization/node.py` — wired pre-pass before MCC loop; added Prompt Rule 4 text + 3 new few-shots (`ex-18`–`ex-20`).
- `backend/tests/agents/categorization/test_golden_set.py` — PE-row partition, 0.92 gate, `main_total`/`pe_total`/`pe_statement_accuracy` report fields, updated stdout summary.
- `backend/tests/agents/categorization/test_enriched_prompt.py` — added `test_prompt_includes_self_transfer_rule`, `test_prompt_includes_card_color_few_shot`.
- `docs/tech-debt.md` — removed reopened TD-042 entry from `## Open`; replaced resolved-section stub with full resolution entry.
- `_bmad-output/implementation-artifacts/sprint-status.yaml` — status `backlog`/`ready-for-dev` → `review`.

**Generated (gitignored — not committed, but preserved locally for audit):**
- `backend/tests/fixtures/categorization_golden_set/runs/20260421T130309013273Z-haiku.json` — post-11.4 Haiku harness run report. Path is covered by `.gitignore` (`backend/tests/fixtures/categorization_golden_set/runs/*.json`); referenced in Debug Log References above.
- `_bmad-output/implementation-artifacts/11-4-description-pattern-pre-pass-conditional.md` — this file.
- `VERSION` — 1.23.0 → 1.24.0 (MINOR bump; Story 11.4 adds a new pre-pass categorization stage, user-visible improvement in categorization correctness).

## Change Log

| Date | Version | Change |
|---|---|---|
| 2026-04-21 | _(pending)_ | Story 11.4 drafted with narrowed, evidence-based scope: Pre-pass Rule A (cash-action override, runs before MCC pass) + Prompt Rule 4 (self-transfer vs P2P). Gate bumped from 0.90 → 0.92 for noise margin. PE-statement rows filtered from main metric via `edge_case_tag`. Target: close `gs-051`, `gs-055`, `gs-001`, `gs-002`, `gs-016`, `gs-017` and resolve reopened TD-042. |
| 2026-04-21 | 1.24.0 | Story 11.4 implemented: `pre_pass.classify_pre_pass` wired before the MCC pass in `categorization_node`; Prompt Rule 4 added to `_build_prompt` with three new few-shots (`ex-18`/`ex-19`/`ex-20`); golden-set harness now segregates `edge_case_tag="pe_statement"` rows and gates at 0.92. Haiku harness: `category_accuracy=0.956`, `kind_accuracy=1.000` — gate cleared with margin. TD-042 marked Resolved. Version bumped from 1.23.0 to 1.24.0 per story completion (MINOR: new categorization stage + user-visible accuracy improvement). |
| 2026-04-21 | 1.24.0 | Code-review follow-ups: corrected fixture-size prose (94-row fixture / 90 main after PE filter, was stated as 90/86); removed false "committed alongside story" claim for the gitignored run artifact; clarified Task 6.3 (review→done transition is the reviewer's action); added `test_categorization_node_bypasses_mcc_pass_for_cash_action` integration-shaped test locking pre-pass-BEFORE-MCC ordering and `test_pre_pass_confidence_is_above_default_threshold` invariant guard. |
