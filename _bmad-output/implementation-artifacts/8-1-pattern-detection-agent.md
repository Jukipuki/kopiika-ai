# Story 8.1: Pattern Detection Agent

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **user**,
I want the system to automatically detect spending patterns, trends, and anomalies in my transactions,
So that I receive insights about financial patterns I would never have spotted manually.

## Acceptance Criteria

1. **Given** the Categorization Agent has completed and persisted categorized transactions for a processing job **When** the Pattern Detection Agent (LangGraph node at `backend/app/agents/pattern_detection/node.py`) runs **Then** it analyzes the transaction set for: month-over-month category spending changes, anomalously large single transactions (outliers by amount within category), and intra-period spending distribution across categories.

2. **Given** two or more months of transaction data are available for the user **When** the Pattern Detection Agent runs `detectors/trends.py` **Then** category-level spending changes (% delta and UAH delta) are computed and persisted to a `pattern_findings` table created via Alembic migration (fields: `id UUID`, `user_id FK`, `upload_id FK`, `pattern_type ENUM('trend', 'anomaly', 'distribution')`, `category`, `period_start DATE`, `period_end DATE`, `baseline_amount_kopiykas INT`, `current_amount_kopiykas INT`, `change_percent FLOAT`, `finding_json JSONB`).

3. **Given** only a single upload's worth of data is available **When** the Pattern Detection Agent runs **Then** it generates intra-period findings only (spending distribution, top categories, high single transactions); `change_percent` and `baseline_amount_kopiykas` are null; no month-over-month fields are emitted.

4. **Given** the Pattern Detection Agent is integrated into the 5-agent pipeline **When** the Celery worker executes the LangGraph pipeline **Then** the flow is: Ingestion → Categorization → **Pattern Detection** → Education; SSE progress emits a `"pattern-detection"` step with its own human-readable message (e.g., `"Detecting spending patterns..."`); the full pipeline still completes within 60 seconds for 200–500 transactions (NFR4).

5. **Given** the Pattern Detection Agent throws an unhandled exception **When** the error handler activates **Then** the pipeline continues to the Education step with whatever findings were produced before the failure — partial findings are acceptable; the job does not fail entirely.

## Tasks / Subtasks

- [x] Task 1: Extend `FinancialPipelineState` with pattern findings (AC: #1, #2)
  - [x] 1.1 In `backend/app/agents/state.py`, add `pattern_findings: list[dict]` to `FinancialPipelineState`. Each dict will carry the detector output: `{pattern_type, category, period_start, period_end, baseline_amount_kopiykas, current_amount_kopiykas, change_percent, finding_json}`.
  - [x] 1.2 Ensure the new field is initialized to `[]` in all existing `_make_state()` test helpers (conftest.py + per-agent fixtures) so existing tests don't break on state construction.

- [x] Task 2: Create Alembic migration for `pattern_findings` table (AC: #2)
  - [x] 2.1 Generate a new migration file: `backend/alembic/versions/<hash>_add_pattern_findings_table.py`. Name it with a descriptive slug consistent with the existing convention (e.g., following `s5t6u7v8w9x0_add_flagged_topic_clusters_table.py`).
  - [x] 2.2 `upgrade()` creates the table with columns: `id UUID PRIMARY KEY DEFAULT gen_random_uuid()`, `user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE`, `upload_id UUID NOT NULL REFERENCES uploads(id) ON DELETE CASCADE`, `pattern_type VARCHAR(20) NOT NULL` (check constraint: `('trend', 'anomaly', 'distribution')`), `category VARCHAR(50)`, `period_start DATE`, `period_end DATE`, `baseline_amount_kopiykas BIGINT`, `current_amount_kopiykas BIGINT`, `change_percent FLOAT`, `finding_json JSONB`, `created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`.
  - [x] 2.3 Add indices: `CREATE INDEX ON pattern_findings (user_id)`, `CREATE INDEX ON pattern_findings (upload_id)`.
  - [x] 2.4 `downgrade()` drops the table. Run `alembic upgrade head` locally to confirm the migration applies cleanly.

- [x] Task 3: Create `PatternFinding` SQLModel (AC: #2)
  - [x] 3.1 Create `backend/app/models/pattern_finding.py` following the existing model conventions (`SQLModel, table=True`, `__tablename__ = "pattern_findings"`). Fields map 1-to-1 to the migration schema. `finding_json` uses `sa_column=Column(JSON)`.
  - [x] 3.2 Import `PatternFinding` in `backend/app/models/__init__.py` (check current import pattern in that file).

- [x] Task 4: Create the detector module `detectors/trends.py` (AC: #1, #2, #3)
  - [x] 4.1 Create package: `backend/app/agents/pattern_detection/__init__.py` (empty), `backend/app/agents/pattern_detection/detectors/__init__.py` (empty).
  - [x] 4.2 Create `backend/app/agents/pattern_detection/detectors/trends.py`. This module is **pure Python — no LLM calls**. It receives categorized transactions and returns a list of finding dicts.
  - [x] 4.3 Implement `detect_trends(transactions: list[dict], categorized: list[dict], user_id: str, upload_id: str) -> list[dict]`. The function:
    - Groups transactions by `(year, month, category)` using the transaction `date` field (ISO string `YYYY-MM-DD`).
    - Identifies "current period" as the most recent calendar month in the data; "baseline period" as the month immediately prior.
    - For each category present in both periods: compute `baseline_amount_kopiykas` (sum of absolute amounts), `current_amount_kopiykas`, and `change_percent = (current - baseline) / baseline * 100`.
    - Emits a finding dict with `pattern_type = "trend"` for each category where `abs(change_percent) >= 10` (avoid noise for tiny fluctuations).
    - If fewer than two distinct months exist in the data: skip month-over-month logic entirely, set the period-comparison fields to `None`.
  - [x] 4.4 Implement `detect_anomalies(transactions: list[dict], categorized: list[dict]) -> list[dict]`. For each category, compute the mean and standard deviation of transaction amounts. Flag individual transactions where `amount > mean + 2 * stddev` as anomalies. Emit `pattern_type = "anomaly"` findings with `finding_json = {transaction_id, amount_kopiykas, category_mean_kopiykas}`. Skip categories with fewer than 5 transactions (insufficient sample for stddev).
  - [x] 4.5 Implement `detect_distribution(transactions: list[dict], categorized: list[dict], period_start: str, period_end: str) -> list[dict]`. Compute each category's share of total spending for the current period. Emit `pattern_type = "distribution"` finding per category with `finding_json = {share_percent, total_kopiykas, rank}`. Always runs regardless of how many months of data exist.

- [x] Task 5: Create the LangGraph node `pattern_detection/node.py` (AC: #1, #4, #5)
  - [x] 5.1 Create `backend/app/agents/pattern_detection/node.py`. The node signature mirrors `categorization_node`: `def pattern_detection_node(state: FinancialPipelineState) -> FinancialPipelineState`.
  - [x] 5.2 Early-exit guard: if `state["categorized_transactions"]` is empty, return state unchanged with `pattern_findings = []` and log a warning. Don't block the pipeline.
  - [x] 5.3 Call all three detector functions from `detectors/trends.py`. Combine their outputs into a single `all_findings: list[dict]` list.
  - [x] 5.4 Persist findings to DB in a single `with get_sync_session() as session:` block: for each finding in `all_findings`, create a `PatternFinding` model instance and `session.add()` it, then `session.commit()`. Use the `user_id` and `upload_id` from state.
  - [x] 5.5 Emit SSE progress immediately before returning:
    ```python
    publish_job_progress(job_id, {
        "event": "pipeline-progress",
        "jobId": job_id,
        "step": "pattern-detection",
        "progress": 55,
        "message": "Detecting spending patterns...",
    })
    ```
  - [x] 5.6 Wrap the entire detector + persist block in a broad `try/except Exception`. On failure: log the error with structured context `{"job_id": ..., "user_id": ..., "step": "pattern_detection"}`, append to `state["errors"]`, set `state["failed_node"] = "pattern_detection"` only if no prior `failed_node` exists, and return state with `pattern_findings = []`. **Do NOT re-raise** — pipeline must continue to Education.
  - [x] 5.7 On success: return state with `pattern_findings = all_findings`, `completed_nodes = [*state["completed_nodes"], "pattern_detection"]`.

- [x] Task 6: Wire the node into `pipeline.py` (AC: #4)
  - [x] 6.1 In `backend/app/agents/pipeline.py`, import `pattern_detection_node` from `app.agents.pattern_detection.node`.
  - [x] 6.2 Add `graph.add_node("pattern_detection", pattern_detection_node)`.
  - [x] 6.3 Change the edge from `categorization → education` to `categorization → pattern_detection → education`:
    - Remove `graph.add_edge("categorization", "education")`
    - Add `graph.add_edge("categorization", "pattern_detection")`
    - Add `graph.add_edge("pattern_detection", "education")`
  - [x] 6.4 Rebuild `financial_pipeline = build_pipeline()` at module level — this is unchanged, just verify no import errors after adding the new node.

- [x] Task 7: Emit SSE progress in `processing_tasks.py` (AC: #4)
  - [x] 7.1 In `backend/app/tasks/processing_tasks.py`, confirm the progress step sequence. Currently: `ingestion (10%) → categorization (30%) → insights (70%) → complete (100%)`. Adjust to insert `pattern-detection (55%)` between categorization and the education/insights step. Verify final progress values still reach 100% at job completion.
  - [x] 7.2 The SSE publish inside the node (Task 5.5) handles the in-node emission. The Celery task wrapper only needs to confirm the step labels remain consistent (e.g., no duplicate step names).

- [x] Task 8: Write tests for the pattern detection node (AC: #1–#5)
  - [x] 8.1 Create `backend/tests/agents/test_pattern_detection.py`. Use the existing test patterns from `test_categorization.py` (sync SQLite, `StaticPool`, `_make_state()` helper, `fake_redis` autouse fixture from conftest).
  - [x] 8.2 **Test: intra-period only (single month).** Provide transactions all within one calendar month. Assert `pattern_type = "distribution"` findings are produced; no `"trend"` findings (baseline missing); function returns without error.
  - [x] 8.3 **Test: month-over-month trend detected.** Provide two months of transactions with a category rising > 10%. Assert a `"trend"` finding with correct `change_percent` is returned.
  - [x] 8.4 **Test: anomaly detection.** Provide 6+ transactions in the same category where one is 3× the mean. Assert one `"anomaly"` finding for that transaction.
  - [x] 8.5 **Test: below-sample-size threshold.** Provide fewer than 5 transactions in a category. Assert no `"anomaly"` findings for that category (insufficient sample guard).
  - [x] 8.6 **Test: empty categorized_transactions early exit.** Pass `state` with `categorized_transactions = []`. Assert `pattern_findings = []` returned, no DB writes, pipeline state returned intact.
  - [x] 8.7 **Test: unhandled exception in detectors doesn't crash pipeline.** Patch one detector to raise `RuntimeError`. Assert `pattern_detection_node` returns state (not raises), `failed_node = "pattern_detection"`, `"pattern_detection"` NOT in `completed_nodes`, Education node can still run.
  - [x] 8.8 **Test: findings persisted to DB.** Use a real SQLite session. After `pattern_detection_node(state)`, query `pattern_findings` by `upload_id` and assert the expected rows exist.

## Dev Notes

### What This Story Is (and Isn't)

Story 8.1 is **purely backend** — no frontend changes, no new API endpoints. It inserts a new LangGraph node between Categorization and Education and backs it with a new DB table. Subscription detection (`detectors/recurring.py`) belongs to **Story 8.2** and must NOT be implemented here, even though the epic's AC mentions it. The Triage Agent (8.3) that will consume `pattern_findings` for severity scoring is also deferred — for now, Education receives the pattern findings in state but does not use them (they are persisted to DB for Triage to query in 8.3).

### Current Pipeline State (Before This Story)

```
categorization_node → education_node → END
```

Pipeline file: [backend/app/agents/pipeline.py](backend/app/agents/pipeline.py)

After this story:

```
categorization_node → pattern_detection_node → education_node → END
```

### No LLM Required for Pattern Detection

Unlike the Categorization and Education nodes, the Pattern Detection node uses **pure statistical computation** — no LLM calls. This is intentional: trends, anomalies, and distribution are deterministic math over numeric amounts. This keeps the node fast (target: < 5 seconds for 500 transactions) and removes LLM failure modes from the critical path.

### State Extensions

Add to `FinancialPipelineState` in [backend/app/agents/state.py](backend/app/agents/state.py):

```python
pattern_findings: list[dict]  # output of pattern_detection_node; each dict is a finding row
```

Each finding dict shape (mirrors the DB row):
```python
{
    "pattern_type": "trend" | "anomaly" | "distribution",
    "category": str | None,
    "period_start": str | None,   # ISO date YYYY-MM-DD
    "period_end": str | None,     # ISO date YYYY-MM-DD
    "baseline_amount_kopiykas": int | None,
    "current_amount_kopiykas": int | None,
    "change_percent": float | None,
    "finding_json": dict,
}
```

### Transaction Amount Convention

**Critical:** All transaction `amount` values are stored as integer kopiykas (1 UAH = 100 kopiykas). Negative amounts are debits (spending). When summing spending for a category, use `abs(amount)` for outflows only. Filter `amount < 0` to isolate spending transactions; skip income (amount > 0) for trend/anomaly analysis.

From [backend/app/models/transaction.py](backend/app/models/transaction.py):
```python
amount: int  # Integer kopiykas (-15050 = -150.50 UAH)
```

### Categorized Transaction Dict Shape

The `categorized_transactions` in state (output from categorization_node) is a list of:
```python
{
    "transaction_id": str (UUID),
    "category": str,       # e.g. "food", "transport", "shopping"
    "confidence_score": float,
    "flagged": bool,
    "uncategorized_reason": str | None,
}
```

The raw `transactions` list (also in state) has the original fields including `amount` and `date`:
```python
{
    "id": str (UUID),
    "date": str,           # YYYY-MM-DD
    "description": str,
    "mcc": int | None,
    "amount": int,         # kopiykas, negative = debit
}
```

To get a transaction's category and amount together, join on `transaction_id == id`.

### Migration Naming Convention

Existing migrations follow the pattern: `<8char_alphanum_id>_<slug>.py`. The last migration is `s5t6u7v8w9x0_add_flagged_topic_clusters_table.py`. Generate a new random prefix that doesn't collide. Run `alembic revision --autogenerate -m "add_pattern_findings_table"` to get a real revision ID, then edit the generated file to match the spec in Task 2.2.

### Node Error Handling Pattern

Follow the same pattern as other nodes — broad except, log, mark failed_node, return state:

```python
try:
    all_findings = detect_trends(...) + detect_anomalies(...) + detect_distribution(...)
    # persist to DB...
    return {**state, "pattern_findings": all_findings, "completed_nodes": [...]}
except Exception as exc:
    logger.error(
        "Pattern detection failed",
        extra={"job_id": job_id, "user_id": user_id, "error": str(exc)},
    )
    state["errors"].append({"step": "pattern_detection", "error_code": "DETECTION_FAILED", "message": str(exc)})
    return {**state, "pattern_findings": [], "failed_node": state.get("failed_node") or "pattern_detection"}
```

### SSE Progress Sequence (After This Story)

| Step | `step` value | `progress` | `message` |
|---|---|---|---|
| File parse | `"ingestion"` | 10 | "Reading transactions..." |
| AI categorization | `"categorization"` | 30 | "Categorizing transactions..." |
| Pattern detection | `"pattern-detection"` | 55 | "Detecting spending patterns..." |
| Education cards | `"insights"` | 70 | "Generating insights..." |
| Done | `"complete"` | 100 | "Done" |

### File Structure (New Files)

```
backend/app/agents/
└── pattern_detection/
    ├── __init__.py                  ← new (empty)
    ├── node.py                      ← new (LangGraph node)
    └── detectors/
        ├── __init__.py              ← new (empty)
        └── trends.py                ← new (statistical detectors)

backend/app/models/
└── pattern_finding.py              ← new (SQLModel)

backend/alembic/versions/
└── <hash>_add_pattern_findings_table.py  ← new (Alembic migration)

backend/tests/agents/
└── test_pattern_detection.py       ← new (unit tests)
```

**Modified files:**
- `backend/app/agents/state.py` — add `pattern_findings` field
- `backend/app/agents/pipeline.py` — insert pattern_detection node
- `backend/app/models/__init__.py` — import PatternFinding
- `backend/app/tasks/processing_tasks.py` — update progress percentages if needed

### Testing Standards

- Sync SQLite + `StaticPool` (same as categorization tests) — no async, no Postgres needed for unit tests
- `fake_redis` autouse fixture from `backend/tests/conftest.py` handles `publish_job_progress` automatically — no extra mocking needed
- No LLM mocking needed (this node has no LLM calls)
- For DB persistence test (Task 8.8): use `sync_engine` fixture to verify `PatternFinding` rows are created

### Performance Constraint (NFR4)

The full pipeline must complete within 60 seconds for 200–500 transactions. Pattern detection is pure Python math — it should run in < 2 seconds for 500 transactions. If the detector logic becomes slow, profile `detect_anomalies` first (the O(n) per-category stddev computation). Use `collections.defaultdict` grouping, not repeated list scans.

### Project Structure Notes

- Alignment: new `pattern_detection/` package mirrors `categorization/` and `education/` naming and layout.
- The `detectors/` subfolder is intentional: Story 8.2 will add `detectors/recurring.py` in the same package without touching `node.py` or `trends.py`.
- Do **not** add any frontend files — the Education node already produces insight cards from whatever is in state; pattern findings flow through DB to the Triage node (Story 8.3) and eventually surface as severity-ranked cards.

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story 8.1] — User story and all 5 acceptance criteria (verbatim source)
- [Source: backend/app/agents/pipeline.py](backend/app/agents/pipeline.py) — Current graph wiring to modify
- [Source: backend/app/agents/state.py](backend/app/agents/state.py) — FinancialPipelineState to extend
- [Source: backend/app/agents/categorization/node.py](backend/app/agents/categorization/node.py) — Node signature, error handling, and state return pattern to mirror
- [Source: backend/app/agents/llm.py](backend/app/agents/llm.py) — LLM client factory (not used in this story, but referenced for consistency)
- [Source: backend/app/models/transaction.py](backend/app/models/transaction.py) — Amount is kopiykas int; negative = debit
- [Source: backend/alembic/versions/s5t6u7v8w9x0_add_flagged_topic_clusters_table.py] — Migration naming and structure convention
- [Source: backend/tests/agents/test_categorization.py] — Test fixtures and mocking patterns to mirror
- [Source: backend/tests/conftest.py] — `fake_redis`, `mock_checkpointer`, `celery_memory_backend` autouse fixtures
- [Source: backend/app/core/redis.py] — `publish_job_progress()` signature and payload shape
- [Source: backend/app/tasks/processing_tasks.py] — Celery task progress step labels and percentages to keep consistent
- [Source: _bmad-output/implementation-artifacts/7-9-celery-beat-scheduler-deployment.md] — Previous story; no learnings relevant to this story (pure infra, no overlap)

## Dev Agent Record

### Agent Model Used

claude-opus-4-7[1m]

### Debug Log References

- Alembic migration initially conflicted with existing head `3f046f0dbf8a`; rebased `down_revision` to that head to restore a single linear history (detected via `tests/test_tenant_isolation.py::test_alembic_config_loads_correctly`).

### Completion Notes List

- Full pipeline rewired: `categorization → pattern_detection → education` in `backend/app/agents/pipeline.py`.
- Pattern detectors are pure statistical Python (mean + 2·stddev anomalies, ≥10% month-over-month trend threshold, share-of-total distribution). Income (amount ≥ 0) and `uncategorized` rows are excluded.
- `pattern_detection_node` early-exits with `pattern_findings=[]` when `categorized_transactions` is empty, marks itself completed, and never re-raises on failure (pipeline always reaches Education; failures recorded in `state.errors` and `state.failed_node`).
- SSE progress sequence now emits `pattern-detection` at 55% between categorization (40%) and education (80%); the step label is unique and monotonic.
- All 583 backend tests pass; 14 new tests added covering the node plus each detector's happy path, sample-size guard, income filter, and DB persistence.
- Version bumped 1.14.1 → 1.15.0 (MINOR — user-facing SSE step + new persisted findings).

### File List

**New files:**
- `backend/app/agents/pattern_detection/__init__.py`
- `backend/app/agents/pattern_detection/node.py`
- `backend/app/agents/pattern_detection/detectors/__init__.py`
- `backend/app/agents/pattern_detection/detectors/trends.py`
- `backend/app/models/pattern_finding.py`
- `backend/alembic/versions/t6u7v8w9x0y1_add_pattern_findings_table.py`
- `backend/tests/agents/test_pattern_detection.py`

**Modified files:**
- `backend/app/agents/state.py`
- `backend/app/agents/pipeline.py`
- `backend/app/models/__init__.py`
- `backend/app/tasks/processing_tasks.py`
- `backend/tests/agents/test_categorization.py`
- `backend/tests/agents/test_education.py`
- `backend/tests/test_pipeline_checkpointing.py`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`
- `VERSION`

## Change Log

- 2026-04-17 — Added Pattern Detection agent (Story 8.1): new LangGraph node between categorization and education, new `pattern_findings` table, three pure statistical detectors (trend/anomaly/distribution), and 14 tests. Pipeline flow is now `categorization → pattern_detection → education`.
- 2026-04-17 — Version bumped from 1.14.1 to 1.15.0 per story completion (MINOR — new user-facing SSE pattern-detection step).
- 2026-04-18 — Code review fixes:
  - **H1 (AC #2):** `finding_json` column switched from `sa.JSON()` to `postgresql.JSONB()` in the migration; model keeps `Column(JSON)` for SQLite test compat (existing project pattern from `FinancialHealthScore`).
  - **H2:** `publish_job_progress` moved out of the persist try/except in `pattern_detection_node`. Redis outages can no longer drop findings from state after the DB commit; new regression test added.
  - **M1 (Task 7.1 rework):** Dropped the duplicate `"Categorization complete"` at progress=60 that fired after pattern-detection's 55% publish. `education` step renamed to `insights` and dropped to `progress=70` to match the Dev Notes SSE table. Net client sequence: 10 → 30 → 40 → 55 → 70 → 90 → 92 → 100.
  - **M2:** Removed dead `user_id`, `upload_id` parameters from `detect_trends`.
  - **M3:** Removed dead `period_start`, `period_end` parameters from `detect_distribution`.
  - **M5:** Added `test_pattern_detection_node_sse_publish_failure_does_not_drop_findings` (15 total pattern-detection tests; 98 backend tests green).
  - **Deferred to tech-debt register:** M4 (naive datetime into `TIMESTAMPTZ`) covered by existing [TD-016](../../docs/tech-debt.md); L3 (duplicated `_make_state` helpers) → [TD-030](../../docs/tech-debt.md); L6 (population vs sample variance in `detect_anomalies`) → [TD-031](../../docs/tech-debt.md). L1, L2, L4, L5 dropped as resolved or cosmetic.
