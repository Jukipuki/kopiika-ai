# Story 3.1: Transaction Categorization Agent

Status: done
Created: 2026-03-29
Epic: 3 - AI-Powered Financial Insights & Teaching Feed

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **user**,
I want my transactions automatically categorized into spending categories,
so that I can understand where my money goes.

## Acceptance Criteria

1. **Given** the Ingestion Agent has extracted structured transactions, **When** the Categorization Agent (LangGraph node) processes them, **Then** each transaction is classified into a spending category using MCC codes and LLM-based analysis

2. **Given** a transaction with a clear MCC code (e.g., 5411 = Grocery Stores), **When** categorization runs, **Then** the MCC code is used as the primary signal, with LLM refining the category based on description context

3. **Given** a transaction with no MCC code or an ambiguous one, **When** the LLM categorizes it, **Then** a category is assigned with a confidence score, and low-confidence categorizations are flagged (flagged = confidence < 0.7)

4. **Given** a batch of 200-500 transactions, **When** the Categorization Agent completes, **Then** categorized transactions are persisted to PostgreSQL with `category`, `confidence_score`, and the pipeline state is checkpointed in `processing_jobs.result_data`

5. **Given** the LLM API call fails, **When** the retry mechanism activates, **Then** it retries with exponential backoff (2s, 4s, 8s), falls back to secondary LLM if primary fails after 3 retries, and logs token usage for cost tracking

## Tasks / Subtasks

- [x] Task 1: Add LangGraph + Anthropic dependencies (AC: all)
  - [x] 1.1 Add `langgraph>=0.2.0`, `langchain-anthropic>=0.3.0`, `langchain-openai>=0.3.0`, `langchain-core>=0.3.0` to `backend/pyproject.toml` dependencies (`tenacity` is a transitive dep of `langchain-core` — no need to add separately)
  - [x] 1.2 Run `uv sync` in `backend/` to install new packages (venv is at `backend/.venv`)
  - [x] 1.3 Add to `backend/app/core/config.py` inside `Settings` class (note: `extra="ignore"` already set so no explosion, but explicit fields are preferred):
    ```python
    ANTHROPIC_API_KEY: Optional[str] = None
    OPENAI_API_KEY: Optional[str] = None
    CATEGORIZATION_CONFIDENCE_THRESHOLD: float = 0.7  # flag if below this
    CATEGORIZATION_BATCH_SIZE: int = 50               # transactions per LLM call
    ```

- [x] Task 2: Create `FinancialPipelineState` TypedDict (AC: #4)
  - [x] 2.1 Create `backend/app/agents/state.py` with `FinancialPipelineState(TypedDict)`:
    ```python
    class FinancialPipelineState(TypedDict):
        job_id: str
        user_id: str
        upload_id: str
        transactions: list[dict]           # list of transaction dicts (id, date, description, mcc, amount)
        categorized_transactions: list[dict]  # list of {transaction_id, category, confidence_score, flagged}
        errors: list[dict]                 # list of {step, error_code, message}
        step: str                          # current pipeline step name
        total_tokens_used: int             # LLM token tracking
    ```
  - [x] 2.2 Create `backend/app/agents/__init__.py` (keep empty, module marker) — already existed

- [x] Task 3: Create MCC code → category mapping (AC: #1, #2)
  - [x] 3.1 Create `backend/app/agents/categorization/mcc_mapping.py` — comprehensive dict `MCC_TO_CATEGORY: dict[int, str]` mapping MCC codes to category names
  - [x] 3.2 Categories to use: `"groceries"`, `"restaurants"`, `"transport"`, `"entertainment"`, `"utilities"`, `"healthcare"`, `"shopping"`, `"travel"`, `"education"`, `"finance"`, `"subscriptions"`, `"fuel"`, `"atm_cash"`, `"government"`, `"other"`
  - [x] 3.3 Include at minimum these mappings (all required codes present)
  - [x] 3.4 Add helper `get_mcc_category(mcc: int | None) -> str | None` function

- [x] Task 4: Create Categorization Agent node (AC: #1, #2, #3, #5)
  - [x] 4.1 Create `backend/app/agents/categorization/__init__.py` (empty)
  - [x] 4.2 Create `backend/app/agents/categorization/node.py` with `categorization_node`
  - [x] 4.3 Implement `_get_llm_client()` — primary ChatAnthropic(claude-haiku-4-5-20251001); raises ValueError if key missing
  - [x] 4.4 Implement `_get_fallback_llm_client()` — fallback ChatOpenAI(gpt-4o-mini); raises ValueError if key missing
  - [x] 4.5 Implement `_categorize_batch()` with structured prompt + tenacity retry (stop_after_attempt(3), wait_exponential multiplier=2 min=2 max=8)
  - [x] 4.6 Implement fallback chain: primary LLM → fallback LLM → category="other" confidence=0.0 flagged=True
  - [x] 4.7 Track token usage: accumulate `total_tokens_used` from `response.usage_metadata["total_tokens"]`
  - [x] 4.8 Log all LLM calls with structured JSON

- [x] Task 5: Create LangGraph pipeline (AC: #4)
  - [x] 5.1 Create `backend/app/agents/pipeline.py` with `build_pipeline()` and `financial_pipeline`
  - [x] 5.2 Pipeline is intentionally minimal — categorization node only; future nodes added in Stories 3.x

- [x] Task 6: Alembic migration — add categorization columns to transactions (AC: #4)
  - [x] 6.1 Create migration `f2a4b6c8d0e1` adding `category`, `confidence_score`, `is_flagged_for_review` to transactions
  - [x] 6.2 Add index `ix_transactions_category` on `(user_id, category)`
  - [x] 6.3 Update `Transaction` SQLModel with new fields

- [x] Task 7: Extend Celery task to run categorization (AC: #4, #5)
  - [x] 7.1 Extended `process_upload` to build pipeline state, call `financial_pipeline.invoke()`, bulk-update transactions
  - [x] 7.2 SSE progress events: progress=40 before categorization, progress=70 after
  - [x] 7.3 Categorization failure sets step="categorization_failed" but keeps status="completed"
  - [x] 7.4 Add `total_tokens_used`, `categorization_count`, `flagged_count_categorization` to `result_data`

- [x] Task 8: Backend tests (AC: all)
  - [x] 8.1 Create `backend/tests/agents/test_categorization.py` with 22 tests covering all requirements
  - [x] 8.2 Create `backend/tests/agents/__init__.py`
  - [x] 8.3 Test pipeline integration: `financial_pipeline.invoke(state)` end-to-end
  - [x] 8.4 Test DB update: transactions correctly updated with category/confidence
  - [x] 8.5 Test categorization failure path: job stays "completed"
  - [x] 8.6 Regression: 181 of 181 non-Redis-infra tests pass; 13 pre-existing Redis failures unchanged

## Dev Notes

### Critical Architecture Compliance

**Tech Stack (MUST use exactly — no substitutions):**
- Backend: Python 3.12, FastAPI, SQLModel, Celery 5.x, Redis 7.x, Alembic
- New AI libs to add: `langgraph>=0.2.0`, `langchain-anthropic>=0.3.0`, `langchain-openai>=0.3.0`, `langchain-core>=0.3.0`
- Primary LLM: `claude-haiku-4-5-20251001` via `langchain-anthropic` (`ChatAnthropic`)
- Fallback LLM: `gpt-4o-mini` via `langchain-openai` (`ChatOpenAI`)
- LangGraph StateGraph for pipeline orchestration (NOT LangChain LCEL chains)
- ORM: SQLModel (SQLAlchemy 2.x + Pydantic v2) — DO NOT use raw psycopg2 for updates

**Backend Component Dependency Rules (MUST follow):**
| Layer | Can Depend On | NEVER Depends On |
|---|---|---|
| `api/` | `core/`, `models/`, `services/` | `agents/`, `tasks/` |
| `services/` | `core/`, `models/` | `api/`, `tasks/` |
| `tasks/` | `core/`, `services/`, `agents/` | `api/` |
| `agents/` | `core/`, `models/` | `api/`, `tasks/`, `services/` |

**Data Format Rules:**
- Money: Integer kopiykas (e.g., `-95000` = -950.00 UAH) — do NOT convert to float in prompts; convert to readable `f"{amount/100:.2f} UAH"` for LLM context only
- `confidence_score`: Python `float` 0.0–1.0 stored as PostgreSQL FLOAT
- `category`: lowercase snake_case string values from the defined set (see Task 3.2)

### Critical Finding: New Dependencies NOT Yet Installed

LangGraph, langchain-anthropic, and langchain-openai are **NOT in `pyproject.toml` and NOT installed**. Task 1 must be done first. The `uv sync` step in backend/ installs into `backend/.venv`.

To verify installation: `cd backend && source .venv/bin/activate && python -c "import langgraph; print(langgraph.__version__)"`

### Categorization Strategy (Architecture-Mandated)

**Two-pass approach:**
1. **MCC Pass** (synchronous, no LLM): Check `mcc_mapping.py`. If MCC maps → assign category + confidence=1.0. Fast, free, covers ~60% of transactions.
2. **LLM Pass** (async batched): Remaining transactions batched 50/call → LLM assigns category + confidence. Batch size 50 chosen to stay within ~4K token context window for claude-haiku.

**LLM Prompt Structure for Batch Classification:**
```
You are a financial transaction categorizer for Ukrainian bank statements.
Categorize each transaction into EXACTLY ONE of these categories:
groceries, restaurants, transport, entertainment, utilities, healthcare,
shopping, travel, education, finance, subscriptions, fuel, atm_cash, government, other

Transactions (amounts in UAH):
1. [uuid-1] "СІЛЬПО Kyiv" -245.50 UAH
2. [uuid-2] "АТБ Маркет" -189.00 UAH
...

Return ONLY a JSON array:
[{"id": "uuid-1", "category": "groceries", "confidence": 0.97}, ...]
```

**Why claude-haiku-4-5-20251001 (not claude-sonnet-4-6):** Categorization is a structured classification task, not complex reasoning. Haiku is 10x cheaper and fast enough. Use the model ID exactly: `"claude-haiku-4-5-20251001"`.

### Pipeline State Design

The `FinancialPipelineState` TypedDict in `state.py` is the single source of truth flowing through ALL LangGraph nodes. Design it carefully because Pattern Detection, Triage, and Education agents (Stories 3.x) will ADD fields to it — don't design it too narrowly.

Current story only populates `categorized_transactions` — future stories will add `patterns`, `insights`, `triage_scores`, etc.

### Key LangGraph Patterns

```python
# Building the graph (pipeline.py)
from langgraph.graph import StateGraph, END

graph = StateGraph(FinancialPipelineState)
graph.add_node("categorization", categorization_node)
graph.set_entry_point("categorization")
graph.add_edge("categorization", END)
pipeline = graph.compile()

# Invoking synchronously (from Celery task)
result_state = pipeline.invoke(initial_state)
```

LangGraph `.invoke()` is synchronous and safe to call from a Celery task. Do NOT use `.ainvoke()` from a Celery worker context (Celery workers are sync).

### Celery Task Integration Pattern

The existing `process_upload()` in `processing_tasks.py` currently: downloads S3 → parses → stores transactions. Story 3.1 extends it with a categorization step AFTER parsing:

```python
# After sync_parse_and_store_transactions() succeeds:
# 1. Query newly stored transactions from DB
transactions_for_pipeline = session.exec(
    select(Transaction).where(Transaction.upload_id == upload.id)
).all()

# 2. Build initial state
initial_state: FinancialPipelineState = {
    "job_id": job_id,
    "user_id": str(job.user_id),
    "upload_id": str(upload.id),
    "transactions": [
        {"id": str(t.id), "mcc": t.mcc, "description": t.description,
         "amount": t.amount, "date": str(t.date)}
        for t in transactions_for_pipeline
    ],
    "categorized_transactions": [],
    "errors": [],
    "step": "categorization",
    "total_tokens_used": 0,
}

# 3. Run pipeline
result_state = financial_pipeline.invoke(initial_state)

# 4. Bulk-update transactions with categories
for cat in result_state["categorized_transactions"]:
    txn = session.get(Transaction, uuid.UUID(cat["transaction_id"]))
    if txn:
        txn.category = cat["category"]
        txn.confidence_score = cat["confidence_score"]
        txn.is_flagged_for_review = cat["flagged"]
        session.add(txn)
session.commit()
```

**IMPORTANT:** The categorization step runs synchronously inside the existing Celery worker. No new Celery task is needed for Story 3.1.

### DB Bulk Update — Avoid N+1

Build a dict of categorization results keyed by transaction ID, then query all transactions in one call and update them:

```python
# Build lookup dict: {transaction_id_str: {category, confidence_score, flagged}}
cat_lookup = {
    cat["transaction_id"]: cat
    for cat in result_state["categorized_transactions"]
}

# Single query for all transactions in this upload
txns = session.exec(
    select(Transaction).where(Transaction.upload_id == upload.id)
).all()

# Update in-memory, then single commit
for txn in txns:
    cat = cat_lookup.get(str(txn.id))
    if cat:
        txn.category = cat["category"]
        txn.confidence_score = cat["confidence_score"]
        txn.is_flagged_for_review = cat["flagged"]
        session.add(txn)

session.commit()
```

**Why this pattern (not `session.execute(update(Model), [list])`):** SQLModel's `Session` extends SQLAlchemy 2.x but `session.exec()` is the SQLModel-idiomatic way. Batch `update()` with list-of-dicts works with raw SQLAlchemy `Session.execute()` but not `SQLModel.Session.exec()`. The query-then-update pattern is safe here since transactions are already in session context from the earlier parse step.

### Testing Without Real API Keys

**CRITICAL:** Tests MUST mock LLM clients. Do NOT require `ANTHROPIC_API_KEY` to be set for tests to pass.

**Follow the exact pattern from `backend/tests/test_processing_tasks.py`** for sync DB tests:

```python
# Sync engine fixture (copy from test_processing_tasks.py)
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel

@pytest.fixture
def sync_engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    yield engine
    SQLModel.metadata.drop_all(engine)
    engine.dispose()

# LLM mock pattern
from unittest.mock import MagicMock, patch

mock_response = MagicMock()
mock_response.content = '[{"id": "uuid-1", "category": "groceries", "confidence": 0.95}]'
mock_response.usage_metadata = {"total_tokens": 150}

with patch("app.agents.categorization.node._get_llm_client") as mock_get_llm:
    mock_get_llm.return_value.invoke.return_value = mock_response
    result_state = categorization_node(state)
```

Agent tests (in `backend/tests/agents/`) do NOT need `async_session` or the HTTP `client` fixture — they test pure Python functions with sync SQLite sessions.

### Accumulated Learnings from Previous Stories

**DO NOT REPEAT these patterns (from Stories 2.5–2.7):**
1. DateTime: Use `datetime.now(UTC).replace(tzinfo=None)` for SQLite test compatibility (UTC-aware datetimes fail in SQLite)
2. Sync SQLite tests need `StaticPool` (not `NullPool`) to share in-memory DB across the session
3. Celery tasks are SYNCHRONOUS — use `redis.Redis` (sync), NOT `redis.asyncio`
4. Use `get_sync_session()` for all DB access inside Celery tasks
5. `ProcessingJob` initial status after upload is `"validated"` (NOT `"pending"`)
6. Pydantic camelCase: `alias_generator=to_camel, populate_by_name=True` on all API response models
7. Money stored as kopiykas (integer) — never float in DB or API

**Patterns established to REUSE:**
- `get_sync_session()` from `backend/app/core/database.py` — use for all DB access in Celery task
- `publish_job_progress()` from `backend/app/core/redis.py` — reuse for categorization SSE events
- `celery_app.conf.update(task_always_eager=True, task_eager_propagates=True)` in test setup
- Mock S3 via `@patch("app.tasks.processing_tasks.boto3.client")`
- `get_current_user_id` dependency for tenant isolation

**Current test count (baseline to maintain): 194 backend tests, 110 frontend tests — ALL must continue to pass.**

### SSE Progress Events for This Story

After this story, the SSE pipeline progress should reflect:
```json
// Before parsing (existing)
{"event": "pipeline-progress", "jobId": "uuid", "step": "ingestion", "progress": 10, "message": "Reading transactions..."}

// After parsing (existing, updated progress)
{"event": "pipeline-progress", "jobId": "uuid", "step": "ingestion", "progress": 30, "message": "Parsing complete"}

// Before categorization (NEW)
{"event": "pipeline-progress", "jobId": "uuid", "step": "categorization", "progress": 40, "message": "Categorizing 245 transactions..."}

// After categorization (NEW)
{"event": "pipeline-progress", "jobId": "uuid", "step": "categorization", "progress": 70, "message": "Categorization complete"}

// Job complete (existing, updated)
{"event": "job-complete", "jobId": "uuid", "status": "completed", "duplicatesSkipped": 0, "newTransactions": 245, "totalInsights": 0}
```

The frontend `ProcessingPipeline.tsx` already handles `step` values — adding "categorization" step should render correctly with the existing progress display.

### What Does NOT Exist Yet (Must Create)

**New files for this story:**
- `backend/app/agents/state.py` — `FinancialPipelineState` TypedDict
- `backend/app/agents/pipeline.py` — LangGraph StateGraph with categorization node
- `backend/app/agents/categorization/__init__.py`
- `backend/app/agents/categorization/node.py` — categorization agent logic
- `backend/app/agents/categorization/mcc_mapping.py` — MCC → category dict
- `backend/alembic/versions/xxx_add_categorization_fields_to_transactions.py`
- `backend/tests/agents/__init__.py`
- `backend/tests/agents/test_categorization.py`

**Modified files:**
- `backend/pyproject.toml` — add langgraph, langchain-anthropic, langchain-openai
- `backend/app/core/config.py` — add `ANTHROPIC_API_KEY`, `OPENAI_API_KEY` settings
- `backend/app/models/transaction.py` — add `category`, `confidence_score`, `is_flagged_for_review` fields
- `backend/app/tasks/processing_tasks.py` — add categorization step after parsing

**No frontend changes needed for this story** — categorization results are stored in DB; the Teaching Feed UI comes in Story 3.4/3.5.

### Project Structure Notes

- Agent files go in `backend/app/agents/categorization/` — per architecture spec (already the dir structure)
- `state.py` and `pipeline.py` go at `backend/app/agents/` root level (shared across all agents)
- No `pipeline_tasks.py` needed yet — Story 3.1 extends the existing `process_upload` task
- Architecture mentions `pipeline_tasks.py` (a separate Celery task for the full AI pipeline) — this will be created in a later story when the full pipeline is built; for now, categorization is appended to `process_upload`
- Test for agents go in `backend/tests/agents/` — creating the `agents/` subfolder for the first time

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Epic 3, Story 3.1]
- [Source: _bmad-output/planning-artifacts/architecture.md#AI Processing Domain — 5-agent sequential pipeline via LangGraph]
- [Source: _bmad-output/planning-artifacts/architecture.md#Backend Organization — agents/ directory structure]
- [Source: _bmad-output/planning-artifacts/architecture.md#Error Handling — LangGraph pipeline, LLM calls]
- [Source: _bmad-output/planning-artifacts/architecture.md#Data Format Rules — kopiykas, ISO dates]
- [Source: _bmad-output/planning-artifacts/architecture.md#Communication Patterns — SSE event structure]
- [Source: _bmad-output/planning-artifacts/architecture.md#Enforcement Guidelines — logging format, dependency rules]
- [Source: _bmad-output/implementation-artifacts/2-7-multiple-statement-uploads-cumulative-history.md — Previous story learnings (datetime UTC, StaticPool, Celery sync patterns)]

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

No blocking issues encountered. All 22 new tests pass. Pre-existing Redis infrastructure failures (13 tests) unchanged.

### Completion Notes List

- Implemented two-pass categorization: MCC-first (fast/free) then LLM batching (50 tx/call)
- Primary LLM: claude-haiku-4-5-20251001 via langchain-anthropic; fallback: gpt-4o-mini via langchain-openai
- Retry with tenacity exponential backoff: 2s, 4s, 8s (3 attempts max)
- Final fallback on all LLM failures: category="other", confidence=0.0, flagged=True
- Flagging threshold: confidence_score < 0.7 → is_flagged_for_review=True
- Categorization failures keep job status="completed" with step="categorization_failed"
- Token usage tracked in pipeline state and persisted to result_data
- SSE progress: 40% before categorization, 70% after
- DB bulk-update uses query-then-update pattern (SQLModel-idiomatic, avoids N+1)
- 26 tests total: MCC mapping, node logic, fallback chains, DB updates, pipeline integration, batch splitting, Celery task integration
- LLM output category validation added: invalid categories replaced with "other" (VALID_CATEGORIES frozenset in mcc_mapping.py)
- fakeredis fixtures added to conftest.py for Redis isolation across all tests

### File List

- backend/pyproject.toml (modified — added langgraph, langchain-anthropic, langchain-openai, langchain-core)
- backend/app/core/config.py (modified — added ANTHROPIC_API_KEY, OPENAI_API_KEY, CATEGORIZATION_CONFIDENCE_THRESHOLD, CATEGORIZATION_BATCH_SIZE)
- backend/app/agents/state.py (created — FinancialPipelineState TypedDict)
- backend/app/agents/pipeline.py (created — LangGraph StateGraph with categorization node)
- backend/app/agents/categorization/__init__.py (created — empty module marker)
- backend/app/agents/categorization/node.py (created — categorization_node with MCC+LLM+fallback logic)
- backend/app/agents/categorization/mcc_mapping.py (created — MCC_TO_CATEGORY dict + get_mcc_category helper)
- backend/alembic/versions/f2a4b6c8d0e1_add_categorization_fields_to_transactions.py (created — migration)
- backend/app/models/transaction.py (modified — added category, confidence_score, is_flagged_for_review)
- backend/app/tasks/processing_tasks.py (modified — categorization pipeline step after parsing)
- backend/tests/agents/__init__.py (created — empty module marker)
- backend/tests/agents/test_categorization.py (created — 26 tests)
- backend/tests/conftest.py (modified — added fakeredis session/function fixtures for Redis isolation)
- backend/tests/test_sse_streaming.py (modified — updated SSE event count assertion 3→5 for categorization progress events)

## Change Log

- 2026-03-30: Story 3.1 implemented — Transaction Categorization Agent with LangGraph pipeline, MCC mapping, LLM fallback, Alembic migration, Celery integration, 22 tests added
- 2026-03-30: Code review complete — 4 issues fixed: (H1) LLM category output validation added; (M1) conftest.py and test_sse_streaming.py added to File List; (M2) batch-splitting test added; (M3) real Celery task categorization-failure integration test added; (M4) real pipeline→DB integration test added. Total tests: 26
