# Story 8.3: Triage Agent & Severity Scoring

Status: done

## Story

As a **user**,
I want my financial insights ranked by severity so I know which ones demand my attention first,
So that I'm not overwhelmed and can focus on what matters most.

## Acceptance Criteria

1. **Given** the Pattern Detection Agent has produced its findings **When** the Triage Agent (LangGraph node at `agents/triage/node.py`) runs **Then** it assigns a `severity` level to each finding using scoring logic in `severity.py` based on UAH impact: `critical` — finding affects > 20% of the user's estimated monthly income, or an inactive subscription costs > 500 UAH/month; `warning` — finding affects 5–20% of monthly income, or a spending category increased > 25% month-over-month; `info` — finding affects < 5% of monthly income or is informational.

2. **Given** severity is assigned to all findings **When** the Education Agent generates insight cards from those findings **Then** each `insights` record is stored with the `severity` field set to the triage output value (`critical`, `warning`, `info`), filling the field that was already in the schema from Story 3.4.

3. **Given** the user's monthly income estimate is unavailable (first upload, no income transactions detected) **When** the severity scoring runs **Then** severity falls back to absolute UAH thresholds: `critical` > 2,000 UAH impact, `warning` 500–2,000 UAH, `info` < 500 UAH.

4. **Given** the Triage Agent fails or produces no output **When** insights are stored **Then** all `severity` fields default to `info` — the pipeline never fails or produces null severity values.

5. **Given** the Teaching Feed API `GET /api/v1/insights` **When** it queries the insights table **Then** results are sorted server-side by severity: `critical` first, `warning` second, `info` third (replacing the previous sort order which used `high`/`medium`/`low` labels).

## Tasks / Subtasks

- [x] Task 1: Create `severity.py` — pure Python severity scoring logic (AC: #1, #3)
  - [x] 1.1 Create `backend/app/agents/triage/severity.py`. No LLM — pure math. This module contains two public functions and shared threshold constants.
  - [x] 1.2 Define module-level constants:
    ```python
    # Income-relative thresholds (fraction of monthly income)
    CRITICAL_INCOME_FRACTION = 0.20   # > 20% of monthly income
    WARNING_INCOME_FRACTION = 0.05    # 5–20% of monthly income
    # Absolute fallback thresholds in kopiykas (UAH × 100)
    CRITICAL_ABS_KOPIYKAS = 200_000   # > 2,000 UAH
    WARNING_ABS_KOPIYKAS = 50_000     # 500–2,000 UAH
    # Subscription-specific absolute threshold in kopiykas
    CRITICAL_SUB_KOPIYKAS = 50_000    # inactive sub > 500 UAH/month
    # MoM change threshold for warning
    WARNING_MOM_CHANGE_PCT = 25.0     # category increased > 25% MoM
    ```
  - [x] 1.3 Implement `score_pattern_finding(finding: dict, monthly_income_kopiykas: int | None) -> str`:
    - Extract `impact_kopiykas = abs(finding.get("current_amount_kopiykas", 0) or 0)` — the affected amount in kopiykas.
    - Extract `change_percent = abs(finding.get("change_percent", 0.0) or 0.0)`.
    - If `monthly_income_kopiykas` is set and > 0:
      - If `impact_kopiykas / monthly_income_kopiykas > CRITICAL_INCOME_FRACTION` → return `"critical"`
      - If `impact_kopiykas / monthly_income_kopiykas > WARNING_INCOME_FRACTION` → return `"warning"`
      - If `change_percent > WARNING_MOM_CHANGE_PCT` → return `"warning"` (MoM check regardless of income fraction)
      - Else → return `"info"`
    - Fallback (no income): use absolute thresholds:
      - `impact_kopiykas > CRITICAL_ABS_KOPIYKAS` → `"critical"`
      - `impact_kopiykas > WARNING_ABS_KOPIYKAS` or `change_percent > WARNING_MOM_CHANGE_PCT` → `"warning"`
      - Else → `"info"`
  - [x] 1.4 Implement `score_subscription(sub: dict, monthly_income_kopiykas: int | None) -> str`:
    - Extract `monthly_cost = sub.get("estimated_monthly_cost_kopiykas", 0) or 0`.
    - Extract `is_active = sub.get("is_active", True)`.
    - Inactive subscription with `monthly_cost > CRITICAL_SUB_KOPIYKAS` → `"critical"` (AC specifies inactive > 500 UAH as critical).
    - If `monthly_income_kopiykas` is set and > 0:
      - If `monthly_cost / monthly_income_kopiykas > CRITICAL_INCOME_FRACTION` → return `"critical"`
      - If `monthly_cost / monthly_income_kopiykas > WARNING_INCOME_FRACTION` → return `"warning"`
    - Fallback:
      - `monthly_cost > CRITICAL_ABS_KOPIYKAS` → `"critical"`
      - `monthly_cost > WARNING_ABS_KOPIYKAS` → `"warning"`
    - Active subscription with `monthly_cost` below warning threshold → `"info"`
    - Default → `"info"`

- [x] Task 2: Create `backend/app/agents/triage/node.py` (AC: #1, #2, #4)
  - [x] 2.1 Create `backend/app/agents/triage/__init__.py` (empty).
  - [x] 2.2 Implement `triage_node(state: FinancialPipelineState) -> FinancialPipelineState`:
    - Extract `user_id`, `job_id` from state.
    - Query `FinancialProfile` from DB using `get_sync_session()` (same pattern as `_persist_findings` in `pattern_detection/node.py`). Look up by `user_id`. If not found, set `monthly_income_kopiykas = None`.
    - If profile found: estimate monthly income as `profile.total_income / max(1, months_in_period)` where `months_in_period = max(1, (profile.period_end - profile.period_start).days / 30)` if both dates are present, else `monthly_income_kopiykas = None`. If `profile.total_income == 0`, set `monthly_income_kopiykas = None`.
    - Score each finding in `state.get("pattern_findings", [])` using `score_pattern_finding(finding, monthly_income_kopiykas)`. Add `"severity"` key to each finding dict (work on copies: `{**f, "severity": score}`).
    - Score each subscription in `state.get("detected_subscriptions", [])` using `score_subscription(sub, monthly_income_kopiykas)`. Add `"severity"` key similarly.
    - Build `triage_category_severity_map: dict[str, str]` — for each pattern finding, map `finding["category"]` to the worst (highest priority) severity across all findings in that category. Severity priority: critical > warning > info.
    - On any exception: log the error, append to `state["errors"]`, return state with original (unmodified) `pattern_findings` and `detected_subscriptions`, and set `triage_category_severity_map = {}` (pipeline never halts — AC #4).
    - On success: return `{**state, "pattern_findings": scored_findings, "detected_subscriptions": scored_subscriptions, "triage_category_severity_map": map, "step": "triage", "completed_nodes": [...completed, "triage"]}`.
  - [x] 2.3 Add structured logging: `logger.info("triage_completed", extra={..., "pattern_count": N, "subscription_count": M, "critical_count": C, "warning_count": W, "monthly_income_available": bool(monthly_income_kopiykas)})`.

- [x] Task 3: Update `pipeline.py` — wire triage between pattern_detection and education (AC: #1, #2)
  - [x] 3.1 In `backend/app/agents/pipeline.py`, import `triage_node` from `app.agents.triage.node`.
  - [x] 3.2 Add `graph.add_node("triage", triage_node)`.
  - [x] 3.3 Update edges: change `graph.add_edge("pattern_detection", "education")` to `graph.add_edge("pattern_detection", "triage")` + `graph.add_edge("triage", "education")`.

- [x] Task 4: Update `state.py` — add triage fields (AC: #1, #2)
  - [x] 4.1 In `backend/app/agents/state.py`, add `triage_category_severity_map: dict` to `FinancialPipelineState`.

- [x] Task 5: Update `processing_tasks.py` — add triage state fields and update severity default (AC: #2, #4)
  - [x] 5.1 Added `"triage_category_severity_map": {}` to the `initial_state` dict in `process_upload` (line ~185). Note: `resume_upload` does NOT construct a new `initial_state` — it calls `resume_pipeline()` which rehydrates state from the LangGraph checkpointer, so no second edit is required.
  - [x] 5.2 Updated both insight card persistence blocks (in `process_upload` and `resume_upload`): changed `severity=card.get("severity", "medium")` to `severity=card.get("severity", "info")`.

- [x] Task 6: Update `education/node.py` — use triage severity (AC: #2)
  - [x] 6.1 In `_build_subscription_cards`, change `"severity": "medium"` to `"severity": sub.get("severity", "info")`. The triage node will have added `"severity"` to each subscription dict before education runs.
  - [x] 6.2 In `education_node`, after parsing LLM cards (`cards = _parse_insight_cards(...)`), apply triage category severity override:
    ```python
    triage_map = state.get("triage_category_severity_map", {})
    if triage_map:
        cards = [
            {**card, "severity": triage_map.get(card.get("category", ""), card.get("severity", "info"))}
            for card in cards
        ]
    ```
    This overrides LLM-generated severity with the triage-computed severity for matching categories. If a card's category is not in triage_map, keep the LLM-assigned severity.

- [x] Task 7: Update `insight_service.py` — sort by critical/warning/info (AC: #5)
  - [x] 7.1 In `backend/app/services/insight_service.py`, update `severity_order` to:
    ```python
    severity_order = case(
        (Insight.severity == "critical", 0),
        (Insight.severity == "warning", 1),
        (Insight.severity == "info", 2),
        # Backward compatibility for pre-8.3 records
        (Insight.severity == "high", 0),
        (Insight.severity == "medium", 1),
        else_=2,
    )
    ```
  - [x] 7.2 Update `_SEV_MAP` to: `{"critical": 0, "warning": 1, "info": 2, "high": 0, "medium": 1, "low": 2}` (backward compat for cursor pagination through pre-8.3 rows).

- [x] Task 8: Update `insight.py` — change severity default (AC: #4)
  - [x] 8.1 In `backend/app/models/insight.py`, change `severity: str = Field(default="medium")` to `severity: str = Field(default="info")`. Comment: `# critical, warning, info (pre-8.3 rows may contain high/medium/low — handled in insight_service.py)`.

- [x] Task 9: Write tests `backend/tests/agents/test_triage.py` (AC: #1–#4)
  - [x] 9.1 Create `backend/tests/agents/test_triage.py`. Use the same sync-SQLite + `StaticPool` fixtures as `test_pattern_detection.py`. Import `fake_redis` autouse from conftest (handles `publish_job_progress` silencing if present — triage doesn't emit SSE but importing the fixture is harmless).
  - [x] 9.2 **Test: `score_pattern_finding` — income-relative critical.** Monthly income = 1,000,000 kopiykas (10,000 UAH). Finding with `current_amount_kopiykas = 250,000` (25% of income > 20% threshold). Assert `"critical"`.
  - [x] 9.3 **Test: `score_pattern_finding` — income-relative warning.** Monthly income = 1,000,000. `current_amount_kopiykas = 100,000` (10%, between 5–20%). Assert `"warning"`.
  - [x] 9.4 **Test: `score_pattern_finding` — income-relative info.** Monthly income = 1,000,000. `current_amount_kopiykas = 30,000` (3% < 5%). `change_percent = 10.0` (< 25%). Assert `"info"`.
  - [x] 9.5 **Test: `score_pattern_finding` — MoM change triggers warning.** Monthly income = 1,000,000. `current_amount_kopiykas = 30,000`. `change_percent = 30.0` (> 25%). Assert `"warning"` (MoM threshold fires even below income fraction threshold).
  - [x] 9.6 **Test: `score_pattern_finding` — absolute fallback critical.** No income (`monthly_income_kopiykas = None`). `current_amount_kopiykas = 300,000` (> 2,000 UAH). Assert `"critical"`.
  - [x] 9.7 **Test: `score_pattern_finding` — absolute fallback info.** No income. `current_amount_kopiykas = 10,000` (100 UAH). `change_percent = 5.0`. Assert `"info"`.
  - [x] 9.8 **Test: `score_subscription` — inactive > 500 UAH → critical.** `estimated_monthly_cost_kopiykas = 60,000`. `is_active = False`. Assert `"critical"` (AC: inactive sub > 500 UAH = critical).
  - [x] 9.9 **Test: `score_subscription` — active below threshold → info.** `estimated_monthly_cost_kopiykas = 10,000`. `is_active = True`. No income. Assert `"info"`.
  - [x] 9.10 **Test: `triage_node` adds severity to pattern_findings.** Build minimal `FinancialPipelineState` with one pattern finding (`current_amount_kopiykas = 300_000`, no income profile in DB). Run `triage_node`. Assert that the returned state's `pattern_findings[0]` has `"severity"` key.
  - [x] 9.11 **Test: `triage_node` adds severity to detected_subscriptions.** Similar setup with one detected subscription. Assert `"severity"` present in returned `detected_subscriptions[0]`.
  - [x] 9.12 **Test: `triage_node` reads FinancialProfile from DB for income estimate.** Insert a `FinancialProfile` into SQLite (via sync engine fixture). Call `triage_node` with a finding that would be "info" on absolute thresholds but "critical" given the profile income. Assert `"critical"` — confirms income was read from DB.
  - [x] 9.13 **Test: `triage_node` failure → no halt, severity defaults to "info".** Patch `score_pattern_finding` to raise `RuntimeError`. Assert node returns a state (no raise), `errors` list is non-empty, `pattern_findings` in returned state retains original dicts (no severity key OR original severity if pre-existing).
  - [x] 9.14 **Test: `triage_category_severity_map` worst-severity-per-category.** Two pattern findings with same `category = "food"`: one scores "warning", one scores "critical". Assert `triage_category_severity_map["food"] == "critical"`.

- [x] Task 10: Version bump (AC: new user-facing feature = MINOR)
  - [x] 10.1 Update `VERSION`: `1.16.0` → `1.17.0`.

## Dev Notes

### Pipeline Topology Change

This story inserts a new node between `pattern_detection` and `education`:

```
Before 8.3: categorization → pattern_detection → education → END
After 8.3:  categorization → pattern_detection → triage → education → END
```

`pipeline.py` is the only place the graph is wired. The `resume_pipeline()` function (used by Celery retry) also uses `build_pipeline()`, so it automatically picks up the new node.

### Triage Node: State Mutation Pattern

The triage node works on **copies** of the finding/subscription dicts. It never mutates the originals. Pattern: `{**f, "severity": score}`. This matches how pattern_detection_node builds state dicts.

### Monthly Income Estimation

The triage node reads `FinancialProfile` using `get_sync_session()` (same sync-DB pattern as `pattern_detection/node.py`). The profile accumulates income across all previous uploads. Monthly estimate:

```python
if profile and profile.total_income > 0 and profile.period_start and profile.period_end:
    months = max(1.0, (profile.period_end - profile.period_start).days / 30.0)
    monthly_income_kopiykas = int(profile.total_income / months)
else:
    monthly_income_kopiykas = None
```

**Important:** The FinancialProfile is updated by `build_or_update_profile()` in `processing_tasks.py` AFTER the pipeline completes (step 8, line ~310). So when triage runs, the profile reflects data from previous uploads only — the current upload's income is not yet included. This is by design: triage uses historical income to score current-upload findings.

### Severity Values: Old vs New

| Old (pre-8.3) | New (8.3+) | Priority |
|---|---|---|
| `high` | `critical` | 0 (first in feed) |
| `medium` | `warning` | 1 |
| `low` | `info` | 2 (last in feed) |

The `insight_service.py` sort handles both old and new values. Old rows in `insights` table remain valid — no migration/backfill required.

### Education Node Changes

Two changes to `education/node.py`:

1. **`_build_subscription_cards`** — change `"severity": "medium"` to `"severity": sub.get("severity", "info")`. The triage node runs before education and adds `"severity"` to each dict in `detected_subscriptions`. This is the primary mechanism for subscription card severity.

2. **LLM card post-processing** — after `_parse_insight_cards(response.content)`, apply triage override:
   ```python
   triage_map = state.get("triage_category_severity_map", {})
   if triage_map:
       cards = [{**c, "severity": triage_map.get(c.get("category", ""), c.get("severity", "info"))} for c in cards]
   ```
   When triage_map is empty (triage failed or no findings), LLM-generated severity is preserved as-is.

### Failure Semantics (AC #4)

The triage node MUST NOT halt the pipeline. Failure modes:
- DB query fails: `monthly_income_kopiykas = None`, scoring continues with absolute thresholds
- Scoring raises (bug in severity.py): catch, log, set all findings to "info", `triage_category_severity_map = {}`
- Return state normally in all cases — LangGraph checkpointing will see a completed "triage" node

### SSE Progress

No new SSE event for triage. The existing progress sequence remains unchanged:
- `"pattern-detection"` at 55% (from pattern_detection_node)
- `"insights"` at 70% (from processing_tasks.py after pipeline completes)

Triage is a fast computation (pure math + one DB read) — no user-visible delay, no new step to report.

### Testing: DB Fixture for FinancialProfile

The `triage_node` test that verifies income reading (Task 9.12) needs to insert a `FinancialProfile` row into the SQLite test engine. The node uses `get_sync_session()` which is patched to use the test engine — same `patch("app.core.database.get_sync_session", ...)` pattern as `test_pattern_detection.py` tests that verify persistence.

### Project Structure Notes

New files follow existing patterns:
- `triage/` subfolder mirrors `pattern_detection/` subfolder layout
- `severity.py` is a pure module (module-level constants + public functions) — same shape as `detectors/trends.py`
- `node.py` follows the same `get_sync_session()` + structured logging pattern as `pattern_detection/node.py`

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story 8.3] — User story and acceptance criteria
- [Source: backend/app/agents/pipeline.py](backend/app/agents/pipeline.py) — Graph to extend with triage node
- [Source: backend/app/agents/state.py](backend/app/agents/state.py) — FinancialPipelineState to extend
- [Source: backend/app/agents/pattern_detection/node.py](backend/app/agents/pattern_detection/node.py) — Node pattern to follow (get_sync_session, structured logging, try/except)
- [Source: backend/app/agents/education/node.py](backend/app/agents/education/node.py) — `_build_subscription_cards` and LLM card parsing to update
- [Source: backend/app/models/insight.py](backend/app/models/insight.py) — severity field default to change
- [Source: backend/app/models/financial_profile.py](backend/app/models/financial_profile.py) — FinancialProfile model (total_income, period_start, period_end)
- [Source: backend/app/services/insight_service.py](backend/app/services/insight_service.py) — severity_order sort to update for critical/warning/info
- [Source: backend/app/tasks/processing_tasks.py](backend/app/tasks/processing_tasks.py) — initial_state (add triage field) and card persistence (update default severity)
- [Source: backend/tests/agents/test_pattern_detection.py](backend/tests/agents/test_pattern_detection.py) — sync SQLite + StaticPool + get_sync_session patch pattern to mirror
- [Source: _bmad-output/implementation-artifacts/8-2-subscription-detection.md] — Previous story learnings (JSONB/JSON, Alembic chain, independent try/except pattern)
- [Source: _bmad-output/implementation-artifacts/8-1-pattern-detection-agent.md] — Story 8.1 learnings (Alembic chain, test fixtures)

## Dev Agent Record

### Agent Model Used

claude-opus-4-7 (1M context)

### Debug Log References

### Completion Notes List

- **Triage node placement.** `triage_node` is wired between `pattern_detection` and `education` in `pipeline.py`. The `resume_pipeline()` function reuses `build_pipeline()`, so checkpoint-based retries automatically pick up the new node.
- **Failure semantics (AC #4).** On any exception inside `triage_node`, the node logs the error, appends a `{step: "triage", error_code: "TRIAGE_FAILED", ...}` entry to `state["errors"]`, returns the original (unmodified) `pattern_findings`/`detected_subscriptions`, and sets `triage_category_severity_map = {}`. It never raises — the pipeline continues to education unchanged. Education then preserves LLM-assigned severities (no override applied) and subscription cards fall back to `sub.get("severity", "info")` → `"info"`. Persistence in `processing_tasks.py` defaults to `"info"` if the card omits severity.
- **Income estimation.** `_estimate_monthly_income_kopiykas()` reads the user's `FinancialProfile` via `get_sync_session()` (same pattern as `pattern_detection/node.py`). Returns `None` when no profile exists, `total_income <= 0`, or period dates are missing. The profile reflects data from PRIOR uploads (it is updated after the pipeline completes), which is intentional — current-upload income is excluded from the divisor for the current upload's findings.
- **Worst-per-category map.** `_worst_severity_per_category()` reduces scored findings to `{category: worst_severity}` where critical < warning < info by integer priority. Used by education to override LLM-assigned severities for matching categories.
- **Education override.** After `_parse_insight_cards`, cards whose `category` is in `triage_category_severity_map` get their severity overridden by the triage value. Cards with categories NOT in the map keep the LLM-assigned severity (which may still be a legacy value like "medium" — that's handled by the backward-compat sort in `insight_service.py`).
- **Subscription card severity.** `_build_subscription_cards` now reads `sub.get("severity", "info")`. The triage node has already added `"severity"` to each subscription dict before education runs, so the actual stored value comes from triage. The default kicks in only on the failure path or when triage didn't run.
- **Sort backward compatibility.** `insight_service.py` `severity_order` and `_SEV_MAP` accept BOTH new (`critical`/`warning`/`info`) and pre-8.3 (`high`/`medium`/`low`) values. `critical`/`high` → 0, `warning`/`medium` → 1, `info`/`low` → 2. No DB migration needed.
- **`processing_tasks.py` Task 5.1 deviation.** The story called out two `initial_state` dicts (one in `process_upload` ~line 185 and one in `resume_upload` ~line 580). In the current code there is only ONE `initial_state` — `resume_upload` uses `resume_pipeline()` which restores state from the LangGraph checkpointer rather than constructing a new initial state. Only the `process_upload` initial_state was updated.
- **Test approach.** 13 tests in `tests/agents/test_triage.py` cover all scoring branches (pure-function tests for `score_pattern_finding` and `score_subscription`) plus node-level tests using the same sync-SQLite + `StaticPool` + `get_sync_session` patch pattern as `test_pattern_detection.py`. The income-from-DB test uses `FinancialProfile(total_income=400_000, period_days=30)` so a 1,000 UAH (100,000 kopiyka) finding is 25% of monthly income → critical via the income-relative branch (would be only "warning" via absolute thresholds).
- **Pre-existing test failures (NOT regressions).** Two tests are failing on `main` baseline independently of this story: `tests/test_sse_streaming.py::test_happy_path_publishes_progress_events` and `tests/test_processing_tasks.py::TestInsightReadySSEEvents::test_insight_ready_events_emitted_per_insight`. Both assert against an SSE event sequence that no longer matches the actual code (e.g. expecting a `step="education"` `pipeline-progress` event that the current `processing_tasks.py` does not emit — it emits `step="insights"` at 70% instead). Confirmed pre-existing by `git stash` / re-run on baseline. Out of scope for Story 8.3.

### Code Review Follow-ups (2026-04-18)

Adversarial senior-dev review surfaced 9 findings; 2 HIGH + 4 MEDIUM were fixed in-place, 3 LOW findings promoted to the tech-debt register.

**HIGH fixed:**
- **H1 — [processing_tasks.py:638](backend/app/tasks/processing_tasks.py#L638)**: `resume_upload` persistence block still defaulted severity to `"medium"`. Task 5.2 was marked complete but only `process_upload:256` was updated. Changed to `"info"`. Without this, any retried job with an LLM-missing-severity card would have persisted with the pre-8.3 value, defeating AC #4.
- **H2 — [education/node.py:75](backend/app/agents/education/node.py#L75)**: `_parse_insight_cards` defaulted LLM-missing severity to `"medium"` — bypassing the new `Insight.severity` model default of `"info"` because the dict carried an explicit value. Changed fallback to `"info"` so cards without an LLM-assigned severity AND without a triage-map match end up as `"info"` per AC #4.

**MEDIUM fixed:**
- **M1 — [triage/node.py:69-133](backend/app/agents/triage/node.py#L69-L133)**: `_estimate_monthly_income_kopiykas` was inside the outer `try`, so a DB failure aborted ALL scoring — contradicting the Dev Notes' promise that "DB query fails: monthly_income = None, scoring continues with absolute thresholds." Split into two try blocks: DB failure now logs a `triage_income_lookup_failed` warning and falls through to absolute-threshold scoring.
- **M2 — [tests/agents/test_triage.py](backend/tests/agents/test_triage.py)**: Added 3 unit tests for `score_subscription` income-relative branches (critical / warning / info) which were previously dead to CI. Also added a node-level regression test `test_triage_node_db_failure_falls_back_to_absolute_thresholds` guarding the M1 fix.
- **M3 — [tests/agents/test_education.py](backend/tests/agents/test_education.py)**: Added `test_education_node_applies_triage_severity_override` and `test_education_node_empty_triage_map_preserves_llm_severity`. These exercise the AC #2 override path in `education_node` — previously tested only on the triage-build side.
- **M4 — [insight_service.py:30](backend/app/services/insight_service.py#L30)**: Docstring said "sorted by severity triage (high first)" — stale after Story 8.3. Updated to describe critical-first ordering with the pre-8.3 compat bucketing.

**LOW promoted to tech-debt register:**
- L1 → **TD-036**: `_SEVERITY_PRIORITY` duplicates `_SEV_MAP` across triage/node.py and insight_service.py.
- L2 → **TD-037**: triage `completed_nodes` not appended on failure path (contract inconsistency with `step` still set).
- L3 → **TD-038**: inverted `FinancialProfile` period silently treated as 1 month of income in the triage divisor.

**Test results after fixes:** `pytest tests/agents/test_triage.py tests/agents/test_education.py -q` → 49 passed. Full suite: 615 passed, 2 pre-existing failures (SSE streaming sequence assertions) unchanged.

### File List

- `backend/app/agents/triage/__init__.py` (new)
- `backend/app/agents/triage/severity.py` (new)
- `backend/app/agents/triage/node.py` (new)
- `backend/app/agents/pipeline.py` (modified — wired triage node + edges)
- `backend/app/agents/state.py` (modified — added `triage_category_severity_map` field)
- `backend/app/agents/education/node.py` (modified — subscription severity from triage; LLM card severity override)
- `backend/app/services/insight_service.py` (modified — sort by critical/warning/info with backward compat)
- `backend/app/models/insight.py` (modified — severity default `medium` → `info`)
- `backend/app/tasks/processing_tasks.py` (modified — initial_state field + severity defaults)
- `backend/tests/agents/test_triage.py` (new — 17 tests; 13 original + 3 subscription income-relative + 1 DB-failure regression)
- `backend/tests/agents/test_education.py` (modified — 2 new tests for triage severity override)
- `docs/tech-debt.md` (modified — TD-036/TD-037/TD-038 added from review)
- `VERSION` (modified — 1.16.0 → 1.17.0)
- `_bmad-output/implementation-artifacts/sprint-status.yaml` (modified — story status → review)

## Change Log

- 2026-04-18 — Story 8.3 implemented: Triage Agent + severity scoring (critical/warning/info), with income-relative + absolute-fallback thresholds, MoM warning threshold, inactive-subscription critical rule, worst-per-category override map for education cards, server-side sort updated with backward compatibility for pre-8.3 severity values. 13 new tests pass; full suite shows no regressions from this story (2 pre-existing failures unrelated to 8.3, present on `main` baseline).
- 2026-04-18 — Version bumped from 1.16.0 to 1.17.0 (MINOR — new user-facing severity ranking behavior in Teaching Feed).
- 2026-04-18 — Adversarial code review: fixed 2 HIGH (severity defaults in `resume_upload` + `_parse_insight_cards` now `"info"`) and 4 MEDIUM (triage DB-failure isolation; subscription income-relative tests; education override test; insight-service docstring). Promoted 3 LOW items to tech-debt register (TD-036/TD-037/TD-038).
