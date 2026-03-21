---
research_type: 'technical'
research_topic: 'Integration Patterns for RAG-Based Multi-Agent Financial AI Pipeline'
research_goals: 'Research integration patterns for LangGraph multi-agent pipeline, RAG with pgvector/BGE-M3, file upload workflows, state management, real-time notifications, and security for Ukrainian financial data'
user_name: 'Oleh'
date: '2026-03-15'
web_research_enabled: true
source_verification: true
---

# Integration Patterns for RAG-Based Multi-Agent Financial AI Pipeline

**Date:** 2026-03-15
**Context:** Multi-agent AI pipeline for Ukrainian financial data analysis
**Stack:** LangGraph, pgvector, BGE-M3 embeddings
**Pipeline:** Ingestion -> Categorization -> Pattern Detection -> Triage -> Education (RAG)

---

## 1. LangGraph Multi-Agent Pipeline Patterns

**Confidence: HIGH** -- Extensively documented with official LangChain docs, production guides, and multiple 2025-2026 implementation references.

### 1.1 Core Architecture: StateGraph with Typed State

LangGraph models multi-agent pipelines as directed graphs where **nodes are agents** and **edges define data flow**. The central construct is `StateGraph`, which maintains a centralized typed state object passed between all nodes.

**State Definition Pattern (TypedDict + Reducers):**

```python
from typing import TypedDict, Annotated, Optional
from operator import add
from langgraph.graph import StateGraph

class FinancialPipelineState(TypedDict):
    # Accumulated messages across all agents
    messages: Annotated[list, add]
    # Raw CSV data from ingestion
    raw_transactions: list[dict]
    # Categorized transactions from categorization agent
    categorized_transactions: list[dict]
    # Detected patterns from pattern detection agent
    patterns: list[dict]
    # Triage priority and flags
    triage_result: Optional[dict]
    # RAG education content
    education_response: Optional[str]
    # Pipeline metadata
    current_step: str
    user_id: str
    processing_errors: Annotated[list, add]
```

Reducers (the second argument in `Annotated[type, reducer]`) define **how state updates are merged** when multiple nodes write to the same field. The `add` operator appends to lists; custom reducers can merge dicts or handle domain-specific logic.

**Key insight:** Agents communicate exclusively through the centralized state object -- no direct peer-to-peer messaging. Each agent reads current state as input and returns a partial state update.

### 1.2 Conditional Routing Between Agents

The `add_conditional_edges()` method enables dynamic routing based on current state. This is critical for the financial pipeline where, for example, triage results determine whether to route to education or to flag for human review.

```python
def triage_router(state: FinancialPipelineState) -> str:
    triage = state["triage_result"]
    if triage["priority"] == "high_risk":
        return "human_review"
    elif triage["needs_education"]:
        return "education_agent"
    else:
        return "complete"

builder.add_conditional_edges(
    "triage_agent",
    triage_router,
    ["human_review", "education_agent", "complete"]
)
```

Three arguments are required: source node, routing function, and list of possible destinations.

### 1.3 Human-in-the-Loop for Financial Workflows

LangGraph provides two core mechanisms: `interrupt` (pauses graph execution) and `Command` (resumes with human input and state updates).

**Pattern: Approval gate for high-value financial insights**

```python
from langgraph.types import interrupt, Command

def human_review_node(state):
    # Pause and surface data to human
    decision = interrupt({
        "flagged_patterns": state["patterns"],
        "risk_level": state["triage_result"]["priority"],
        "question": "Approve analysis results before sending to user?"
    })
    # Resume with human decision
    if decision["approved"]:
        return {"current_step": "education_agent"}
    else:
        return {"current_step": "rejected", "messages": [decision["feedback"]]}
```

**Financial use cases for HITL:**
- Approval gates for flagged spending patterns before user notification
- Human override for categorization confidence below threshold
- Review of AI-generated financial education content before delivery

LangGraph persists execution state via **checkpointing**, so the workflow can pause indefinitely while awaiting human input (async review over hours/days).

### 1.4 Subgraphs for Modular Agent Design

Each pipeline agent can be its own subgraph, enabling independent development and testing. Handoffs between subgraphs use `Command(goto="target_agent", update={...}, graph=Command.PARENT)`.

**Pipeline execution patterns:**
- **Sequential pipeline** (your primary flow): Ingestion -> Categorization -> Pattern Detection -> Triage -> Education
- **Scatter-gather**: Distribute categorization to multiple specialized agents, consolidate results
- **Pipeline parallelism**: Categorization and pattern detection run concurrently on overlapping data

### Sources

- [LangGraph Multi-Agent Orchestration: Complete Framework Guide 2025](https://latenode.com/blog/ai-frameworks-technical-infrastructure/langgraph-multi-agent-orchestration/langgraph-multi-agent-orchestration-complete-framework-guide-architecture-analysis-2025)
- [Mastering LangGraph State Management in 2025](https://sparkco.ai/blog/mastering-langgraph-state-management-in-2025)
- [Agentic AI with LangGraph: Orchestrating Multi-Agent Workflows in 2026](https://adspyder.io/blog/agentic-ai-with-langgraph/)
- [Production Multi-Agent System with LangGraph: State Checkpointing, Error Recovery](https://markaicode.com/langgraph-production-agent/)
- [Human-in-the-loop -- LangChain Docs](https://docs.langchain.com/oss/python/langchain/human-in-the-loop)
- [Human in the loop (HITL) AI Agents with LangGraph & Elastic](https://www.elastic.co/search-labs/blog/human-in-the-loop-hitllanggraph-elasticsearch)
- [Human-in-the-Loop AI: Time-Travel Workflows with LangGraph](https://christianmendieta.ca/human-in-the-loop-ai-time-travel-workflows-with-langgraph/)
- [LangGraph 201: Adding Human Oversight -- Towards Data Science](https://towardsdatascience.com/langgraph-201-adding-human-oversight-to-your-deep-research-agent/)
- [Advanced LangGraph: Implementing Conditional Edges and Tool-Calling Agents](https://dev.to/jamesli/advanced-langgraph-implementing-conditional-edges-and-tool-calling-agents-3pdn)
- [Mastering State Reducers in LangGraph: A Complete Guide](https://medium.com/data-science-collective/mastering-state-reducers-in-langgraph-a-complete-guide-b049af272817)
- [Build multi-agent systems with LangGraph and Amazon Bedrock](https://aws.amazon.com/blogs/machine-learning/build-multi-agent-systems-with-langgraph-and-amazon-bedrock/)
- [Graph API overview -- LangChain Docs](https://docs.langchain.com/oss/python/langgraph/graph-api)

---

## 2. RAG Pipeline Integration with LangChain/LangGraph

**Confidence: HIGH** -- Direct tutorials exist for LangChain + pgvector + BGE-M3 integration, plus financial education chatbot examples.

### 2.1 pgvector + BGE-M3 Integration

**BGE-M3 key advantages for this project:**
- Supports **100+ languages** including Ukrainian -- critical for multilingual financial content
- Produces **1024-dimensional** dense embeddings
- Supports **hybrid retrieval**: dense embeddings + sparse (BM25-like) retrieval simultaneously
- Handles inputs up to **8192 tokens** -- accommodates long financial education documents
- Learns a common semantic space across languages, enabling both within-language and cross-language retrieval

**pgvector configuration for BGE-M3:**

```sql
-- Enable pgvector extension
CREATE EXTENSION vector;

-- Financial education content table
CREATE TABLE financial_education_docs (
    id SERIAL PRIMARY KEY,
    content TEXT NOT NULL,
    metadata JSONB,
    embedding vector(1024),  -- BGE-M3 dimension
    language VARCHAR(10),
    category VARCHAR(100),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- HNSW index for fast ANN search (recommended over IVFFlat for production)
CREATE INDEX ON financial_education_docs
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);
```

### 2.2 LangChain RAG Chain with pgvector

```python
from langchain_community.vectorstores import PGVector
from langchain_community.embeddings import HuggingFaceBgeEmbeddings

# BGE-M3 embeddings
embeddings = HuggingFaceBgeEmbeddings(
    model_name="BAAI/bge-m3",
    model_kwargs={"device": "cpu"},
    encode_kwargs={"normalize_embeddings": True}
)

# pgvector store
vectorstore = PGVector(
    collection_name="financial_education",
    connection_string=DATABASE_URL,
    embedding_function=embeddings,
)

# Retriever with search parameters
retriever = vectorstore.as_retriever(
    search_type="similarity",
    search_kwargs={"k": 5}
)
```

### 2.3 Agentic RAG Node in LangGraph

The recommended LangGraph pattern uses a **retrieve -> grade -> generate** flow:

1. **Query generation node**: Determines if retrieval is needed based on pipeline context
2. **Retrieval node**: Queries pgvector for relevant financial education content
3. **Document grading node**: Evaluates relevance of retrieved docs to the user's financial situation
4. **Generation node**: Synthesizes personalized financial education response

```python
def education_retrieve_node(state: FinancialPipelineState):
    """Retrieve relevant financial education content based on detected patterns."""
    query = build_education_query(state["patterns"], state["triage_result"])
    docs = retriever.invoke(query)
    return {"retrieved_docs": docs}

def education_grade_node(state: FinancialPipelineState):
    """Grade retrieved documents for relevance to user's financial situation."""
    graded = []
    for doc in state["retrieved_docs"]:
        score = grade_document_relevance(doc, state["patterns"])
        if score > 0.7:
            graded.append(doc)
    return {"graded_docs": graded}

def education_generate_node(state: FinancialPipelineState):
    """Generate personalized financial education response."""
    prompt = financial_education_prompt.format(
        patterns=state["patterns"],
        context=format_docs(state["graded_docs"]),
        language="Ukrainian"
    )
    response = llm.invoke(prompt)
    return {"education_response": response.content}
```

### 2.4 Prompt Templates for Financial Education

Financial education prompts should include:
- User's detected spending patterns as context
- Retrieved knowledge base content
- Language specification (Ukrainian)
- Tone guidance (educational, not judgmental)
- Specific actionable recommendations format

### 2.5 Hybrid Retrieval Recommendation

BGE-M3's multi-functionality enables **hybrid retrieval + re-ranking**, which is the recommended approach:
1. Dense retrieval via pgvector (semantic similarity)
2. Sparse retrieval via BM25 (keyword matching for financial terms)
3. Re-ranking of combined results for maximum relevance

### Sources

- [Build a RAG Chatbot with LangChain, pgvector, NVIDIA BGE-M3](https://zilliz.com/tutorials/rag/langchain-and-pgvector-and-nvidia-bge-m3-and-ollama-bge-m3)
- [BGE M3 Multilingual: Massive Embeddings for Global RAG Systems 2025](https://johal.in/bge-m3-multilingual-massive-embeddings-for-global-rag-systems-2025-3/)
- [BAAI/bge-m3 -- Hugging Face](https://huggingface.co/BAAI/bge-m3)
- [Build a custom RAG agent with LangGraph -- LangChain Docs](https://docs.langchain.com/oss/python/langgraph/agentic-rag)
- [Building a Financial Education Chatbot with RAG](https://medium.com/@hlealpablo/building-a-financial-education-chatbot-with-retrieval-augmented-generation-rag-bf338aa2df09)
- [Building an Autonomous Financial Research Analyst with Agents + RAG (LangGraph)](https://medium.com/@brijeshrn/building-an-autonomous-financial-research-analyst-with-agents-rag-langgraph-0d5bca823c54)
- [Implementing RAG with LangChain, Pgvector and OpenAI](https://codemancers.com/blog/2024-10-24-rag-with-langchain)
- [PGVector: Integrating PostgreSQL with LangChain for Advanced Similarity Search](https://medium.com/@rahulmydur/pgvector-integrating-postgresql-with-langchain-for-advanced-semantic-search-c8cabacaa79b)
- [Using LangChain and LangGraph to Build a RAG-Powered Chatbot](https://www.linode.com/docs/guides/using-langchain-langgraph-build-rag-powered-chatbot/)
- [Agentic RAG with Query Router Using LangGraph](https://sajalsharma.com/posts/agentic-rag-query-router-langgraph/)

---

## 3. CSV/File Upload Integration Patterns

**Confidence: HIGH** -- Well-established patterns with multiple production references.

### 3.1 Recommended Architecture: Async Upload + Queue + Background Workers

The proven pattern for AI processing pipelines decouples upload acknowledgment from processing:

```
Client uploads CSV
    -> API receives file, stores to disk/S3, returns job_id immediately (HTTP 202)
    -> Message queued (Redis/RabbitMQ/Celery)
    -> Background worker picks up job
    -> Runs through LangGraph pipeline (Ingestion -> ... -> Education)
    -> Updates job status in DB
    -> Notifies client via SSE/webhook
```

**Key principle:** Never process AI workloads synchronously in the upload request handler. Return immediately with a job tracking ID.

### 3.2 FastAPI Implementation Pattern

```python
from fastapi import FastAPI, UploadFile, BackgroundTasks
from uuid import uuid4

@app.post("/api/upload-transactions", status_code=202)
async def upload_transactions(
    file: UploadFile,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user)
):
    job_id = str(uuid4())

    # Save file to storage
    file_path = await save_upload(file, current_user.id, job_id)

    # Create job record
    await create_job(job_id, current_user.id, status="queued")

    # Queue for async processing
    background_tasks.add_task(
        run_financial_pipeline, job_id, file_path, current_user.id
    )

    return {"job_id": job_id, "status_url": f"/api/jobs/{job_id}/status"}
```

### 3.3 Progress Tracking

For long-running multi-agent pipelines, track progress per-agent:

```python
# Update progress as pipeline moves through agents
async def run_financial_pipeline(job_id, file_path, user_id):
    await update_job(job_id, status="processing", step="ingestion", progress=0)
    # ... run ingestion agent ...
    await update_job(job_id, step="categorization", progress=20)
    # ... run categorization agent ...
    await update_job(job_id, step="pattern_detection", progress=40)
    # ... and so on ...
    await update_job(job_id, step="complete", progress=100)
```

### 3.4 File Validation for Monobank CSV

Before queuing for processing, validate the uploaded file:
- Check MIME type (text/csv)
- Validate file size limits
- Parse header row to confirm expected Monobank format
- Return validation errors synchronously (before async processing begins)

### Sources

- [Building an Asynchronous Document-Processing System with Azure Functions, Queues, and AI Search](https://amrollahi.medium.com/building-an-asynchronous-document-processing-system-with-azure-functions-queues-and-ai-search-37f9e3993247)
- [Async File Uploads in FastAPI: Handling Gigabyte-Scale Data Smoothly](https://medium.com/@connect.hashblock/async-file-uploads-in-fastapi-handling-gigabyte-scale-data-smoothly-aec421335680)
- [Building a Scalable Asynchronous File Upload System: From Concept to Code](https://medium.com/@mahernaveed531/building-a-scalable-asynchronous-file-upload-system-from-concept-to-code-2c69aade351d)
- [Building Scalable AI Services: The Service Bus + Background Worker Pattern](https://www.caseyspaulding.com/blog/building-scalable-ai-services-the-service-bus-background-worker-pattern)
- [How We Scaled Large File Uploads: From Blocking API Calls to Async Processing](https://rohitsinghwd1993.medium.com/how-we-scaled-large-file-uploads-from-blocking-api-calls-to-async-processing-95fbb4681384)
- [Uploading Files Using FastAPI: A Complete Guide](https://betterstack.com/community/guides/scaling-python/uploading-files-using-fastapi/)

---

## 4. Multi-Agent State Management for Financial Data

**Confidence: HIGH** -- Strong architectural guidance from AWS, Deloitte, and LangGraph-specific implementations.

### 4.1 Financial Pipeline State Architecture

For the Ingestion -> Categorization -> Pattern Detection -> Triage -> Education pipeline, the state object serves as the **single source of truth** flowing through all agents.

**Five-layer agent architecture (AWS pattern for financial services):**
1. **Foundation layer**: Secure infrastructure, database connections
2. **Perception layer**: Data ingestion from CSV, standardizes formats
3. **Intelligence layer**: ML models + business rules (categorization, pattern detection)
4. **Action layer**: Workflow execution (triage decisions, education generation)
5. **Governance layer**: Compliance, audit logging, human oversight

### 4.2 State Immutability and Checkpointing

LangGraph creates a **new state version** on each agent update rather than mutating in place. This provides:
- Race condition prevention (critical for financial data integrity)
- Full audit trail of state changes (compliance requirement)
- Ability to "time travel" back to any pipeline stage
- Safe parallel execution of independent agents

**Checkpointing** persists state to storage (Postgres, Redis, or SQLite) after each node. If the pipeline fails at pattern detection, it can resume from the last checkpoint without re-running ingestion and categorization.

### 4.3 Transaction Context Preservation

For financial workflows, ensure transaction context is preserved across the full pipeline:

```python
class TransactionContext(TypedDict):
    """Context that flows through entire pipeline."""
    upload_id: str
    user_id: str
    file_metadata: dict          # Original file info
    date_range: dict             # Transaction date range
    total_transactions: int
    currency: str                # UAH for Ukrainian data
    processing_started_at: str
    agent_execution_log: Annotated[list[dict], add]  # Audit trail
```

### 4.4 Supervisor vs Sequential Orchestration

Two patterns from the financial AI literature:

- **Sequential pipeline** (recommended for your use case): Linear flow through agents, each receiving the full accumulated state. Simpler, easier to debug, sufficient for a fixed processing pipeline.
- **Supervisor pattern**: A supervisor agent dynamically dispatches subtasks to specialist agents. Better for open-ended queries, but adds complexity.

For the Ingestion -> Categorization -> Pattern Detection -> Triage -> Education flow, **sequential with conditional branching at triage** is the recommended pattern.

### Sources

- [Agentic AI in Financial Services: Choosing the Right Pattern for Multi-Agent Systems -- AWS](https://aws.amazon.com/blogs/industries/agentic-ai-in-financial-services-choosing-the-right-pattern-for-multi-agent-systems/)
- [Build an intelligent financial analysis agent with LangGraph and Strands Agents -- AWS](https://aws.amazon.com/blogs/machine-learning/build-an-intelligent-financial-analysis-agent-with-langgraph-and-strands-agents/)
- [Building a Multi-Agent Hierarchical AI System for Financial Data Analysis](https://medium.com/@krishnparasar/building-a-multi-agent-hierarchical-ai-system-for-financial-data-analysis-f81414d0340a)
- [Building Multi-Agent Workflows for Financial Data Aggregation and Classification](https://medium.com/@israelhilerio/agentic-workflows-financial-data-aggregation-langgraph-88258d0c9202)
- [AI Agents in Finance: Use Cases, Architecture, and Implementation Guide](https://www.agilesoftlabs.com/blog/2025/11/ai-agents-in-finance-use-cases)
- [Where is the value of AI in M&A: why multi-agent systems needs modern data architecture -- Deloitte](https://www.deloitte.com/cz-sk/en/services/consulting/blogs/where-is-the-value-of-AI-in-MA-why-multi-agent-systems-needs-modern-data-architecture.html)
- [MCP-Powered Financial AI Workflows on Databricks](https://www.databricks.com/blog/mcp-powered-financial-ai-workflows-databricks)

---

## 5. Webhook and Real-Time Notification Patterns

**Confidence: HIGH** -- Well-established web patterns with clear applicability.

### 5.1 Recommended Pattern: Server-Sent Events (SSE) for Progress + Webhooks for Completion

For a multi-step AI pipeline, use a **dual notification strategy**:

| Mechanism | Use Case | Direction |
|-----------|----------|-----------|
| **SSE** | Real-time progress updates during pipeline execution | Server -> Browser |
| **Polling** | Fallback for clients that don't support SSE | Browser -> Server |
| **Webhooks** | Notify external systems on completion | Server -> External |
| **WebSocket** | If bidirectional communication needed (e.g., HITL) | Bidirectional |

### 5.2 SSE for Pipeline Progress

SSE is ideal because the connection stays open, and the server pushes updates without the client needing to poll:

```python
from fastapi import Request
from sse_starlette.sse import EventSourceResponse

@app.get("/api/jobs/{job_id}/stream")
async def stream_job_progress(job_id: str, request: Request):
    async def event_generator():
        while True:
            if await request.is_disconnected():
                break
            job = await get_job(job_id)
            yield {
                "event": "progress",
                "data": json.dumps({
                    "step": job.current_step,
                    "progress": job.progress,
                    "message": job.status_message
                })
            }
            if job.status in ("complete", "failed"):
                yield {"event": "done", "data": json.dumps(job.result)}
                break
            await asyncio.sleep(1)
    return EventSourceResponse(event_generator())
```

### 5.3 Progress Events for Each Pipeline Stage

```
Event: progress | Step: ingestion      | Progress: 10% | "Parsing CSV file..."
Event: progress | Step: categorization  | Progress: 30% | "Categorizing 245 transactions..."
Event: progress | Step: patterns        | Progress: 55% | "Detecting spending patterns..."
Event: progress | Step: triage          | Progress: 70% | "Analyzing financial health..."
Event: progress | Step: education       | Progress: 90% | "Generating personalized insights..."
Event: done     | Step: complete        | Progress: 100% | {full results payload}
```

### 5.4 Best Practices

- Include **correlation IDs** to track events across the pipeline
- Log all events for debugging and audit
- Implement exponential backoff for SSE reconnection on client side
- Use HTTP 202 (Accepted) on initial upload, with `Location` header pointing to status endpoint

### Sources

- [Using Webhooks together with Server-Sent Events](https://medium.com/darwinlabs/using-webhooks-with-server-sent-events-in-outsystems-cd0506af38c9)
- [Webhooks and Asynchronous APIs: Real-Time Communication Patterns](https://satyendrakjaiswal.medium.com/webhooks-and-asynchronous-apis-real-time-communication-patterns-b6dee06b855d)
- [Why Implement Asynchronous Processing of Webhooks](https://hookdeck.com/webhooks/guides/why-implement-asynchronous-processing-webhooks)
- [Webhooks Best Practices: Lessons from the Trenches](https://medium.com/@xsronhou/webhooks-best-practices-lessons-from-the-trenches-57ade2871b33)

---

## 6. Authentication and Data Security Patterns for Financial AI

**Confidence: HIGH** -- Critical area with clear regulatory requirements and established patterns.

### 6.1 Ukrainian Data Protection Framework

**Current law:** Law of Ukraine on Personal Data Protection No 2297-VI (2010), modeled on Council of Europe Convention 108. A **GDPR-harmonization draft law** was adopted as a basis by Parliament on November 20, 2024, and is currently being prepared for second reading -- though full adoption is delayed due to the war.

**Financial-sector-specific laws:**
- Law "On Banks and Banking" -- bank secrecy provisions
- Law "On Financial Services and Financial Companies" -- additional privacy norms for financial sector

**Recommendation:** Build to GDPR standards now, as Ukraine is actively harmonizing toward GDPR equivalence. This also future-proofs the application.

### 6.2 Encryption Requirements

| Layer | Requirement | Implementation |
|-------|------------|----------------|
| **In transit** | TLS 1.3 for all API communication | HTTPS everywhere, certificate pinning |
| **At rest** | AES-256 encryption for stored financial data | PostgreSQL pgcrypto, disk-level encryption |
| **Embeddings** | Vector data is derived, but may leak PII patterns | Encrypt pgvector tables, access controls |
| **LLM context** | Financial data sent to LLM | Use local/self-hosted models or ensure data processing agreements |

### 6.3 Authentication and Access Control

- **Authentication**: JWT tokens with short expiry, refresh token rotation
- **Authorization**: Role-based access control (RBAC) -- users can only access their own financial data
- **Zero Trust**: Validate every request, even from internal services
- **IAM**: Token management with real-time behavioral monitoring

### 6.4 AI-Specific Security Threats

Financial AI applications face unique attack vectors beyond traditional web security:
- **Prompt injection**: Malicious inputs that manipulate LLM behavior to leak financial data
- **Data leakage**: LLM responses inadvertently revealing training data or other users' data
- **Model poisoning**: Corrupted financial education content in the RAG knowledge base
- **Embedding inversion attacks**: Potential recovery of original text from vector embeddings

**Mitigations:**
- Input sanitization before LLM processing
- Output filtering to prevent PII leakage in education responses
- Knowledge base content validation and provenance tracking
- Tenant isolation in pgvector (user-scoped queries only)

### 6.5 GDPR-Aligned Compliance Checklist for Ukrainian Financial App

1. **Data minimization**: Only collect and process financial data necessary for analysis
2. **Purpose limitation**: Clearly define and communicate data processing purposes
3. **Right to erasure**: Implement data deletion endpoint (including embeddings)
4. **Explainability**: AI-generated financial insights must be explainable (not black-box)
5. **Consent management**: Explicit user consent for AI processing of financial data
6. **Data processing records**: Maintain audit logs of all processing activities
7. **Data Protection Impact Assessment**: Required for high-risk automated processing of financial data

### Sources

- [Data Protection Laws and Regulations Report 2025-2026 Ukraine](https://iclg.com/practice-areas/data-protection-laws-and-regulations/ukraine)
- [Ukraine's Privacy Law: Understanding GDPR Impact](https://svitla.com/blog/privacy-law-and-the-impact-of-gdpr-in-ukraine/)
- [Data protection and cybersecurity laws in Ukraine -- CMS](https://cms.law/en/int/expert-guides/cms-expert-guide-to-data-protection-and-cyber-security-laws/ukraine)
- [Data protection laws in Ukraine -- DLA Piper](https://www.dlapiperdataprotection.com/index.html?t=law&c=UA)
- [Elevating Trust: AI Security in Financial Services -- BigID](https://bigid.com/blog/elevating-trust-ai-security-in-financial-services/)
- [AI Application Security: Safeguarding Data, Code, and Behavior](https://www.obsidiansecurity.com/blog/ai-application-security)
- [AI Privacy Rules: GDPR, EU AI Act, and U.S. Law](https://www.parloa.com/blog/AI-privacy-2026/)
- [The Future of Finance: Adapting to AI and Data Privacy Laws -- GDPR Local](https://gdprlocal.com/the-future-of-finance-adapting-to-ai-and-data-privacy-laws/)
- [Protecting sensitive financial information in the age of gen AI](https://www.bai.org/banking-strategies/protecting-sensitive-financial-information-in-the-age-of-kopiika-ai/)
- [Is Financial Data Personal Data Under GDPR?](https://agentiveaiq.com/blog/is-financial-data-personal-data-under-gdpr)

---

## Summary: Recommended Integration Architecture

```
                    +------------------+
                    |  Next.js Frontend |
                    |  (File Upload UI) |
                    +--------+---------+
                             |
                     CSV Upload (HTTPS/TLS 1.3)
                             |
                    +--------v---------+
                    |   FastAPI Backend  |
                    | - JWT Auth         |
                    | - File Validation  |
                    | - Job Queue        |
                    +--------+---------+
                             |
                    HTTP 202 + Job ID (immediate)
                    SSE stream (progress updates)
                             |
                    +--------v---------+
                    | LangGraph Pipeline |
                    | (Background Worker)|
                    +--------+---------+
                             |
              +--------------+---------------+
              |              |               |
     +--------v---+  +------v------+  +-----v--------+
     | Ingestion  |  |Categorization|  |Pattern Detect|
     | Agent      |->| Agent        |->| Agent        |
     +------------+  +--------------+  +------+-------+
                                              |
                                    +---------v--------+
                                    |   Triage Agent    |
                                    +---+----------+---+
                                        |          |
                              (needs_education) (high_risk)
                                        |          |
                              +---------v--+  +----v-------+
                              | Education   |  | Human-in-  |
                              | Agent (RAG) |  | the-Loop   |
                              +------+------+  +------------+
                                     |
                              +------v------+
                              |  pgvector   |
                              | (BGE-M3     |
                              |  embeddings)|
                              +-------------+
```

**Key Integration Decisions:**
1. **Sequential pipeline with conditional branching** at triage stage
2. **Async file processing** with SSE progress streaming
3. **Agentic RAG** (retrieve -> grade -> generate) for education agent
4. **pgvector + BGE-M3** for multilingual Ukrainian financial content retrieval
5. **HITL via LangGraph interrupt/Command** for high-risk pattern review
6. **GDPR-aligned security** with encryption at rest/transit, tenant isolation, audit logging
