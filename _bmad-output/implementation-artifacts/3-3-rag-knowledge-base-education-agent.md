# Story 3.3: RAG Knowledge Base & Education Agent

Status: done
Created: 2026-04-04
Epic: 3 - AI-Powered Financial Insights & Teaching Feed

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **user**,
I want to receive personalized financial education based on my spending data,
so that I learn about my finances, not just see numbers.

## Acceptance Criteria

1. **Given** the RAG knowledge base, **When** it is initialized, **Then** 20-30 core financial literacy concepts are embedded using OpenAI `text-embedding-3-small` (1536 dimensions) and stored in pgvector (creating the `embeddings` table via Alembic migration)

2. **Given** categorized transaction data for a user, **When** the Education Agent (LangGraph node) runs, **Then** it retrieves relevant financial education content via RAG and generates personalized insight cards combining the user's data with educational context

3. **Given** a user with language preference set to Ukrainian, **When** the Education Agent generates content, **Then** the content is generated in Ukrainian using bilingual LLM prompts

4. **Given** a user with language preference set to English, **When** the Education Agent generates content, **Then** the content is generated in English

5. **Given** the RAG retrieval or Education Agent fails, **When** graceful degradation activates, **Then** the system displays categorized data without education layers rather than showing nothing (NFR28)

## Tasks / Subtasks

- [x] Task 1: Create RAG infrastructure — embeddings service (AC: #1)
  - [x] 1.1 Add `pgvector>=0.3.0` to `pyproject.toml` dependencies (OpenAI SDK already present via `langchain-openai`)
  - [x] 1.2 Create `backend/app/rag/embeddings.py` — thin wrapper around OpenAI `text-embedding-3-small` API: `embed_text(text: str) -> list[float]` and `embed_batch(texts: list[str]) -> list[list[float]]` using the existing `OPENAI_API_KEY`
  - [x] 1.3 Create `backend/app/rag/__init__.py`

- [x] Task 2: Create `embeddings` DB table via Alembic migration (AC: #1)
  - [x] 2.1 Create `backend/app/models/embedding.py` — `DocumentEmbedding` SQLModel with fields: `id` (UUID PK), `doc_id` (str, the corpus slug, e.g. `en/budgeting-basics`), `language` (str, 'en'|'uk'), `chunk_type` (str, e.g. 'overview'|'key_concepts'|etc.), `content` (str), `embedding` (Vector(1536) via pgvector), `created_at` (datetime). Add unique constraint on `(doc_id, chunk_type)` for upsert idempotency.
  - [x] 2.2 Generate Alembic migration: enable `pgvector` extension + create `document_embeddings` table with `embedding vector(1536)` column and HNSW index (`m=16, ef_construction=64`)
  - [x] 2.3 Add `DocumentEmbedding` to `backend/app/models/__init__.py`

- [x] Task 3: Create RAG retriever (AC: #1, #2)
  - [x] 3.1 Create `backend/app/rag/retriever.py` — `retrieve_relevant_docs(query: str, language: str, top_k: int = 5) -> list[dict]` using cosine similarity via pgvector `<=>` operator with sync SQLAlchemy session (called from Celery worker context)
  - [x] 3.2 The retriever must filter by `language` column to prefer language-matched results, fallback to cross-lingual if <3 results found

- [x] Task 4: Create corpus seeding script (AC: #1)
  - [x] 4.1 Create `backend/app/rag/seed.py` — CLI script (`python -m app.rag.seed`) that reads all `.md` files from `backend/data/rag-corpus/en/` and `backend/data/rag-corpus/uk/`, chunks by H2 section headers, generates BGE-M3 embeddings, and inserts into `document_embeddings` table (idempotent: upsert by `doc_id + chunk_type`)
  - [x] 4.2 Chunking strategy: split each corpus document by `## ` H2 headers, each H2 section becomes one chunk. Section name → `chunk_type`. Full `## SectionName\n...content` → `content` field.
  - [x] 4.3 Add `make seed-rag` target to `backend/Makefile` (or document CLI command in README if Makefile doesn't exist)

- [x] Task 5: Create Education Agent LangGraph node (AC: #2, #3, #4, #5)
  - [x] 5.1 Create `backend/app/agents/education/__init__.py`
  - [x] 5.2 Create `backend/app/agents/education/prompts.py` — bilingual prompt templates for insight card generation: English and Ukrainian versions. Prompt must include `{user_context}` (spending summary) and `{rag_context}` (retrieved docs), produce structured JSON output matching InsightCard schema
  - [x] 5.3 Create `backend/app/agents/education/node.py` — `education_node(state: FinancialPipelineState) -> FinancialPipelineState`:
    - Build a spending summary from `state["categorized_transactions"]` (top 3 categories by spend volume, amounts in UAH)
    - Determine `locale` from `state["locale"]` (default `"uk"` if not present)
    - Call `retrieve_relevant_docs(query=spending_summary, language=locale, top_k=5)`
    - Build prompt using `prompts.py` template
    - Call LLM (same `_get_llm_client()` / `_get_fallback_llm_client()` pattern as categorization node)
    - Parse response into list of `InsightCard` dicts: `{headline, key_metric, why_it_matters, deep_dive, severity, category}`
    - On any failure (retrieval OR LLM), log error and return state with `insight_cards=[]` (graceful degradation — AC #5)
    - Return updated state with `insight_cards` field populated
  - [x] 5.4 Add `locale: str` and `insight_cards: list[dict]` to `FinancialPipelineState` TypedDict in `backend/app/agents/state.py`

- [x] Task 6: Wire Education Agent into pipeline (AC: #2)
  - [x] 6.1 Update `backend/app/agents/pipeline.py` to add `education` node after `categorization`: `graph.add_node("education", education_node)` → `graph.add_edge("categorization", "education")` → `graph.add_edge("education", END)`
  - [x] 6.2 Update the Celery task that invokes the pipeline to pass `locale` from `user.locale` (User model field, default `"uk"`) into the initial state

- [x] Task 7: Persist insight cards to DB (AC: #2)
  - [x] 7.1 Create `backend/app/models/insight.py` — `Insight` SQLModel with fields: `id` (UUID PK), `user_id` (UUID FK → users.id), `upload_id` (UUID FK → uploads.id, nullable), `headline` (str), `key_metric` (str), `why_it_matters` (str), `deep_dive` (str), `severity` (str: 'high'|'medium'|'low'), `category` (str), `created_at` (datetime)
  - [x] 7.2 Create Alembic migration for `insights` table
  - [x] 7.3 Add `Insight` to `backend/app/models/__init__.py`
  - [x] 7.4 After education node runs, persist each InsightCard in the Celery task (same pattern as transaction persistence in story 3.1)

- [x] Task 8: Tests (AC: #1–#5)
  - [x] 8.1 `backend/tests/agents/test_education.py` — unit tests for `education_node`: mock retriever + LLM, verify insight_cards populated; test graceful degradation returns empty list on failure
  - [x] 8.2 `backend/tests/test_rag_retrieval.py` — unit tests for retriever: mock DB session, verify cosine query construction and language filter; verify fallback to cross-lingual
  - [x] 8.3 `backend/tests/test_embeddings.py` — unit test for `embed_text()`: mock OpenAI API call, verify output is list of 1536 floats
  - [x] 8.4 All existing 220 backend tests must continue passing (243 total: 220 existing + 23 new)

## Dev Notes

### Architecture: RAG System Overview

```
Corpus markdown files (backend/data/rag-corpus/)
         ↓  seed.py (one-time + refreshable, calls OpenAI Embeddings API)
document_embeddings table (pgvector, 1536-dim HNSW)
         ↓  retriever.py (cosine similarity, locale filter)
Education Agent node (LangGraph, bilingual LLM prompt)
         ↓
insight_cards in FinancialPipelineState
         ↓
insights table (PostgreSQL)
```

### OpenAI Embedding Model

**Model:** `text-embedding-3-small` via OpenAI API  
**Dimensions:** 1536 (fixed — Alembic migration must use exactly `vector(1536)`)  
**No extra dependencies:** Uses the OpenAI SDK already available via `langchain-openai`. Uses the existing `OPENAI_API_KEY` from settings.  
**Multilingual:** Handles both Ukrainian and English text well. Corpus is already split by language directory, so cross-lingual retrieval is a fallback, not the primary path.

**Why not BGE-M3 (local model)?** BGE-M3 requires `sentence-transformers` which pulls in PyTorch (~4GB container bloat). OpenAI embeddings are lightweight API calls, cost ~$0.02/1M tokens (negligible for ~50 corpus docs + one query per pipeline run), and avoid memory pressure in Celery workers.

**Implementation pattern:**
```python
# backend/app/rag/embeddings.py
from openai import OpenAI
from app.core.config import settings

_client: OpenAI | None = None

def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=settings.OPENAI_API_KEY)
    return _client

def embed_text(text: str) -> list[float]:
    response = _get_client().embeddings.create(
        model="text-embedding-3-small",
        input=text,
    )
    return response.data[0].embedding

def embed_batch(texts: list[str]) -> list[list[float]]:
    response = _get_client().embeddings.create(
        model="text-embedding-3-small",
        input=texts,
    )
    return [item.embedding for item in response.data]
```

**Bedrock migration note:** When migrating to AWS Bedrock post-Epic 3, replace `text-embedding-3-small` with **Amazon Titan Text Embeddings V2** (`amazon.titan-embed-text-v2:0`, 1024 dims). This will require:
- Changing `embeddings.py` to use `langchain-aws` `BedrockEmbeddings` client
- Re-running the seed script to re-embed all corpus docs with the new model
- Updating the Alembic migration to change `vector(1536)` → `vector(1536)` (or create a new migration)
- Updating the HNSW index accordingly

### pgvector Setup

**Extension:** `pgvector` must be enabled in the migration:
```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

**SQLModel/SQLAlchemy column type:**
```python
from pgvector.sqlalchemy import Vector
from sqlalchemy import Column

class DocumentEmbedding(SQLModel, table=True):
    __tablename__ = "document_embeddings"
    embedding: list[float] = Field(sa_column=Column(Vector(1536)))
```

**Add to `pyproject.toml` dependencies:**
- `pgvector>=0.3.0` (Python pgvector client, provides `pgvector.sqlalchemy.Vector`)
- `openai` SDK already available via `langchain-openai` — no new dependency needed for embeddings

**HNSW index** for fast approximate nearest-neighbor search:
```sql
CREATE INDEX ON document_embeddings USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);
```

**Retrieval query pattern (pgvector cosine similarity):**
```python
# In retriever.py — uses sync session (Celery context)
from pgvector.sqlalchemy import Vector
from sqlalchemy import text

query_embedding = embed_text(query)
results = session.execute(
    text("""
        SELECT doc_id, language, chunk_type, content,
               1 - (embedding <=> :embedding) AS similarity
        FROM document_embeddings
        WHERE language = :language
        ORDER BY embedding <=> :embedding
        LIMIT :top_k
    """),
    {"embedding": query_embedding, "language": language, "top_k": top_k}
).fetchall()
```

### Document Chunking Strategy

Each corpus document is split at H2 headers (`## `). Chunk types map directly to H2 section names:

| H2 Header | chunk_type |
|-----------|------------|
| `## Overview` | `overview` |
| `## Key Concepts` | `key_concepts` |
| `## Practical Examples` | `practical_examples` |
| `## Actionable Takeaways` | `actionable_takeaways` |
| `## Related Topics` | `related_topics` |

**doc_id format:** `{language}/{slug}` — e.g. `en/budgeting-basics`  
Upsert idempotency uses the unique constraint on `(doc_id, chunk_type)` — no need to encode chunk_type into doc_id.

### FinancialPipelineState Changes

Add two new fields to `state.py`:
```python
class FinancialPipelineState(TypedDict):
    # ... existing fields ...
    locale: str                # 'en' or 'uk', from user.locale
    insight_cards: list[dict]  # output of education node
```

`locale` must be populated in the Celery task that builds the initial pipeline state. The user's locale preference is stored in the `users` table as `locale` field (default `"uk"`, added in Story 1.6).

### Pipeline Flow After This Story

```python
# pipeline.py after story 3.3
graph.add_node("categorization", categorization_node)
graph.add_node("education", education_node)
graph.set_entry_point("categorization")
graph.add_edge("categorization", "education")
graph.add_edge("education", END)
```

### Education Agent Prompts

The Education Agent must produce structured JSON. Use the same pattern as the categorization node (return JSON array, no markdown).

**English prompt skeleton:**
```
You are a financial education assistant for a personal finance app.
The user's recent spending summary: {user_context}

Relevant financial education context:
{rag_context}

Generate 3-5 insight cards. Return ONLY a JSON array (no markdown):
[{
  "headline": "Short factual observation about their spending",
  "key_metric": "The key number (e.g., '₴4,200 on food this month')",
  "why_it_matters": "1-2 sentences explaining financial significance",
  "deep_dive": "2-3 sentences of educational depth using the retrieved content",
  "severity": "high|medium|low",
  "category": "the spending category this relates to"
}]
```

**Ukrainian prompt:** Same structure, all text in Ukrainian. Use natural Ukrainian financial terminology from the corpus (e.g., "витрати", "заощадження", "бюджет").

### Graceful Degradation (AC #5 / NFR28)

The education node MUST NOT raise exceptions. Any failure (OpenAI Embeddings API error, DB error, LLM error) must be caught and logged, returning state with `insight_cards=[]`:

```python
def education_node(state: FinancialPipelineState) -> FinancialPipelineState:
    try:
        # ... normal flow ...
        return {**state, "insight_cards": cards, "step": "education"}
    except Exception as exc:
        logger.error('{"level": "ERROR", "step": "education", "error": "%s"}', exc)
        return {**state, "insight_cards": [], "step": "education"}
```

Story 3.4 (Teaching Feed API) will return an empty insights array when `insight_cards=[]`, which Story 3.5 UI handles as "no insights yet" state — not an error.

### Celery Task Integration

Find the Celery task in `backend/app/tasks/processing_tasks.py` → `process_upload()` (lines ~132-150) that builds the pipeline state and invokes `financial_pipeline`. It currently passes `job_id`, `user_id`, `upload_id`, `transactions`. Add `locale` lookup:

```python
# In the Celery task, before building initial state:
from app.models.user import User
user = session.get(User, user_id)
locale = user.locale or "uk"

state = FinancialPipelineState(
    job_id=...,
    user_id=...,
    upload_id=...,
    transactions=...,
    categorized_transactions=[],
    errors=[],
    step="start",
    total_tokens_used=0,
    locale=locale,
    insight_cards=[],
)
```

### User Model Locale Field

The `users` table has a `locale: str = Field(default="uk")` column (added in Story 1.6). Use `user.locale` to determine corpus language. Values: `"uk"` (Ukrainian, default) or `"en"` (English).

### File Locations (Critical — Do Not Use Wrong Paths)

| Artifact | Path |
|----------|------|
| RAG corpus (source) | `backend/data/rag-corpus/en/` and `backend/data/rag-corpus/uk/` |
| Embeddings service | `backend/app/rag/embeddings.py` |
| Retriever | `backend/app/rag/retriever.py` |
| Seed script | `backend/app/rag/seed.py` |
| Education agent | `backend/app/agents/education/node.py` |
| Education prompts | `backend/app/agents/education/prompts.py` |
| Insight model | `backend/app/models/insight.py` |
| Embedding model | `backend/app/models/embedding.py` |

**Do NOT use** `backend/app/rag/content/` for corpus files — the architecture sketch was wrong. Corpus lives in `backend/data/rag-corpus/` as established in Story 3.2.  
**Do NOT use** `_uk.md`/`_en.md` suffixes — use `en/`/`uk/` subdirectories with matching slugs.

### Testing Strategy

**Unit test pattern for education_node** (mock retriever + LLM, no real embeddings):
```python
# tests/agents/test_education.py
from unittest.mock import patch, MagicMock

def test_education_node_happy_path():
    mock_docs = [{"content": "Budgeting helps...", "chunk_type": "overview", "similarity": 0.9}]
    mock_response = MagicMock()
    mock_response.content = '[{"headline": "Test", "key_metric": "₴1000", ...}]'
    
    with patch("app.agents.education.node.retrieve_relevant_docs", return_value=mock_docs):
        with patch("app.agents.education.node._get_llm_client") as mock_llm:
            mock_llm.return_value.invoke.return_value = mock_response
            result = education_node({...state...})
    
    assert len(result["insight_cards"]) > 0

def test_education_node_graceful_degradation():
    with patch("app.agents.education.node.retrieve_relevant_docs", side_effect=Exception("DB down")):
        result = education_node({...state...})
    assert result["insight_cards"] == []
    assert result["step"] == "education"
```

**Test count baseline:** 220 backend tests must still pass. Education node tests will add ~8-10 more. Target: ~228-230 tests passing after this story.

### LLM Client Reuse

Do NOT reinvent LLM initialization. Reuse the same pattern from `categorization/node.py`:
- `_get_llm_client()` → `ChatAnthropic(model="claude-haiku-4-5-20251001")`
- `_get_fallback_llm_client()` → `ChatOpenAI(model="gpt-4o-mini")`
- Wrap calls in try/except with fallback chain

Consider extracting these two functions to `backend/app/agents/llm.py` shared module — but only if it doesn't bloat the scope. At minimum, copy the pattern identically.

### Seed Script Notes

The seed script must be idempotent (safe to run multiple times). Use `INSERT ... ON CONFLICT (doc_id, chunk_type) DO UPDATE SET content=excluded.content, embedding=excluded.embedding` pattern.

**Running locally:**
```bash
cd backend
python -m app.rag.seed
```

The seed script does NOT need to run as part of the test suite or Celery startup — it's an ops script. Add to project README under "Setup" instructions.

### Project Structure Notes

New directories/files created by this story:
```
backend/app/rag/
├── __init__.py
├── embeddings.py
├── retriever.py
└── seed.py

backend/app/agents/education/
├── __init__.py
├── node.py
└── prompts.py

backend/app/models/
├── embedding.py    (new)
└── insight.py      (new)

backend/alembic/versions/
├── xxxx_create_document_embeddings_table.py  (new)
└── xxxx_create_insights_table.py             (new)
```

All paths align with `architecture.md#Backend Directory Structure` (lines 960-964, 922-924).

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story 3.3] — acceptance criteria
- [Source: _bmad-output/planning-artifacts/architecture.md#Vector Embeddings — pgvector with BGE-M3 1024 dimensions, line 281]
- [Source: _bmad-output/planning-artifacts/architecture.md#Backend Directory Structure, lines 960-964]
- [Source: _bmad-output/planning-artifacts/architecture.md#Primary Database, line 275]
- [Source: _bmad-output/planning-artifacts/architecture.md#NFR28 — graceful degradation]
- [Source: _bmad-output/implementation-artifacts/3-1-transaction-categorization-agent.md — LLM client pattern, pipeline node structure, FinancialPipelineState]
- [Source: _bmad-output/implementation-artifacts/3-2-rag-financial-literacy-corpus-creation.md — corpus structure, file locations, chunk format]
- [Source: backend/app/agents/categorization/node.py — LLM init pattern, retry/fallback pattern, structured JSON response parsing]
- [Source: backend/app/agents/state.py — FinancialPipelineState TypedDict to extend]
- [Source: backend/app/agents/pipeline.py — pipeline graph to update]
- [Source: backend/app/core/config.py — Settings, ANTHROPIC_API_KEY, OPENAI_API_KEY]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6

### Debug Log References

- Fixed Alembic migration revision ID collision: `a1b2c3d4e5f6` was already used by `f3a8b2c1d4e5_add_format_detection_fields.py`; changed to `g3h4i5j6k7l8`
- Fixed `UnboundLocalError` for `insight_cards` in Celery task when categorization pipeline fails before education node runs; initialized variable before try block

### Completion Notes List

- RAG infrastructure: embeddings service wrapping OpenAI `text-embedding-3-small` (1536-dim), retriever with cosine similarity via pgvector `<=>` operator and cross-lingual fallback, idempotent seed script chunking corpus by H2 sections
- Education Agent: LangGraph node generating 3-5 bilingual insight cards from spending data + RAG context, with graceful degradation returning empty list on any failure
- Pipeline updated: categorization -> education -> END; Celery task passes user locale and persists insight cards to new `insights` table
- Two new Alembic migrations: `document_embeddings` (with HNSW index) and `insights` tables
- 23 new tests added (243 total, all passing), covering education node, retriever, embeddings service, prompt selection, graceful degradation, and LLM fallback paths

### Change Log

- 2026-04-04: Story 3.3 implementation complete — RAG knowledge base, education agent, insight persistence, 23 new tests
- 2026-04-04: Code review fixes — [C1] fixed spending summary to join transactions+categories instead of reading non-existent amount field from categorized_transactions; [C2] fixed test mock data to match real categorization output shape; [H1] extracted shared LLM clients to app/agents/llm.py; [H2] added SSE progress event for education step; [M1] added missing Transaction/FlaggedImportRow imports to alembic/env.py; [M2] moved Insight import to module top in processing_tasks.py; [M3] seed.py now captures pre-H2 preamble content; [M4] embed_batch guards against empty input

### File List

**New files:**
- backend/app/rag/embeddings.py
- backend/app/rag/retriever.py
- backend/app/rag/seed.py
- backend/app/agents/education/__init__.py
- backend/app/agents/education/node.py
- backend/app/agents/education/prompts.py
- backend/app/agents/llm.py
- backend/app/models/embedding.py
- backend/app/models/insight.py
- backend/alembic/versions/g3h4i5j6k7l8_create_document_embeddings_table.py
- backend/alembic/versions/b2c3d4e5f6a7_create_insights_table.py
- backend/tests/agents/test_education.py
- backend/tests/test_rag_retrieval.py
- backend/tests/test_embeddings.py

**Modified files:**
- backend/pyproject.toml (added pgvector dependency)
- backend/app/agents/state.py (added locale, insight_cards fields)
- backend/app/agents/pipeline.py (added education node to graph)
- backend/app/tasks/processing_tasks.py (locale lookup, insight persistence, totalInsights SSE, education progress event)
- backend/app/models/__init__.py (added DocumentEmbedding, Insight exports)
- backend/alembic/env.py (added all model imports)
- backend/app/agents/categorization/node.py (use shared LLM clients from app/agents/llm.py)
- backend/tests/agents/test_categorization.py (updated mock paths for shared LLM, added locale/insight_cards to state)
