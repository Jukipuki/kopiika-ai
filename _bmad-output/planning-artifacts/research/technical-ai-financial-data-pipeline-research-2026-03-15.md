---
stepsCompleted: [1, 2, 3, 4, 5, 6]
inputDocuments:
  - product-brief-kopiika-ai-2026-03-15.md
workflowType: 'research'
lastStep: 1
research_type: 'technical'
research_topic: 'AI Pipeline for Ukrainian Financial Data: RAG vs Fine-tuning, Monobank CSV Format, Vector Store Options'
research_goals: 'Determine optimal AI approach (RAG vs fine-tuning) for Ukrainian financial data, understand Monobank CSV format specifics, evaluate vector store options for financial literacy knowledge base'
user_name: 'Oleh'
date: '2026-03-15'
web_research_enabled: true
source_verification: true
---

# Building an AI-Powered Financial Education Pipeline for Ukraine: Comprehensive Technical Research

**Date:** 2026-03-15
**Author:** Oleh
**Research Type:** Technical Architecture & Implementation

---

## Executive Summary

This research evaluates the technical foundation for building a **kōpiika** — an AI-powered platform that transforms Ukrainian bank statement data into personalized financial education. The product targets Ukraine's 9.88M+ Monobank users through a trust-first CSV/PDF upload model, processing transactions through a 5-agent AI pipeline (Ingestion → Categorization → Pattern Detection → Triage → Education) to deliver severity-ranked insights wrapped in progressive educational content.

The research conclusively answers three core technical questions:

1. **RAG vs. Fine-tuning:** RAG-first is the clear winner for V1. Financial education content changes frequently, RAG provides citation traceability (critical for financial advice), and it avoids the Ukrainian financial data scarcity problem. A hybrid approach (RAG + fine-tuned MamayLM) is the validated evolution path, with evidence showing 22% accuracy improvement over either approach alone.

2. **Data Ingestion Architecture:** Monobank's 17-field API transaction structure is well-documented (Windows-1251 CSV encoding, semicolon delimiters, kopiykas amounts). PDF parsing via pdfplumber with Claude API fallback provides cost-efficient dual-format support. A strategy pattern with bank-specific parsers enables clean multi-bank, multi-format extensibility.

3. **Vector Store & Embeddings:** pgvector on PostgreSQL is the optimal V1 choice — zero additional cost, 1-2ms query latency at 100K vectors, ACID compliance for financial data, and unified relational + vector storage. BGE-M3 embeddings provide confirmed Ukrainian language support with cross-lingual retrieval capability.

**Key Technical Findings:**

- **Modular monolith** architecture over microservices saves $3,000-6,000/mo in infrastructure while maintaining development velocity for a solo/small team
- **LangGraph** is the recommended multi-agent framework — deterministic execution paths and audit trails address the #1 concern (governance, 48%) blocking AI agent production deployment
- **Total MVP infrastructure cost: ~$30-35/mo** on Render (FastAPI + Celery + PostgreSQL + Redis) with Next.js frontend on Vercel free tier
- **NBU's Harazd platform** provides a ready-made, free Ukrainian financial literacy content source for the RAG knowledge base
- **Four-tier LLM cost optimization** (prompt caching + model cascading + semantic caching + RAG optimization) can achieve **50-87% cost reduction**

**Top Recommendations:**

1. Deploy RAG pipeline with BGE-M3 embeddings + pgvector on PostgreSQL — production-ready at minimal cost
2. Use LangGraph for the 5-agent pipeline with Celery + Redis for async processing
3. Build dual CSV/PDF ingestion with pdfplumber + Claude API fallback
4. Seed RAG knowledge base from NBU Harazd + Financial Competencies Framework
5. Start on Render (~$30/mo), scale to Fly.io when GPU needed for embeddings

---

## Table of Contents

1. [Technology Stack Analysis](#technology-stack-analysis)
   - AI Approach: RAG vs Fine-tuning
   - Embedding Models with Ukrainian Support
   - Ukrainian LLMs for Fine-tuning
   - Vector Store Options
   - Monobank CSV Format & Data Ingestion
   - Multi-Agent Pipeline Architecture
   - Technology Adoption Trends
2. [Integration Patterns Analysis](#integration-patterns-analysis)
   - LangGraph Multi-Agent Pipeline Integration
   - RAG Pipeline Integration (pgvector + BGE-M3)
   - File Upload & Async Processing Pipeline
   - Monobank API Integration
   - API Design for Teaching Feed
   - Authentication & Data Security
   - Payment Integration for Ukrainian Market
3. [Architectural Patterns and Design](#architectural-patterns-and-design)
   - System Architecture: Modular Monolith
   - Clean Architecture / Hexagonal Architecture
   - PDF Bank Statement Parsing Architecture
   - Database Architecture
   - Deployment Architecture
   - Caching & Performance Architecture
   - Scalability Patterns
4. [Implementation Approaches](#implementation-approaches-and-technology-adoption)
   - CI/CD Pipeline
   - Testing Strategy for AI/LLM Pipelines
   - Monitoring and Observability
   - LLM Cost Optimization
   - Development Environment
   - RAG Knowledge Base Seeding
   - Risk Assessment and Mitigation
5. [Technical Recommendations](#technical-research-recommendations)
   - Implementation Roadmap (16 weeks)
   - Technology Stack Summary
   - Key Success Metrics

---

## Research Methodology

**Scope:** AI pipeline architecture for Ukrainian financial data analysis — RAG vs fine-tuning trade-offs, Monobank CSV/PDF format specifics, vector store evaluation, multi-agent pipeline design, deployment and implementation strategies.

**Approach:**
- 50+ web searches across academic papers, industry reports, official documentation, and technical benchmarks
- Multi-source validation for all critical technical claims
- Confidence levels assigned: HIGH (multiple corroborating sources), MEDIUM-HIGH (strong evidence with some gaps), MEDIUM (limited direct evidence)
- All sources verified as current (2025-2026 data prioritized)

**Input Documents:** Product Brief (kopiika-ai, 2026-03-15) defining the kōpiika — multi-agent pipeline, Teaching Feed UX, cumulative intelligence model, Ukrainian market first.

---

## Technology Stack Analysis

### AI Approach: RAG vs Fine-tuning for Ukrainian Financial Data

**Recommendation: RAG-first with hybrid evolution path** _(Confidence: HIGH)_

| Factor | RAG | Fine-tuning |
|--------|-----|-------------|
| **Cost model** | OpEx (ongoing retrieval infrastructure) | CapEx (upfront training + periodic retraining) |
| **Initial investment** | Lower — vector DB + embedding pipeline | Higher — GPU compute (LoRA fine-tuning <$300/session) |
| **Update frequency** | Low cost — update documents in knowledge base | High cost — requires retraining cycle |
| **Latency** | +30-50% retrieval overhead | Lower per-query (no retrieval step) |
| **Traceability** | Citations/source excerpts for compliance | Knowledge embedded in weights (less auditable) |
| **Best for** | Fast-changing data (regulations, market data) | Stable domain behavior, language fluency |

RAG is strongly recommended for V1 because financial education content, regulations, and market data change frequently. Fine-tuning is better suited for establishing Ukrainian financial domain behavior and language fluency (Phase 2).

**Hybrid approach validated:** A financial trading firm using RAG + fine-tuned model reported **22% increase in prediction accuracy** over either approach alone. The pattern: fine-tune for domain behavior/language, RAG for dynamic knowledge access.

**ICLR 2026 insight:** RAG can be distilled into fine-tuned models, reducing token usage by **10-60%** — a viable Phase 3 optimization path.

_Sources: [b-eye.com](https://b-eye.com/blog/rag-vs-fine-tuning/), [orq.ai](https://orq.ai/blog/finetuning-vs-rag), [calmops.com](https://calmops.com/ai/rag-vs-fine-tuning-2026-complete-guide/), [arXiv 2510.01375](https://arxiv.org/abs/2510.01375), [AWS hybrid guide](https://aws.amazon.com/blogs/machine-learning/tailoring-foundation-models-for-your-business-needs-a-comprehensive-guide-to-rag-fine-tuning-and-hybrid-approaches/)_

### Embedding Models with Ukrainian Language Support

**Recommendation: BGE-M3 for Phase 1, Jina-embeddings-v3 as alternative** _(Confidence: HIGH)_

| Model | Ukrainian Support | Params | Dimensions | Context | Cost | Best For |
|-------|-------------------|--------|------------|---------|------|----------|
| **BGE-M3** | Yes (100+ languages) | ~568M | 1024 | 8192 tokens | Free (Apache 2.0) | Hybrid retrieval (dense+sparse+ColBERT) |
| **Jina-embeddings-v3** | Yes (top-30 best languages) | 570M | Variable | 8192 tokens | Free (open-source) | Production-proven, most downloaded |
| **Qwen3-Embedding-8B** | Yes (100+ languages) | 8B | 1024 | 32768 tokens | Free (Apache 2.0) | Best accuracy (#1 MTEB multilingual) |
| **ukr-paraphrase-multilingual-mpnet-base** | Ukrainian-specific fine-tuning | ~278M | 768 | 512 tokens | Free | Ukrainian-specific tasks |

BGE-M3 is recommended for V1 because it's free, supports 100+ languages including Ukrainian, offers 1024 dimensions (optimal for pgvector performance), handles 8192-token context (long financial documents), and uniquely supports dense + sparse + multi-vector retrieval for hybrid search.

Cross-lingual retrieval is critical for bilingual systems — BGE-M3 and Qwen3-Embedding enable queries in Ukrainian to retrieve English documents and vice versa.

_Sources: [HuggingFace BGE-M3](https://huggingface.co/BAAI/bge-m3), [Jina v3 announcement](https://jina.ai/news/jina-embeddings-v3-a-frontier-multilingual-embedding-model/), [Qwen3 blog](https://qwenlm.github.io/blog/qwen3-embedding/), [HuggingFace ukr-paraphrase](https://huggingface.co/lang-uk/ukr-paraphrase-multilingual-mpnet-base)_

### Ukrainian LLMs for Fine-tuning (Phase 2)

**Key model: MamayLM v1.0** _(Confidence: MEDIUM-HIGH)_

| Model | Parameters | Base | Key Achievement |
|-------|------------|------|-----------------|
| **MamayLM v1.0** | 9B / 12B | Gemma 2/3 | State-of-the-art Ukrainian LLM; outperforms models up to 5x its size on Ukrainian benchmarks; runs on single GPU |
| **Kyivstar National LLM** | TBD | Gemma | Government-backed initiative targeting financial services |

MamayLM is the strongest candidate for Phase 2 domain fine-tuning. Ukrainian is still classified as low-resource, so the recommended approach is:
1. Start with MamayLM as base
2. Curate Ukrainian financial corpus (NBU reports, regulations, financial news)
3. Apply LoRA/QLoRA fine-tuning (<$300/session)
4. Supplement with translated English financial datasets where needed

_Sources: [HuggingFace MamayLM blog](https://huggingface.co/blog/INSAIT-Institute/mamaylm), [INSAIT announcement](https://insait.ai/insait-releases-the-first-open-and-efficient-multimodal-ukrainian-llm/), [arXiv 2404.09138](https://arxiv.org/html/2404.09138v1)_

### Vector Store Options

**Recommendation: Start with pgvector, scale to Qdrant** _(Confidence: HIGH)_

| Feature | pgvector | Chroma | Qdrant | Weaviate | Pinecone |
|---------|----------|--------|--------|----------|----------|
| **Type** | PG Extension | Embedded/Cloud | Standalone DB | Standalone DB | Managed SaaS |
| **License** | PostgreSQL | Apache 2.0 | Apache 2.0 | BSD-3 | Proprietary |
| **Free tier** | Free (self-hosted) | $5 cloud credits | 1GB free cluster | 14-day sandbox | 2GB storage |
| **Hybrid search** | Manual (tsvector) | No | Yes (sparse+dense) | Yes (best-in-class) | Yes |
| **Query latency (100K)** | ~1-2ms (HNSW) | ~5-15ms | <5ms | <10ms | <50ms |
| **ACID compliance** | Yes (full PG) | No | No | No | No |
| **Monthly cost (100K docs)** | $0-25 | $10-25 | $0-27 | $25-45 | $50+ |

**Why pgvector for Phase 1:**
- **Zero additional cost** if already running PostgreSQL
- **1-2ms query latency** at 100K vectors with HNSW — more than sufficient for RAG
- **Unified data model** — join financial metadata with vector similarity in single SQL query
- **ACID compliance** — critical for financial data integrity
- **All major frameworks** (LangChain, LlamaIndex) have pgvector integration
- At 10K-100K documents, pgvector performs comparably to purpose-built vector databases

**Scale-up path:** pgvector (MVP) → Qdrant (production scale) → Weaviate/Pinecone (enterprise). Using LangChain/LlamaIndex abstractions from day one makes migration straightforward.

_Sources: [AWS pgvector 0.8.0](https://aws.amazon.com/blogs/database/supercharging-vector-search-performance-and-relevance-with-pgvector-0-8-0-on-amazon-aurora-postgresql/), [Crunchy Data HNSW](https://www.crunchydata.com/blog/hnsw-indexes-with-postgres-and-pgvector), [Encore blog](https://encore.dev/blog/you-probably-dont-need-a-vector-database), [Qdrant pricing](https://qdrant.tech/pricing/), [Pinecone pricing](https://www.pinecone.io/pricing/)_

### Monobank CSV Format & Data Ingestion

**Monobank API Transaction Structure (17 fields, definitive)** _(Confidence: HIGH)_

| Field | Type | Unit | Notes |
|-------|------|------|-------|
| `id` | string | — | Unique ID (e.g., `"ZuHWzqkKGVo="`) |
| `time` | int32 | Unix seconds | UTC timestamp |
| `description` | string | — | Merchant name (Cyrillic/Latin/mixed) |
| `mcc` | int32 | — | Merchant Category Code (ISO 18245) |
| `originalMcc` | int32 | — | Original MCC before remapping |
| `hold` | bool | — | Pending transaction flag |
| `amount` | int64 | kopiykas | Account currency amount (negative = debit) |
| `operationAmount` | int64 | kopiykas | Transaction currency amount |
| `currencyCode` | int32 | ISO 4217 numeric | 980=UAH, 840=USD, 978=EUR |
| `commissionRate` | int64 | kopiykas | Commission charged |
| `cashbackAmount` | int64 | kopiykas | Cashback earned |
| `balance` | int64 | kopiykas | Balance after transaction |
| `comment` | string | — | User-added comment (optional) |
| `receiptId` | string | — | ATM receipt ID |
| `invoiceId` | string | — | FOP invoice ID |
| `counterEdrpou` | string | — | Counterparty EDRPOU (FOP only) |
| `counterIban` | string | — | Counterparty IBAN (FOP only) |

**CSV Export Format:**
- **Encoding:** Windows-1251 (web cabinet) / UTF-8 (API)
- **Delimiter:** Semicolon (`;`) — Ukrainian locale uses comma for decimals
- **Date format:** `dd.MM.yyyy HH:mm:ss`
- **Amounts:** Comma as decimal separator (`-950,00`)
- **API rate limit:** 1 request/60s, max 31 days, max 500 transactions/response

**Critical parsing pitfalls:**
1. Windows-1251 encoding (not UTF-8) for web cabinet exports
2. Comma as decimal separator / semicolon as field delimiter
3. Embedded newlines in description fields break naive CSV parsing
4. Ukrainian Cyrillic `і` vs Latin `i` — visually identical, different code points
5. API amounts in kopiykas vs human-readable decimals in CSV exports
6. UTC timestamps (API) vs Kyiv time (CSV, EET/EEST UTC+2/+3)

**MCC Codes Dataset:** Open-source with Ukrainian/English/Russian translations, 20 business category groups, MIT licensed — [Merchant-Category-Codes GitHub](https://github.com/Oleksios/Merchant-Category-Codes)

**Open-source ecosystem:** 8+ Monobank API client libraries (Go, Python, Ruby, Dart, C#, Kotlin, JS). Key tools: `mono-cli` (Go, CSV export), `python-monobank` (Python API client), `monobudget` (Kotlin, YNAB import).

_Sources: [Monobank Open API](https://api.monobank.ua/docs/index.html), [python-monobank](https://pypi.org/project/monobank/), [mono-cli](https://github.com/lungria/mono-cli), [BookKeeper W-1251 confirmation](https://bookkeeper.kiev.ua/zavantazhennya-vipisok-monobank-dlya-yurosib-v-bookkeeper/)_

### Multi-Agent Pipeline Architecture

**Recommendation: LangGraph for production, CrewAI for prototyping** _(Confidence: HIGH)_

Market adoption is accelerating: **44% of finance teams** will use agentic AI in 2026 (600%+ increase). Gartner projects 75% of large enterprises will adopt multi-agent systems by 2026.

**Architectural patterns for the product's 5-agent pipeline:**

| Pattern | Description | Fit for Product |
|---------|-------------|-----------------|
| **Workflow (Sequential)** | Each agent completes before passing to next | Best fit — Ingestion → Categorization → Pattern Detection → Triage → Education |
| **Swarm (Parallel)** | Specialized agents work simultaneously | Good for running Pattern Detection + Subscription Detection in parallel |
| **Crew-Based (Role)** | Agents with distinct roles collaborate | Good for Education Agent orchestrating sub-specialists |

**Framework comparison:**

| Framework | Best For | Financial Suitability |
|-----------|----------|----------------------|
| **LangGraph** | Deterministic control flow, audit trails | **Best for regulated financial systems** — explicit execution paths, human-in-the-loop |
| **CrewAI** | Role-based collaboration, rapid prototyping | **Good for analysis teams** — 40% faster prototyping |
| **AutoGen** | Multi-turn conversations | Good for advisory scenarios |

**Implementation note:** Only 11% of companies have moved agents to production despite 99% planning to — governance (48%) and privacy (30%) are top concerns. LangGraph's deterministic approach directly addresses these.

_Sources: [AWS multi-agent patterns](https://aws.amazon.com/blogs/industries/agentic-ai-in-financial-services-choosing-the-right-pattern-for-multi-agent-systems/), [arXiv 2502.05439](https://arxiv.org/html/2502.05439v1), [Neurons Lab](https://neurons-lab.com/article/agentic-ai-in-financial-services-2026/), [LangGraph vs CrewAI 2026](https://particula.tech/blog/langgraph-vs-crewai-vs-openai-agents-sdk-2026)_

### Technology Adoption & Industry Trends

_Adoption trends for AI in financial services (Confidence: HIGH)_

- **Event-driven streaming architecture** is now standard — 70%+ adoption by 2026 in financial institutions
- **60% of successful AI initiatives** depend on modernized data platforms with lineage, observability, and interoperability
- **FinSage reference architecture** (1,200+ users in production) achieves **92.51% recall** using multi-path sparse-dense retrieval with DPO-tuned re-ranking
- Governance controls must be embedded directly in MLOps pipelines — responsible AI frameworks at every lifecycle stage
- RAG-powered financial education can generate custom learning paths and contextual explanations from regulatory filings and knowledge bases

_Sources: [Microsoft AI Financial Services 2026](https://www.microsoft.com/en-us/industry/blog/financial-services/2025/12/18/ai-transformation-in-financial-services-5-predictors-for-success-in-2026/), [FinSage arXiv](https://arxiv.org/html/2504.14493v2), [WJAETS data pipelines](https://wjaets.com/sites/default/files/fulltext_pdf/WJAETS-2025-0459.pdf)_

## Integration Patterns Analysis

### LangGraph Multi-Agent Pipeline Integration

**Core pattern: StateGraph with sequential pipeline + conditional branching** _(Confidence: HIGH)_

LangGraph models the 5-agent pipeline as a directed graph where agents are nodes and edges define data flow. State is a `TypedDict` with reducer functions that define how concurrent state updates merge.

**Pipeline architecture:**

```
[CSV Upload] → [Ingestion Agent] → [Categorization Agent] → [Pattern Detection Agent] → [Triage Agent] → [Education Agent (RAG)]
                                                                      ↕
                                                              [Parallel: Subscription Detection]
```

**Key integration patterns:**

| Pattern | LangGraph Implementation | Use Case |
|---------|--------------------------|----------|
| **Sequential pipeline** | `graph.add_edge(node_a, node_b)` | Ingestion → Categorization → Pattern Detection → Triage → Education |
| **Conditional branching** | `graph.add_conditional_edges()` | Route based on triage severity (e.g., high-risk → human review) |
| **Human-in-the-loop** | `interrupt()` + `Command()` | Pause at triage for manual approval of flagged patterns |
| **Subgraphs** | Independent `StateGraph` per agent | Each pipeline agent encapsulates its own internal logic |
| **State versioning** | Immutable state — each agent creates new version | Full audit trail, no race conditions |
| **Checkpointing** | Persist to Postgres/Redis after each node | Crash recovery, resume from last completed agent |

**Centralized state TypedDict:**
```python
class PipelineState(TypedDict):
    user_id: str
    upload_id: str
    raw_transactions: list[dict]        # From Ingestion
    categorized_transactions: list[dict] # From Categorization
    patterns: list[dict]                 # From Pattern Detection
    triage_cards: list[dict]             # From Triage (severity-ranked)
    education_content: list[dict]        # From Education Agent (RAG)
    processing_log: Annotated[list[dict], add]  # Audit trail accumulator
```

_Sources: [LangGraph Multi-Agent Orchestration 2025](https://latenode.com/blog/ai-frameworks-technical-infrastructure/langgraph-multi-agent-orchestration/langgraph-multi-agent-orchestration-complete-framework-guide-architecture-analysis-2025), [LangGraph State Management 2025](https://sparkco.ai/blog/mastering-langgraph-state-management-in-2025), [LangGraph Human-in-the-loop](https://docs.langchain.com/oss/python/langchain/human-in-the-loop), [Production Multi-Agent with LangGraph](https://markaicode.com/langgraph-production-agent/)_

### RAG Pipeline Integration (pgvector + BGE-M3 + LangChain)

**Integration flow for the Education Agent** _(Confidence: HIGH)_

```
[User's triage card] → [Query formulation] → [BGE-M3 embedding] → [pgvector HNSW search]
                                                                            ↓
[Response generation] ← [Re-ranking] ← [Document grading] ← [Retrieved financial education chunks]
```

**Key integration details:**

- Use `PGVector` from `langchain_community.vectorstores` with `HuggingFaceBgeEmbeddings` for BGE-M3
- HNSW index on pgvector (recommended over IVFFlat for production)
- **Agentic RAG flow** in LangGraph: retrieve → grade documents for relevance → generate response
- **Hybrid retrieval** recommended: combine BGE-M3 dense embeddings with BM25-like sparse retrieval (via pgvector tsvector) for best results on financial terminology
- Financial education knowledge base chunked by topic with metadata (category, difficulty_level, language)

**SQL-powered hybrid search example:**
```sql
SELECT a.title, a.content, a.category,
       1 - (a.embedding <=> query_embedding) AS similarity
FROM education_articles a
WHERE a.language = 'uk' AND a.category = 'budgeting'
ORDER BY a.embedding <=> query_embedding
LIMIT 10;
```

_Sources: [LangChain + pgvector + BGE-M3 tutorial](https://zilliz.com/tutorials/rag/langchain-and-pgvector-and-nvidia-bge-m3-and-ollama-bge-m3), [LangGraph Agentic RAG](https://docs.langchain.com/oss/python/langgraph/agentic-rag), [Financial Education Chatbot with RAG](https://medium.com/@hlealpablo/building-a-financial-education-chatbot-with-retrieval-augmented-generation-rag-bf338aa2df09)_

### File Upload & Async Processing Pipeline

**Pattern: Async upload with queue-based background processing** _(Confidence: HIGH)_

```
[Browser] --POST multipart--> [FastAPI] --validate--> [Store CSV] --enqueue--> [Celery Worker]
    ↑                              |                                                |
    |                         HTTP 202 + job_id                              [LangGraph pipeline]
    |                                                                              |
    +<------- SSE stream (progress per agent step) --------------------------------+
```

**Implementation pattern:**
1. FastAPI `UploadFile` receives CSV, validates (MIME type, size, Monobank header format)
2. Returns HTTP 202 with `job_id` and `Location` header pointing to status/stream endpoint
3. **Celery + Redis** runs LangGraph agents inside workers
4. Job progress tracked in PostgreSQL with per-agent step updates
5. SSE (`sse-starlette`) streams live progress to browser: `progress` events per step, `done` event with results

**Celery integration with LangGraph:**
- Use Celery `chain` primitive for sequential pipeline steps
- Use `chord` for parallel execution (Pattern Detection + Subscription Detection)
- LangGraph agents invoked inside Celery workers via `asyncio.get_event_loop()` + `loop.run_until_complete()`

_Sources: [Scalable AI Services: Service Bus + Background Worker](https://www.caseyspaulding.com/blog/building-scalable-ai-services-the-service-bus-background-worker-pattern), [FastAPI File Uploads](https://betterstack.com/community/guides/scaling-python/uploading-files-using-fastapi/), [Async Document Processing](https://amrollahi.medium.com/building-an-asynchronous-document-processing-system-with-azure-functions-queues-and-ai-search-37f9e3993247)_

### Monobank API Integration

**Dual ingestion strategy: CSV upload (V1) + API integration (future)** _(Confidence: HIGH)_

**CSV Upload (V1 — primary):**
- Detect encoding: try Windows-1251 first, fallback to UTF-8
- Parse with semicolon delimiter, comma decimal separator
- Strip embedded newlines from description fields
- Convert `dd.MM.yyyy HH:mm:ss` to ISO 8601
- Normalize amounts: divide kopiykas by 100 if smallest-unit format

**API Integration (future — when trust is established):**

| Aspect | Detail |
|--------|--------|
| **Auth** | `X-Token` header (not OAuth) — user generates via QR in Monobank app |
| **Rate limit** | 1 request/60s (Personal API); no limit on Corporate API |
| **Max period** | 31 days + 1 hour per request |
| **Max transactions** | 500 per response |
| **Historical sync** | 1 year = ~12 API calls minimum = ~12 minutes |
| **Webhooks** | `POST /personal/webhook` — real-time transaction push, 3-retry policy (5s timeout, retries at 60s and 600s, then disables) |

**Internal transaction data model** (normalized from Monobank format):

| Field | Type | Source |
|-------|------|--------|
| `id` | UUID | Generated |
| `external_id` | string | Monobank `id` |
| `user_id` | UUID | Auth context |
| `timestamp` | datetime (UTC) | Monobank `time` (converted) |
| `description` | string | Monobank `description` |
| `amount` | decimal | Monobank `amount / 100` |
| `currency` | string (ISO 4217 alpha) | Monobank `currencyCode` → mapped |
| `balance_after` | decimal | Monobank `balance / 100` |
| `mcc_code` | int | Monobank `mcc` |
| `category` | string | AI-assigned (Categorization Agent) |
| `is_recurring` | bool | AI-detected (Pattern Detection Agent) |
| `raw_data` | JSONB | Original Monobank JSON for auditability |

_Sources: [Monobank Open API](https://api.monobank.ua/docs/index.html), [python-monobank](https://pypi.org/project/monobank/), [mono-cli](https://github.com/lungria/mono-cli)_

### API Design for Teaching Feed

**Recommendation: REST API with cursor-based pagination, SSE for streaming** _(Confidence: HIGH)_

| Endpoint Pattern | Method | Purpose |
|-----------------|--------|---------|
| `/api/upload` | POST | CSV file upload, returns job_id |
| `/api/jobs/{id}/status` | GET (SSE) | Stream processing progress |
| `/api/feed` | GET | Teaching Feed cards (cursor-paginated, sorted by triage severity) |
| `/api/feed/{card_id}` | GET | Single insight card with education layers |
| `/api/profile/health-score` | GET | Financial Health Score + history |
| `/api/queries/{slug}` | GET | Pre-built data query results |
| `/api/auth/*` | POST | JWT auth with refresh token rotation |

**Frontend streaming pattern:**
- SSE is the de facto standard for LLM streaming in 2025-2026 (used by OpenAI, Anthropic)
- FastAPI `StreamingResponse` → Vercel AI SDK `useChat`/`useCompletion` hooks on Next.js frontend
- SSE wins over WebSockets for this use case: unidirectional, stateless, HTTP-native, no sticky sessions
- Cache aggressively — AI-generated insights are write-once, read-many

_Sources: [Vercel AI SDK docs](https://sdk.vercel.ai/docs), [FastAPI StreamingResponse](https://fastapi.tiangolo.com/advanced/custom-response/)_

### Authentication & Data Security

**Build to GDPR standards now — Ukraine GDPR-harmonization law pending** _(Confidence: HIGH)_

| Layer | Pattern | Implementation |
|-------|---------|----------------|
| **Transit** | TLS 1.3 | All API communication encrypted |
| **At rest** | AES-256 | PostgreSQL transparent data encryption (including pgvector tables) |
| **Auth** | JWT + refresh tokens | Short expiry (15min) + token rotation |
| **Tenant isolation** | Row-level security | Users can only query their own financial data |
| **AI-specific** | Input sanitization | Prevent prompt injection before LLM |
| **AI-specific** | Output filtering | Prevent PII leakage in AI responses |
| **Compliance** | Data minimization | Only store necessary financial data |
| **Compliance** | Right to erasure | One-click delete including embeddings |
| **Compliance** | Audit logging | Full pipeline execution trail via LangGraph state versioning |

Ukraine's current data protection law (No 2297-VI, 2010) is modeled on Convention 108. A GDPR-harmonization draft law passed first reading in Parliament (Nov 2024) and is pending second reading. Building to GDPR standards future-proofs the product.

_Sources: [Ukraine Data Protection 2025-2026 ICLG](https://iclg.com/practice-areas/data-protection-laws-and-regulations/ukraine), [Ukraine Privacy Law GDPR Impact](https://svitla.com/blog/privacy-law-and-the-impact-of-gdpr-in-ukraine/), [AI Security in Financial Services](https://bigid.com/blog/elevating-trust-ai-security-in-financial-services/)_

### Payment Integration for Ukrainian Market

**Two-track approach required — Stripe NOT available in Ukraine** _(Confidence: MEDIUM)_

| Market | Provider | Rationale |
|--------|----------|-----------|
| **Ukrainian users** | **Fondy** | Best recurring billing support, mature API, 200+ countries, native Ukrainian integration |
| **International users** | **LemonSqueezy** | Merchant of Record (handles global tax), no foreign company needed for Ukrainian founders |

Stripe is confirmed unavailable in Ukraine as of November 2025 per NBU restrictions. Fondy is the recommended primary payment processor for the freemium model (99-149 UAH/month premium tier).

_Sources: [Fondy documentation](https://docs.fondy.eu/), [LemonSqueezy](https://www.lemonsqueezy.com/)_

## Architectural Patterns and Design

### System Architecture: Modular Monolith

**Recommendation: Modular monolith for MVP, with one early extraction (embedding service)** _(Confidence: HIGH)_

Industry consensus for 2025-2026 is unambiguous — start monolithic:
- Organizations with <50 engineers rarely see net benefits from microservices
- 42% of companies that adopted microservices have consolidated some services back (2025 CNCF survey)
- Monoliths cost ~$1,100-2,300/mo vs ~$4,200-8,500/mo for comparable microservices infrastructure
- Below 10 developers, monoliths decisively outperform microservices in development velocity

**Exception:** The BGE-M3 embedding computation may need to be a separate service early on — distinct scaling requirements (GPU vs CPU) and different deployment lifecycle.

**When to split a module into a service:**
1. It needs independent scaling (e.g., embedding computation under heavy load)
2. Fundamentally different deployment lifecycle (GPU vs CPU workloads)
3. Domain boundaries proven stable through months of production use

**Recommended modular monolith structure:**

```
app/
├── core/                        # Shared infrastructure
│   ├── config.py               # Pydantic BaseSettings
│   ├── db.py                   # Base models, session management
│   ├── deps.py                 # Dependency injection
│   ├── middleware.py           # Auth, logging, error handling
│   └── services/               # Events, cache, queue
├── auth/                        # Authentication module
│   ├── models.py / schemas/ / routes/
│   ├── gateway.py              # Public interface for other modules
│   └── events.py               # Domain events
├── ingestion/                   # Statement upload & parsing module
│   ├── parsers/
│   │   ├── csv_parser.py       # Monobank/PrivatBank CSV
│   │   ├── pdf_parser.py       # Monobank/PrivatBank PDF
│   │   └── base_parser.py      # Common parser interface
│   ├── services/ / routes/
│   └── gateway.py
├── ai_pipeline/                 # LangGraph multi-agent module
│   ├── agents/
│   │   ├── categorization.py
│   │   ├── pattern_detection.py
│   │   ├── triage.py
│   │   └── education.py        # RAG-powered
│   ├── graph.py                # LangGraph StateGraph definition
│   └── gateway.py
├── insights/                    # Teaching Feed & profile module
│   ├── models.py / schemas/ / routes/
│   └── gateway.py
├── knowledge_base/              # RAG knowledge base management
│   ├── embeddings.py
│   ├── retrieval.py
│   └── content_management.py
└── main.py
```

**Cross-module communication:**
- **Gateways** (synchronous): Each module exposes a Gateway class as its public API
- **Domain events** (asynchronous): via `fastapi-events` for loose coupling, enabling future service extraction

_Sources: [Java Code Geeks monolith vs microservices 2026](https://www.javacodegeeks.com/2025/12/microservices-vs-monoliths-in-2026-when-each-architecture-wins.html), [FastAPI modular monolith starter](https://github.com/arctikant/fastapi-modular-monolith-starter-kit), [FastAPI best practices (zhanymkanov)](https://github.com/zhanymkanov/fastapi-best-practices), [FastAPI + LangGraph template](https://github.com/wassim249/fastapi-langgraph-agent-production-ready-template)_

### Clean Architecture / Hexagonal Architecture

**Ports and adapters applied to the AI financial pipeline** _(Confidence: HIGH)_

```
src/
├── domain/                          # Pure business logic, ZERO framework imports
│   ├── transactions/
│   │   ├── entities.py              # Transaction, FinancialProfile
│   │   ├── value_objects.py         # Money, Category, Severity, Currency
│   │   ├── services.py              # Categorization rules, pattern detection
│   │   └── repositories.py          # Abstract repository interfaces (ports)
│   ├── insights/
│   │   ├── entities.py              # InsightCard, EducationalContent
│   │   └── services.py              # Insight generation rules
│   └── events.py                    # Domain events
├── application/                      # Use cases / orchestration
│   ├── ingest_statement.py          # Parse CSV/PDF → store transactions
│   ├── analyze_transactions.py      # Run multi-agent AI pipeline
│   ├── generate_insights.py         # RAG-based education generation
│   └── ports/                       # Application-level ports
│       ├── llm_port.py              # Abstract LLM interface
│       ├── embedding_port.py        # Abstract embedding interface
│       └── storage_port.py          # Abstract file storage interface
├── infrastructure/                   # Adapters (implementations)
│   ├── persistence/
│   │   ├── postgres_transaction_repo.py
│   │   └── pgvector_embedding_repo.py
│   ├── ai/
│   │   ├── langgraph_pipeline.py
│   │   ├── claude_adapter.py
│   │   └── bge_m3_adapter.py
│   ├── ingestion/
│   │   ├── monobank_csv_parser.py
│   │   ├── monobank_pdf_parser.py
│   │   ├── privatbank_csv_parser.py
│   │   └── privatbank_pdf_parser.py
│   └── cache/
│       └── redis_cache.py
└── presentation/                     # FastAPI routes
    ├── api/v1/
    └── dependencies.py               # DI wiring
```

**Key principles:**
1. **Domain layer has zero imports from infrastructure** — categorization logic, severity scoring, pattern detection rules are pure Python
2. **Ports define contracts** — LLM port is abstract; Claude adapter and any future local model adapter both implement it
3. **LangGraph pipeline is an infrastructure concern**, not domain — domain defines *what* to analyze; LangGraph defines *how* to orchestrate
4. **Value Objects for financial data** — Money amounts, currencies, categories are immutable with validation, not raw strings/floats

_Sources: [Hexagonal Architecture + DDD in Python](https://dev.to/hieutran25/building-maintainable-python-applications-with-hexagonal-architecture-and-domain-driven-design-chp), [AWS Hexagonal Architecture Pattern](https://docs.aws.amazon.com/prescriptive-guidance/latest/patterns/structure-a-python-project-in-hexagonal-architecture-using-aws-lambda.html)_

### PDF Bank Statement Parsing Architecture

**V1 requirement: CSV + PDF ingestion with dual-path strategy** _(Confidence: HIGH)_

**PDF parsing library comparison:**

| Library | Table Extraction | Speed | Best For |
|---------|-----------------|-------|----------|
| **pdfplumber** | Excellent (complex tables) | Medium | Bank statement tables with fine-grained control |
| **Camelot** | Good (bordered tables) | Medium | Tables with visible borders/grid lines |
| **Docling** | Excellent (97.9% cell accuracy) | 6.3s/page | Enterprise-grade accuracy |
| **PyMuPDF (fitz)** | Good | Very fast (42ms) | High-speed text extraction |
| **tabula-py** | Basic (requires JVM) | Fast | Simple tables only |

**Recommendation: pdfplumber for V1** — best control for complex tables, no external dependencies (no JVM), strongest community support for bank statement parsing. Docling as upgrade path for higher accuracy.

**Dual CSV/PDF ingestion architecture:**

```
User Upload
    │
    ▼
[Format Detector] ── detects by extension + magic bytes
    │
    ├──▶ CSV Path:  csv_parser.py   ──▶ normalize ──▶ CommonTransaction
    ├──▶ PDF Path:  pdf_parser.py   ──▶ normalize ──▶ CommonTransaction
    └──▶ XLS Path:  xls_parser.py   ──▶ normalize ──▶ CommonTransaction
    │
    ▼
[Bank Detector] ── identifies bank from content patterns (headers, IBAN format)
    │
    ▼
[Bank-Specific Parser] ── per-bank logic for column mapping, date/amount parsing
    │
    ▼
[Validation Layer] ── check dates, amounts, balances, duplicates
    │
    ▼
[Storage] ── PostgreSQL with CommonTransaction model
```

**Strategy pattern for parsers:**

```python
class BankParser(Protocol):
    def parse(self, file: UploadedFile) -> list[CommonTransaction]: ...
    def detect(self, file: UploadedFile) -> bool: ...

# Implementations:
# MonobankCsvParser, MonobankPdfParser
# PrivatBankCsvParser, PrivatBankPdfParser
```

**LLM fallback for unknown PDF formats:**
- Attempt pdfplumber rule-based extraction first (free)
- If validation fails (missing columns, parse errors, low row count), send PDF to Claude API
- Claude has best PDF table understanding among LLMs (~1,500-3,000 tokens/page)
- Cost-efficient: LLM only used when rule-based parsing fails

**Monobank PDF statement columns** (Ukrainian headers):
- Дата (Date/Time)
- Опис операцiї (Description)
- Сума (Amount)
- Комiсiя (Commission)
- Кешбек (Cashback)
- Залишок (Balance)

**PrivatBank PDF statement columns:**
- Номер документа (Document Number)
- Дата операції (Operation Date)
- IBAN / Account Number
- Найменування контрагента (Counterparty Name)
- Дебет / Кредит (Debit / Credit — separate columns)
- Призначення платежу (Payment Purpose)
- Залишок (Balance)

**PDF parsing best practices for Ukrainian bank statements:**
- Detect and skip repeated headers on multi-page tables
- Match against known Ukrainian column names with fuzzy matching
- Ukrainian locale: comma as decimal separator, space as thousands separator (`1 234,56`)
- Parse amounts: `amount_str.replace(' ', '').replace(',', '.')` → `Decimal()`
- Date formats: `DD.MM.YYYY` or `DD.MM.YYYY HH:MM:SS`
- Credit/Debit may be separate columns (PrivatBank) or combined with +/- (Monobank)
- Hash file contents for idempotent processing (prevent duplicate imports)

**Critical risk:** Get real Monobank and PrivatBank PDF statements early to validate parsing logic. Exact column positions and formatting can only be confirmed with real documents.

_Sources: [pdfplumber GitHub](https://github.com/jsvine/pdfplumber), [Docling PDF benchmark 2025](https://procycons.com/en/blogs/pdf-data-extraction-benchmark/), [Camelot comparison](https://github.com/camelot-dev/camelot/wiki/Comparison-with-other-PDF-Table-Extraction-libraries-and-tools), [Claude PDF support](https://platform.claude.com/docs/en/build-with-claude/pdf-support), [bank-statement-parser architecture](https://github.com/felgru/bank-statement-parser)_

### Database Architecture

**PostgreSQL schema with pgvector, RLS, and time-series partitioning** _(Confidence: HIGH)_

```sql
-- Row-Level Security for multi-tenant isolation
ALTER TABLE transactions ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON transactions
  USING (user_id = current_setting('app.current_user_id')::uuid);

-- Transaction storage (partitioned by month)
CREATE TABLE transactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id),
    external_id TEXT,                    -- Monobank/PrivatBank transaction ID
    amount NUMERIC(15,2) NOT NULL,
    currency VARCHAR(3) DEFAULT 'UAH',
    description TEXT,
    mcc_code INTEGER,
    category VARCHAR(100),              -- AI-assigned
    category_confidence FLOAT,
    original_date TIMESTAMPTZ NOT NULL,
    source_bank VARCHAR(50),            -- 'monobank', 'privatbank'
    source_format VARCHAR(10),          -- 'csv', 'pdf', 'api'
    metadata JSONB,                      -- Flexible extra fields
    created_at TIMESTAMPTZ DEFAULT now()
) PARTITION BY RANGE (original_date);

-- Embedding storage alongside relational data
CREATE TABLE education_embeddings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    content_id UUID REFERENCES education_content(id),
    embedding vector(1024),              -- BGE-M3 dimension
    model_version VARCHAR(50),
    created_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX ON education_embeddings USING hnsw (embedding vector_cosine_ops);

-- AI-generated insight cards
CREATE TABLE insights (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id),
    insight_type VARCHAR(50),            -- 'spending_alert', 'educational', 'pattern'
    severity VARCHAR(20),                -- 'critical', 'warning', 'info'
    headline TEXT NOT NULL,
    education_content JSONB,             -- Progressive disclosure layers
    context JSONB,                       -- Supporting transaction data
    is_read BOOLEAN DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Cumulative financial profile
CREATE TABLE financial_profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID UNIQUE NOT NULL REFERENCES users(id),
    health_score FLOAT,                  -- 0-100
    monthly_summaries JSONB,             -- Aggregated spending by category
    pattern_data JSONB,                  -- Detected recurring patterns
    literacy_level VARCHAR(20),          -- 'beginner', 'intermediate', 'advanced'
    total_uploads INTEGER DEFAULT 0,
    last_upload_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ DEFAULT now()
);
```

**Key decisions:**
- **JSONB for flexible aggregations** — `monthly_summaries`, `pattern_data`, `education_content` use JSONB for schema flexibility during rapid iteration
- **Time-series partitioning** — monthly partitions on transactions enable efficient range queries and data retention policies
- **RLS for tenant isolation** — application sets `SET app.current_user_id` on each connection; critical: connect as non-owner role
- **pgvector alongside relational** — single DB for relational + vector, unified backup/restore, JOIN similarity with metadata

_Sources: [AWS RLS multi-tenant](https://aws.amazon.com/blogs/database/multi-tenant-data-isolation-with-postgresql-row-level-security/), [Crunchy Data RLS](https://www.crunchydata.com/blog/row-level-security-for-tenants-in-postgres), [pgvector GitHub](https://github.com/pgvector/pgvector)_

### Deployment Architecture

**Phase-based deployment strategy optimized for budget** _(Confidence: HIGH)_

| Platform | Basic VM | Managed PG | GPU | Best For |
|----------|----------|------------|-----|----------|
| **Render** | $7/mo | Free 1GB / $7/mo | No | Lowest cost MVP |
| **Fly.io** | ~$10.70/mo | ~$33.90/mo | Yes (A10, A100) | Scale with GPU |
| **Railway** | ~$30/mo | Yes | No | Usage-based simplicity |

**Phase 1 — Capstone/MVP (Render, ~$30-35/mo):**
- FastAPI web service: $7/mo
- Celery worker (background): $7/mo
- PostgreSQL (persistent): $7/mo
- Redis: $10/mo managed
- Next.js frontend: Vercel free tier (global CDN included)

**Phase 2 — Production (Fly.io, ~$80-150/mo):**
- GPU instances for BGE-M3 if self-hosting
- Lower per-unit compute costs at scale
- Edge deployment for Ukrainian users

**BGE-M3 deployment specifics:**
- ~1.06 GB VRAM (float16) or ~270 MB (int4 quantized)
- **CPU inference is viable for MVP** — set `use_fp16=False`, latency ~200-500ms per batch vs ~50ms on GPU
- Budget option: HuggingFace Inference Endpoints or quantized model on CPU, cache aggressively with Redis

_Sources: [Fly.io vs Railway 2026](https://thesoftwarescout.com/fly-io-vs-railway-2026-which-developer-platform-should-you-deploy-on/), [Render FastAPI deployment](https://dev.to/jod35/deploying-fastapi-postgresql-celery-redis-on-render-fastapi-beyond-crud-part-23-5ha0), [BGE-M3 memory requirements](https://huggingface.co/BAAI/bge-m3/discussions/64)_

### Caching & Performance Architecture

**Multi-layer Redis caching strategy** _(Confidence: HIGH)_

| Cache Layer | Purpose | TTL | Impact |
|-------------|---------|-----|--------|
| **Embedding Cache** | Cache BGE-M3 embeddings for identical queries | 24h | 85.4% latency reduction |
| **Semantic Cache** | Cache LLM-generated insights by semantic similarity | 1h | 50-80% LLM cost reduction |
| **Application Cache** | Financial profile summaries, category mappings | 1h or until new upload | Reduce DB load |
| **CDN (Vercel)** | Static educational content, frontend assets | Long | Global edge delivery |

**Semantic caching pattern (Redis LangCache):**
- Caches LLM responses based on semantic similarity (cosine threshold 0.3), not exact query match
- Saves 1-5 seconds per cache hit by skipping the LLM call entirely
- Stream response to user, cache complete response after streaming finishes
- Preload high-traffic queries (common financial education questions)

**Embedding cache (Redis EmbeddingsCache):**
- Batch operations (`mset`/`mget`) are 15-20x faster than individual operations
- Async API support for FastAPI integration
- Cache invalidation: on model version change only

_Sources: [Redis EmbeddingsCache](https://redis.io/docs/latest/develop/ai/redisvl/user_guide/embeddings_cache/), [Redis Semantic Caching](https://redis.io/blog/what-is-semantic-caching/), [Redis LangCache](https://redis.io/langcache/)_

### Scalability Patterns

**Horizontal scaling with Celery + Redis** _(Confidence: HIGH)_

- Redis broker achieves **5,200 tasks/sec** with 12ms average latency
- Horizontal worker scaling is **near-linear up to 16 workers** (88% efficiency)
- Use `worker_prefetch_multiplier=1` to prevent worker overload
- Route task types to dedicated workers: `ingestion_worker`, `ai_pipeline_worker`, `notification_worker`

**Database scaling path:**
1. **PgBouncer** in transaction pooling mode (immediate)
2. **Read replica** for financial summaries, insight retrieval (when needed)
3. **Connection pooling**: `NullPool` in SQLAlchemy, let PgBouncer handle all pooling

**Queue-based load leveling** is built into the architecture:
- User uploads → API returns 202 immediately
- Tasks queue in Redis under load rather than overloading AI pipeline
- Workers process at their own pace; users notified via SSE when complete

_Sources: [Celery + Redis + FastAPI 2025](https://medium.com/@dewasheesh.rana/celery-redis-fastapi-the-ultimate-2025-production-guide-broker-vs-backend-explained-5b84ef508fa7), [High Availability Celery (Six Feet Up)](https://www.sixfeetup.com/blog/high-availability-scaling-with-celery)_

## Implementation Approaches and Technology Adoption

### CI/CD Pipeline

**GitHub Actions with uv + Ruff + pytest, auto-deploy to Render** _(Confidence: HIGH)_

| Tool | Purpose | Replaces |
|------|---------|----------|
| **uv** | Dependency management (fast) | pip/poetry |
| **Ruff** | Linting + formatting | flake8 + black |
| **mypy** | Static type checking | — |
| **pytest** | Testing with `--cov` | — |
| **bandit** | Security vulnerability scanning | — |
| **DeepEval** | RAG/LLM evaluation metrics in CI | Custom LLM tests |

**Workflow structure:**
- **PR checks:** lint (Ruff) → type check (mypy) → test (pytest + DeepEval) → security (bandit)
- **Merge to main:** Docker build → push to GHCR → trigger Render deploy hook
- **Caching:** `astral-sh/setup-uv@v5` with `enable-cache: true` for fast dependency restoration
- **AI-specific CI:** snapshot/golden-file tests for embedding outputs, DeepEval for RAG quality metrics

**Reference template:** [fastapi-production-template](https://github.com/ArmanShirzad/fastapi-production-template) — one-click Render deployment, multi-stage Docker builds (non-root user), pre-configured CI/CD workflows.

_Sources: [GitHub Actions for Python 2025](https://ber2.github.io/posts/2025_github_actions_python/), [FastAPI Production Template](https://github.com/ArmanShirzad/fastapi-production-template), [Python CI/CD Pipeline Guide 2025](https://atmosly.com/blog/python-ci-cd-pipeline-mastery-a-complete-guide-for-2025)_

### Testing Strategy for AI/LLM Pipelines

**Two-level LangGraph testing + DeepEval RAG evaluation** _(Confidence: HIGH)_

**Level 1 — Unit Testing Nodes:**
- Test individual LangGraph nodes in isolation
- Mock LLM layer using LangChain's `GenericFakeChatModel` (accepts iterator of canned `AIMessage` responses)
- Test state parsing, state updates, error handling — all deterministic parts

**Level 2 — Graph Flow Path Testing:**
- Test edges route correctly between nodes given specific state conditions
- Verify full graph traverses expected path with mocked services
- Use `pytest-asyncio` for async node tests

**Test folder structure:**
```
tests/
  test_nodes/           # individual node tests
  test_flows/           # graph path tests
  test_parsers/         # CSV/PDF parser tests
  test_rag/             # RAG quality with DeepEval
  conftest.py           # shared fixtures, mock LLM setup
```

**RAG Pipeline Evaluation with DeepEval (14k+ GitHub stars):**

| Metric | What It Measures |
|--------|-----------------|
| **Faithfulness** | Does response factually align with retrieved context? |
| **Contextual Recall** | Did you retrieve the relevant documents? |
| **Contextual Precision** | Are relevant chunks ranked higher? |
| **Contextual Relevancy** | Is retrieval context relevant to query? |
| **Answer Relevancy** | Does final answer address the user's question? |

DeepEval integrates directly into CI via `deepeval test run`. Uses LLM-as-a-judge and local NLP models for scoring.

**HTTP Request Recording:** Use **vcrpy** or **pytest-recording** to record and replay LLM API calls for deterministic tests without live API costs.

_Sources: [Unit Testing LangGraph Nodes and Flow Paths](https://medium.com/@anirudhsharmakr76/unit-testing-langgraph-testing-nodes-and-flow-paths-the-right-way-34c81b445cd6), [DeepEval RAG Evaluation](https://deepeval.com/guides/guides-rag-evaluation), [How to Mock LangChain LLM in Tests](https://medium.com/@matgmc/how-to-properly-mock-langchain-llm-execution-in-unit-tests-python-76efe1b8707e)_

### Monitoring and Observability

**Start with LangSmith free tier, migrate to self-hosted Langfuse when needed** _(Confidence: HIGH)_

| Factor | LangSmith (free tier) | Langfuse (self-hosted) |
|--------|----------------------|------------------------|
| **Cost** | Free: 5k traces/mo | $0 (infrastructure only) |
| **Setup** | 2 env vars | Docker Compose (~2 min) |
| **LangGraph integration** | Native (zero-config) | Via CallbackHandler |
| **Self-hosting** | Enterprise-only | MIT license, Docker Compose |
| **Cost tracking** | Feature-based spend | Token usage monitoring |

**What to monitor:**
- Trace latency per agent in the 5-agent pipeline
- RAG retrieval quality (precision/recall over time)
- Token usage and cost per API call and per agent
- Error rates and LLM response degradation
- Embedding generation latency (BGE-M3 on CPU)

**Recommendation:** LangSmith free tier for MVP (zero-config LangGraph tracing, 5k traces/mo). If you outgrow it or need data ownership, migrate to self-hosted Langfuse (requires PG + ClickHouse + Redis, ~4 vCPUs, 16 GB RAM).

_Sources: [Langfuse vs LangSmith 2026](https://markaicode.com/vs/langfuse-vs-langsmith/), [Langfuse self-hosting](https://langfuse.com/self-hosting), [Best LLM Observability Tools 2026](https://www.firecrawl.dev/blog/best-llm-observability-tools)_

### LLM Cost Optimization

**Four-tier strategy for 50-87% cost reduction** _(Confidence: HIGH)_

| Tier | Strategy | Savings | Effort |
|------|----------|---------|--------|
| **1. Prompt optimization** | Compress prompts, use prompt caching (Anthropic: 90% cost reduction on cached prefixes) | 15-40% | Days |
| **2. Model cascading** | Route 90% of simple queries to cheaper models (Haiku/GPT-4o-mini), escalate complex to premium | ~87% | Weeks |
| **3. Semantic caching** | Redis `RedisSemanticCache` — match similar queries, skip LLM call entirely | 15-30% additional | Days |
| **4. RAG optimization** | Retrieve only relevant chunks, cache common Q&A pairs | 70%+ context reduction | Built-in |

**LiteLLM Proxy** recommended as AI gateway:
- Unified OpenAI-compatible interface for 100+ LLM APIs
- Per-key budget limits and cost tracking
- Model fallback and load balancing
- Integrates directly into FastAPI backend

**Batch processing optimal sizes:** text generation (10-50 requests), classification (100-500), Q&A (50-200). Reduces overhead by up to 90%.

_Sources: [LLM Cost Optimization 80% Reduction](https://ai.koombea.com/blog/llm-cost-optimization), [Prompt Caching 60% Cost Reduction](https://medium.com/tr-labs-ml-engineering-blog/prompt-caching-the-secret-to-60-cost-reduction-in-llm-applications-6c792a0ac29b), [LiteLLM Cost Tracking](https://docs.litellm.ai/docs/proxy/cost_tracking), [Redis Semantic Caching](https://redis.io/blog/what-is-semantic-caching/)_

### Development Environment

**Docker Compose local stack** _(Confidence: HIGH)_

| Service | Image | Port | Purpose |
|---------|-------|------|---------|
| **FastAPI app** | Custom Dockerfile | 8000 | API server with hot-reload |
| **PostgreSQL + pgvector** | `pgvector/pgvector:pg17` | 5432 | DB + vector storage |
| **Redis** | `redis:7-alpine` | 6379 | Celery broker + semantic cache |
| **Celery worker** | Same app image | — | Background AI pipeline processing |
| **Celery Beat** | Same app image | — | Scheduled tasks |
| **Ollama** (optional) | `ollama/ollama` | 11434 | Local LLM/embedding testing |

**Key setup details:**
- pgvector init SQL: `CREATE EXTENSION IF NOT EXISTS vector;` mounted at `/docker-entrypoint-initdb.d/`
- BGE-M3 available in Ollama: `ollama pull bge-m3` (567M, runs on CPU)
- Local LLM testing: `ollama pull llama3.2` (3B params, no API costs)
- Environment variables: `.env` files with Docker Compose `env_file` directive; `.env.example` in repo, `.env` in `.gitignore`

_Sources: [Local AI Development Stack with Docker Compose](https://markaicode.com/docker-compose-local-ai-stack/), [pgvector Docker Setup](https://www.sarahglasmacher.com/how-to-pgvector-docker-local-vector-database/), [Ollama BGE-M3](https://ollama.com/library/bge-m3)_

### RAG Knowledge Base Seeding (Ukrainian Financial Content)

**Primary source: NBU financial literacy ecosystem** _(Confidence: MEDIUM-HIGH)_

| Source | Content Type | Language | Access |
|--------|-------------|----------|--------|
| **Harazd (harazd.gov.ua)** | Personal finance education articles | Ukrainian | Free, public website |
| **Financial Competencies Framework** | Taxonomy of financial knowledge areas | Ukrainian | NBU publication |
| **National Financial Literacy Strategy 2030** | 5 strategic areas (budgeting, saving, credit, digital literacy, entrepreneurship) | Ukrainian | NBU publication |
| **Talan (talan.bank.gov.ua)** | Structured education materials | Ukrainian | Free, educator platform |
| **NBU YouTube Channel** | Video content (transcribable) | Ukrainian | Free |

**Seeding pipeline:**
1. **Ingest:** pdfplumber for PDFs, BeautifulSoup/Scrapy for web content
2. **Chunk:** Semantic chunking by section/paragraph (respect financial topic boundaries)
3. **Embed:** BGE-M3 handles Ukrainian natively (100+ languages, 1024-dim)
4. **Store:** PostgreSQL + pgvector with metadata (source, topic_category, language, difficulty_level, last_updated)
5. **Index:** HNSW index for fast retrieval

**Content phases:**
- **Phase 1 (V1):** Harazd articles, Financial Competencies Framework, basic budgeting/saving/spending education
- **Phase 2:** Ukrainian tax summaries, banking product comparisons, insurance basics, pension system
- **Phase 3:** NBU exchange rates, inflation impact, Deposit Guarantee Fund updates

**Bilingual handling:** BGE-M3's multilingual capability allows Ukrainian and English content to coexist in the same vector space. Cross-language retrieval works — Ukrainian queries find relevant English documents and vice versa.

_Sources: [NBU Financial Literacy Strategy](https://bank.gov.ua/en/about/strategy-fin-literacy), [NBU Harazd website](https://bank.gov.ua/en/news/all/natsionalniy-bank-zapustiv-sayt-z-finansovoyi-gramotnosti-garazd), [NBU Financial Competencies Framework](https://bank.gov.ua/en/news/all/oprilyudneno-ramku-finansovih-kompetentnostey-doroslogo-naselennya-ukrayini)_

### Risk Assessment and Mitigation

| Risk | Severity | Mitigation |
|------|----------|------------|
| **Ukrainian financial data scarcity** | HIGH | Augment with translated English data; RAG reduces fine-tuning data needs |
| **PDF format assumptions** | HIGH | Get real Monobank/PrivatBank PDFs early; LLM fallback for unknown formats |
| **LLM cost overrun** | MEDIUM | Model cascading (87% savings), prompt caching, semantic caching, budget caps via LiteLLM |
| **Embedding quality for Ukrainian** | MEDIUM | BGE-M3 confirmed Ukrainian support; test with real financial queries; consider Ukrainian-specific fine-tuning |
| **Monobank API rate limits** | LOW | 1 req/60s handled by async queue; CSV/PDF upload as primary V1 path |
| **GDPR-harmonization uncertainty** | MEDIUM | Build to GDPR standards now; right to erasure, data minimization, audit logging |
| **Solo developer bus factor** | HIGH | Modular monolith with clean architecture; comprehensive tests; documented architecture decisions |

## Technical Research Recommendations

### Implementation Roadmap

**Phase 1 — Foundation (Weeks 1-4):**
- Set up Docker Compose local dev environment (FastAPI + PG/pgvector + Redis + Celery)
- Implement auth module (JWT + refresh tokens + RLS)
- Build Monobank CSV parser + PDF parser (pdfplumber)
- Seed RAG knowledge base from NBU Harazd content
- Set up CI/CD (GitHub Actions → Render)

**Phase 2 — AI Pipeline (Weeks 5-8):**
- Implement LangGraph StateGraph with 5 agents
- Build Ingestion Agent (CSV/PDF → CommonTransaction)
- Build Categorization Agent (MCC + AI classification)
- Build Pattern Detection Agent (recurring charges, spending trends)
- Set up BGE-M3 embeddings on CPU + pgvector HNSW index

**Phase 3 — Education & UX (Weeks 9-12):**
- Build Triage Agent (severity ranking)
- Build Education Agent (RAG-powered, pgvector retrieval)
- Implement Teaching Feed API (REST + cursor pagination)
- Build Next.js frontend (Teaching Feed cards, upload flow, SSE progress)
- Implement Financial Health Score

**Phase 4 — Polish & Launch (Weeks 13-16):**
- PrivatBank CSV/PDF parser support
- Bilingual support (UK/EN)
- Email notifications (upload reminders)
- Freemium model + Fondy payment integration
- LangSmith monitoring setup
- Performance optimization (Redis caching layers)
- Deploy to Render

### Technology Stack Summary

| Layer | Technology | Rationale |
|-------|-----------|-----------|
| **Backend** | Python 3.12+ / FastAPI | Async, type-safe, LangChain ecosystem |
| **AI Framework** | LangGraph | Deterministic, auditable, human-in-the-loop |
| **Database** | PostgreSQL + pgvector | ACID + vector search in one DB |
| **Task Queue** | Celery + Redis | 5,200 tasks/sec, near-linear horizontal scaling |
| **Embeddings** | BGE-M3 (self-hosted, CPU) | Free, Ukrainian support, hybrid retrieval |
| **PDF Parsing** | pdfplumber | Best table extraction, no JVM |
| **Frontend** | Next.js on Vercel | SSR, free CDN, Vercel AI SDK for SSE |
| **Deployment** | Render (MVP) → Fly.io (scale) | $30/mo MVP, GPU when needed |
| **Monitoring** | LangSmith free → Langfuse | Zero-config → self-hosted |
| **Payments** | Fondy (Ukraine) + LemonSqueezy (intl) | Stripe unavailable in Ukraine |
| **CI/CD** | GitHub Actions + uv + Ruff + DeepEval | Free, fast, AI-aware testing |

### Key Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| **CSV/PDF parsing accuracy** | >95% transactions correctly parsed | Compare parsed output vs manual verification |
| **RAG retrieval quality** | >85% contextual recall (DeepEval) | Automated evaluation in CI |
| **Pipeline latency** | <30 seconds for full 5-agent pipeline | LangSmith trace monitoring |
| **Embedding latency** | <500ms per query on CPU | Redis cache hit rate + raw latency |
| **LLM cost per upload** | <$0.10 per statement processing | LiteLLM cost tracking |
| **First-upload completion** | >80% (upload → view insight) | Product analytics |
| **Monthly infrastructure cost** | <$35 for MVP | Render dashboard |

---

## Technical Research Conclusion

### Summary of Key Findings

This research confirms the technical viability of building an AI-powered financial education platform for the Ukrainian market. The technology landscape in 2025-2026 provides every component needed:

1. **The RAG-first approach is validated** — it solves the Ukrainian financial data scarcity problem, provides citation traceability for financial advice, and costs significantly less to maintain than fine-tuning. The hybrid evolution path (RAG now, fine-tuned MamayLM later) is well-supported by both academic research (ICLR 2026) and industry practice.

2. **Ukrainian language support is mature enough** — BGE-M3, Jina-embeddings-v3, and Qwen3-Embedding all explicitly support Ukrainian. MamayLM provides a state-of-the-art Ukrainian LLM foundation for future fine-tuning. The NBU's financial literacy ecosystem (Harazd, Financial Competencies Framework) offers ready-made Ukrainian educational content for the RAG knowledge base.

3. **The infrastructure cost is remarkably low** — a production-ready MVP can run for ~$30-35/mo on Render, with BGE-M3 viable on CPU and pgvector eliminating the need for a separate vector database. This makes the product accessible as both a capstone project and a viable startup.

4. **The multi-agent pipeline has strong framework support** — LangGraph provides exactly the deterministic, auditable execution model needed for financial data processing, with built-in checkpointing, human-in-the-loop, and state versioning that directly address governance concerns.

5. **PDF parsing is solvable** — pdfplumber handles Monobank/PrivatBank table extraction, with Claude API as an intelligent fallback. The strategy pattern enables clean multi-bank, multi-format extensibility.

### Strategic Technical Impact

The technical architecture positions the product for:
- **Immediate differentiation** — no existing Ukrainian product combines AI-powered financial analysis with personalized education
- **Low barrier to entry** — $30-35/mo infrastructure, open-source stack, solo-developer-friendly architecture
- **Clear scaling path** — modular monolith → service extraction, pgvector → Qdrant, Render → Fly.io, CPU → GPU
- **Cumulative technical moat** — each upload builds the user's financial profile, making the product more valuable over time

### Next Steps

1. **Obtain real Monobank and PrivatBank PDF statements** to validate parsing assumptions (highest-risk item)
2. **Set up Docker Compose development environment** with pgvector, Redis, and Celery
3. **Prototype the Monobank CSV parser** and verify against real transaction data
4. **Seed a minimal RAG knowledge base** from NBU Harazd content to test BGE-M3 Ukrainian retrieval quality
5. **Build a single LangGraph agent** (Categorization) end-to-end to validate the pipeline architecture before building all five

---

**Technical Research Completion Date:** 2026-03-15
**Research Scope:** Comprehensive technical analysis across AI approach, data ingestion, vector storage, multi-agent architecture, integration patterns, deployment, and implementation
**Sources:** 50+ web searches verified across academic papers, industry reports, official documentation, and technical benchmarks
**Confidence Level:** HIGH — based on multiple authoritative sources with cross-validation

_This technical research document serves as the architectural foundation for the kōpiika product, providing evidence-based technology decisions and a clear implementation roadmap._
