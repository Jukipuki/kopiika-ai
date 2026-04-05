# Story 3.8: Adaptive Education Depth

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **user**,
I want the education content adapted to my financial literacy level,
So that I get content that's challenging but not overwhelming.

## Acceptance Criteria

1. **Given** a new user with no prior uploads, **When** the Education Agent generates content, **Then** it defaults to beginner-level explanations with more foundational concepts.

2. **Given** a user who has uploaded 3+ statements AND whose first upload was at least 7 days ago, **When** the Education Agent generates content, **Then** it adjusts content depth to intermediate level with more nuanced insights.

3. **Given** the user's detected literacy level, **When** insight cards are generated, **Then** the headline, "why this matters", and deep-dive layers each reflect the appropriate depth.

## Tasks / Subtasks

- [x] Task 1: Backend — Add `literacy_level` to pipeline state (AC: #1, #2, #3)
  - [x] 1.1 In `backend/app/agents/state.py`, add `literacy_level: str` field to `FinancialPipelineState` (value: `"beginner"` or `"intermediate"`)

- [x] Task 2: Backend — Detect literacy level in processing task (AC: #1, #2)
  - [x] 2.1 In `backend/app/tasks/processing_tasks.py`, after querying `user` for locale (line ~136), query upload count and earliest upload date:
    ```python
    from sqlmodel import func
    from datetime import datetime, timedelta, timezone
    upload_stats = session.exec(
        select(func.count(), func.min(Upload.created_at))
        .where(Upload.user_id == job.user_id)
    ).one()
    upload_count, first_upload_at = upload_stats
    days_since_first = (datetime.now(timezone.utc) - first_upload_at).days if first_upload_at else 0
    literacy_level = "intermediate" if upload_count >= 3 and days_since_first >= 7 else "beginner"
    ```
  - [x] 2.2 Add `literacy_level` to `initial_state` dict passed to `financial_pipeline.invoke()`

- [x] Task 3: Backend — Adaptive prompts for Education Agent (AC: #1, #2, #3)
  - [x] 3.1 In `backend/app/agents/education/prompts.py`, add beginner and intermediate variants for both English and Ukrainian:
    - Beginner: simpler vocabulary, foundational concepts, analogies, avoid jargon
    - Intermediate: nuanced analysis, industry terms defined briefly, actionable strategies
  - [x] 3.2 Update `get_prompt(locale: str)` signature to `get_prompt(locale: str, literacy_level: str = "beginner") -> str`
  - [x] 3.3 Return appropriate prompt based on both `locale` and `literacy_level`

- [x] Task 4: Backend — Pass literacy level through education node (AC: #1, #2, #3)
  - [x] 4.1 In `backend/app/agents/education/node.py`, read `literacy_level` from state: `literacy_level = state.get("literacy_level", "beginner")`
  - [x] 4.2 Pass `literacy_level` to `get_prompt(locale, literacy_level)` call
  - [x] 4.3 Add `"literacy_level": literacy_level` to structured log output

- [x] Task 5: Tests (AC: #1–#3)
  - [x] 5.1 Backend: update `backend/tests/test_processing_tasks.py` — assert `literacy_level` is set to `"beginner"` for first upload, `"beginner"` for 3+ uploads within 7 days, and `"intermediate"` for 3+ uploads with first upload > 7 days ago
  - [x] 5.2 Backend: add unit tests for `get_prompt(locale, literacy_level)` — assert different prompts returned for each combination (en/beginner, en/intermediate, uk/beginner, uk/intermediate)
  - [x] 5.3 Backend: update `education_node` tests — assert `literacy_level` is read from state and passed to prompt
  - [x] 5.4 All 168 pre-existing frontend tests continue passing; all 258 backend tests continue passing

## Dev Notes

### Architecture Overview

**Story 3.8 scope (backend only — no frontend changes):**
- **Backend (4 files):** `state.py` (add field), `processing_tasks.py` (count uploads + time check, set literacy_level), `education/prompts.py` (literacy-aware prompts), `education/node.py` (read literacy_level from state)

**What does NOT change:**
- LangGraph pipeline graph (`pipeline.py`) — state shape change is backward-compatible (TypedDict with default)
- Insight model, API endpoint, or insight service — no changes
- SSE infrastructure — no changes
- All frontend files — no changes (pagination moved to Story 3.9)

### Backend: Literacy Level Detection

**File:** `backend/app/tasks/processing_tasks.py` (line ~136)

**Logic:** Count all `Upload` rows for the user AND check time since first upload. Both conditions must be met to graduate to intermediate:
- Upload count < 3 → "beginner"
- Upload count >= 3 but first upload < 7 days ago → "beginner" (too early to graduate)
- Upload count >= 3 AND first upload >= 7 days ago → "intermediate"

```python
# After: user = session.get(User, job.user_id)
from datetime import datetime, timedelta, timezone
upload_stats = session.exec(
    select(func.count(), func.min(Upload.created_at))
    .where(Upload.user_id == job.user_id)
).one()
upload_count, first_upload_at = upload_stats
days_since_first = (datetime.now(timezone.utc) - first_upload_at).days if first_upload_at else 0
literacy_level = "intermediate" if upload_count >= 3 and days_since_first >= 7 else "beginner"

initial_state: FinancialPipelineState = {
    # ... existing fields ...
    "literacy_level": literacy_level,
}
```

**Import needed:** `from sqlmodel import func` — check if `func` is already imported (it may be via `sqlmodel`). `select` is already imported. `Upload` model import needed for the query.

**Note on engagement tracking:** The epics mention "expanded deep-dive layers" as an engagement signal, but no analytics/event table exists in the schema. Upload count + time-since-first-upload is the proxy for literacy level in this story. The 7-day minimum ensures users have time to absorb beginner content before graduating. Future stories can add engagement tracking for finer-grained detection.

### Backend: State Change

**File:** `backend/app/agents/state.py`

```python
class FinancialPipelineState(TypedDict):
    job_id: str
    user_id: str
    upload_id: str
    transactions: list[dict]
    categorized_transactions: list[dict]
    errors: list[dict]
    step: str
    total_tokens_used: int
    locale: str
    insight_cards: list[dict]
    literacy_level: str  # NEW: "beginner" or "intermediate"
```

`TypedDict` fields are required by default, but `state.get("literacy_level", "beginner")` in the education node is safe as a fallback. Python `TypedDict` at runtime is just a dict — `get()` with a default works fine.

### Backend: Adaptive Prompts

**File:** `backend/app/agents/education/prompts.py`

Add 4 prompt templates: English/beginner, English/intermediate, Ukrainian/beginner, Ukrainian/intermediate.

**Beginner prompt guidance to include:**
- "Explain concepts simply, as if to someone new to personal finance"
- "Avoid jargon; when financial terms are needed, define them briefly"
- "Focus on foundational habits: budgeting basics, understanding where money goes"
- "Use encouraging, supportive tone"

**Intermediate prompt guidance to include:**
- "The user has experience with their finances; use precise financial terminology"
- "Focus on optimization strategies, trend analysis, and comparative insights"
- "Reference strategies like 50/30/20 budgeting, savings rate, category ratios"
- "Be direct and analytical; skip basic definitions"

```python
def get_prompt(locale: str, literacy_level: str = "beginner") -> str:
    if locale == "en":
        return ENGLISH_INTERMEDIATE_PROMPT if literacy_level == "intermediate" else ENGLISH_BEGINNER_PROMPT
    return UKRAINIAN_INTERMEDIATE_PROMPT if literacy_level == "intermediate" else UKRAINIAN_BEGINNER_PROMPT
```

Rename existing `ENGLISH_PROMPT` → `ENGLISH_BEGINNER_PROMPT`, `UKRAINIAN_PROMPT` → `UKRAINIAN_BEGINNER_PROMPT`. The existing prompts are already beginner-appropriate.

### Backend: Education Node Change

**File:** `backend/app/agents/education/node.py`

```python
def education_node(state: FinancialPipelineState) -> FinancialPipelineState:
    try:
        # ... existing setup ...
        locale = state.get("locale", "uk")
        literacy_level = state.get("literacy_level", "beginner")  # NEW
        
        # ... RAG retrieval unchanged ...
        
        prompt_template = get_prompt(locale, literacy_level)  # UPDATED
        prompt = prompt_template.format(
            user_context=spending_summary,
            rag_context=rag_context if rag_context else "No educational content available.",
        )
        
        # ... LLM call unchanged ...
        
        logger.info(
            '{"level": "INFO", "step": "education", "cards_generated": %d, "locale": "%s", "literacy_level": "%s"}',
            len(cards), locale, literacy_level,
        )
```

### Previous Story Intelligence (Story 3.7)

- 168 frontend tests passing (20 test files), 258 backend tests passing (from code review completion)
- Education agent pipeline runs as part of LangGraph `financial_pipeline` invoked from Celery task

### Git Intelligence

- `c7ba5ab Story 3.7: Progressive Card Appearance & SSE Integration` — established `useFeedSSE`, `ProgressiveLoadingState`, `FeedContainer` jobId wiring
- `170964f Story 3.6: Card Stack Navigation & Gestures` — `CardStackNavigator` with keyboard + drag navigation, swipe gestures
- `2d4da52 Story 3.5: Teaching Feed Card UI & Progressive Disclosure` — `InsightCard`, `EducationLayer`, `TriageBadge` components

### Project Structure Notes

- **Alignment with unified structure:** All changes follow existing patterns
  - Backend: new field in TypedDict, new import via `sqlmodel.func`, extending prompts module
  - No frontend changes in this story (pagination moved to Story 3.9)

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story 3.8] — acceptance criteria, story statement (line 795)
- [Source: _bmad-output/planning-artifacts/epics.md] — FR17: Adapt education depth to literacy level
- [Source: backend/app/agents/state.py] — `FinancialPipelineState` TypedDict to extend
- [Source: backend/app/agents/education/node.py] — `education_node` function to update
- [Source: backend/app/agents/education/prompts.py] — `get_prompt()` to extend with literacy level
- [Source: backend/app/tasks/processing_tasks.py#136] — user/locale lookup; add upload count + time check + literacy_level here
- [Source: backend/app/models/upload.py] — `Upload` model with `user_id` FK and `created_at` for counting and time check
- [Source: _bmad-output/implementation-artifacts/3-7-progressive-card-appearance-sse-integration.md#Completion Notes] — test baselines: 168 frontend, 258 backend

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

### Completion Notes List

- All 5 tasks implemented: state field, literacy detection, adaptive prompts, node passthrough, tests
- Literacy level detected from upload count (>=3) AND time since first upload (>=7 days)
- 4 prompt variants created: EN/UK × beginner/intermediate
- Education node reads literacy_level with "beginner" fallback for backward compatibility
- 15 new tests added (6 prompt tests, 5 education node tests, 4 processing task tests)
- All 273 backend tests pass (258 pre-existing + 15 new), all 168 frontend tests pass
- No frontend changes required (as specified in story)

### Change Log

- 2026-04-05: Implemented adaptive education depth — literacy_level field, detection logic, bilingual adaptive prompts, education node integration, 12 new tests
- 2026-04-05: Code review fixes — consistent naive-UTC datetime in literacy detection, 7-day boundary test, intermediate prompt end-to-end test, log verification test, duplicate section header cleanup, registered pytest.mark.slow marker

### File List

- backend/app/agents/state.py (modified — added literacy_level field)
- backend/app/tasks/processing_tasks.py (modified — added upload count/time query, literacy_level detection, passed to initial_state)
- backend/app/agents/education/prompts.py (modified — renamed prompts to beginner variants, added intermediate variants for EN/UK, updated get_prompt signature)
- backend/app/agents/education/node.py (modified — reads literacy_level from state, passes to get_prompt, added to structured log)
- backend/tests/agents/test_education.py (modified — added 9 new tests for prompts and node literacy handling)
- backend/tests/test_processing_tasks.py (modified — added 3 new tests for literacy level detection)
