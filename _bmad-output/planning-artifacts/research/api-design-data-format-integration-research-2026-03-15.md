# API Design & Data Format Integration Patterns Research

**Date:** 2026-03-15
**Context:** Personal finance AI product ingesting Monobank data, multi-agent AI pipeline (LangGraph), PostgreSQL + pgvector, Python backend, Next.js frontend, Teaching Feed card-based UI.

---

## 1. API Design for AI-Powered Web Apps

**Confidence: HIGH**

### REST vs GraphQL for Serving AI-Generated Insights

The 2025-2026 landscape shows a clear hybrid trend: **REST for public/external APIs and GraphQL for Backend-for-Frontend (BFF) patterns**.

- Over 61% of organizations now use GraphQL; enterprise adoption grew 340%+ since 2023.
- For this product, a **hybrid approach** is recommended:
  - **REST endpoints** for: Monobank webhook ingestion, payment callbacks, health checks, simple CRUD
  - **GraphQL** for: Teaching Feed queries (cards with variable fields), user dashboard (fetch only needed data), flexible insight queries where cards have heterogeneous shapes

**Key recommendation for Teaching Feed:**
GraphQL is well-suited for card-based UIs where each card type has different data requirements. A single `teachingFeed` query can return a union type of different card variants (spending insight, saving tip, anomaly alert, etc.) without over-fetching.

### Streaming Responses for LLM Outputs

**SSE (Server-Sent Events) is the clear winner for LLM streaming in 2025-2026.** This is the de facto standard used by OpenAI, Anthropic, and most LLM APIs.

**Python Backend (FastAPI) implementation pattern:**
```python
from fastapi.responses import StreamingResponse

async def generate_insight_stream(prompt, context):
    async for chunk in langgraph_agent.astream(prompt, context):
        yield f"data: {json.dumps({'delta': chunk})}\n\n"

@app.get("/api/insights/{insight_id}/stream")
async def stream_insight(insight_id: str):
    return StreamingResponse(
        generate_insight_stream(prompt, context),
        media_type="text/event-stream"
    )
```

**Frontend (Next.js) consumption:**
- Next.js 15 has excellent built-in SSE support with App Router streaming
- The Vercel AI SDK (`ai` package) provides `useChat` and `useCompletion` hooks that handle SSE parsing automatically
- The `fastapi-ai-sdk` Python library provides Vercel AI SDK-compatible streaming from FastAPI

**Why SSE over WebSockets for this product:**
- Unidirectional (server -> client) is sufficient for streaming AI-generated text
- Stateless: horizontal scaling with multiple API servers, no sticky sessions needed
- HTTP-native: works through proxies, CDNs, load balancers without extra configuration
- Simpler to implement and debug

**When to consider WebSockets:** If the product later adds real-time collaborative features or bidirectional chat, WebSocket can supplement SSE.

### Pagination for Teaching Feed Cards

**Cursor-based pagination** is recommended over offset-based for the Teaching Feed:
- Cards are generated asynchronously and may be inserted out of order
- Cursor-based avoids the "shifting window" problem when new insights are generated
- GraphQL has native cursor/connection patterns (Relay specification)

### Sources
- [REST vs GraphQL 2026 Trends - zuniweb](https://zuniweb.com/blog/api-architecture-showdown-rest-graphql-and-grpc-for-modern-web-and-mobile-apps/)
- [GraphQL vs REST 2025 Comparison - API7.ai](https://api7.ai/blog/graphql-vs-rest-api-comparison-2025)
- [REST vs GraphQL Enterprise 2026 - BizData360](https://www.bizdata360.com/rest-api-vs-graphql/)
- [AI-Powered APIs Performance - SmartDev](https://smartdev.com/ai-powered-apis-grpc-vs-rest-vs-graphql/)
- [API Development 2026 Python - Nucamp](https://www.nucamp.co/blog/api-development-in-2026-building-rest-and-graphql-apis-with-python)
- [FastAPI SSE Tutorial](https://fastapi.tiangolo.com/tutorial/server-sent-events/)
- [FastAPI AI SDK on PyPI](https://pypi.org/project/fastapi-ai-sdk/)

---

## 2. Monobank API Integration Patterns

**Confidence: HIGH**

### Authentication Flow

Monobank uses a **token-based authentication** model (not OAuth):

1. User logs into https://api.monobank.ua/ and generates a personal API token
2. Token is passed as `X-Token` HTTP header on every request
3. For production/commercial use, **Corporate API** is recommended (no rate limits, but requires partnership agreement with Monobank)

**Implementation note:** Store the user's Monobank token encrypted in the database. Consider a token refresh/re-auth flow in the UI since tokens can be revoked.

### Key API Endpoints

| Endpoint | Method | Rate Limit | Purpose |
|---|---|---|---|
| `/bank/currency` | GET | None specified | Exchange rates |
| `/personal/client-info` | GET | 1 req/60s | Account list, balances |
| `/personal/statement/{account}/{from}/{to}` | GET | 1 req/60s | Transaction history |
| `/personal/webhook` | POST | N/A | Set webhook URL |

### Webhook Subscription for Real-Time Updates

**Setup flow:**
1. Call POST `/personal/webhook` with `{"webHookUrl": "https://your-server.com/api/monobank/webhook"}`
2. Monobank verifies the URL (must respond HTTP 200)
3. Transactions arrive as POST requests:
   ```json
   {
     "type": "StatementItem",
     "data": {
       "account": "account_id",
       "statementItem": { /* transaction fields */ }
     }
   }
   ```

**Retry policy:** If webhook delivery fails:
- Retry after 60 seconds
- Retry after 600 seconds (10 min)
- If third attempt fails, webhook is **disabled** (must re-register)

**Implication:** Your webhook endpoint must be highly available and respond within 5 seconds. Use an async pattern: accept the webhook, enqueue for processing, return 200 immediately.

### Rate Limiting Strategy (1 req/60s)

**Recommended approach:**
```python
# Use python-monobank library with built-in rate limit handling
import monobank

try:
    statements = monobank.personal.statement(account, from_ts, to_ts)
except monobank.TooManyRequests:
    # Retry with backoff
    await asyncio.sleep(60)
```

**Batch data retrieval strategy for initial sync:**
- Maximum window: 31 days + 1 hour (2,682,000 seconds)
- With 1 req/60s limit, syncing 1 year of data = ~12 requests = ~12 minutes minimum
- Queue historical sync requests via Celery with 60s delays between them
- Use webhook for ongoing real-time updates after initial sync

### Python Libraries

- [`python-monobank`](https://github.com/vitalik/python-monobank) (PyPI: `monobank`) - most popular, includes rate limit exception handling
- [`monobankua`](https://pypi.org/project/monobankua/) - alternative with async support

### Sources
- [Monobank Official API Docs](https://api.monobank.ua/docs/index.html)
- [Monobank Open API Documentation - GitHub](https://github.com/siomochkin/monobank-open-api-documentation)
- [python-monobank - GitHub](https://github.com/vitalik/python-monobank)
- [monobank on PyPI](https://pypi.org/project/monobank/)
- [Monobank Corp API Interaction - GitHub Gist](https://gist.github.com/Sominemo/8714a82e26a268c30e4a332b0b2fd943)
- [Monobank API Postman Collection](https://documenter.getpostman.com/view/25272928/2sA3JGe3W4)

---

## 3. Financial Data Interchange Formats

**Confidence: MEDIUM-HIGH**

### Internal Transaction Data Model

For a personal finance AI product, the internal transaction model should normalize Monobank's format into a standardized schema inspired by Open Banking and ISO 20022 principles:

**Recommended core transaction fields:**

```python
class Transaction(Base):
    __tablename__ = "transactions"

    id: str                    # Internal UUID
    external_id: str           # Monobank transaction ID
    account_id: str            # Monobank account reference
    amount: int                # In smallest currency unit (kopiykas)
    currency_code: int         # ISO 4217 numeric code (980 = UAH)
    operation_amount: int      # Original amount if foreign currency
    operation_currency: int    # Original currency code
    mcc: int                   # Merchant Category Code (ISO 18245)
    description: str           # Transaction description from bank
    timestamp: datetime        # Unix timestamp of transaction
    hold: bool                 # Whether transaction is still held

    # Enriched fields (added by AI pipeline)
    category: str              # AI-classified category
    subcategory: str           # More granular classification
    merchant_name: str         # Normalized merchant name
    is_recurring: bool         # AI-detected recurring pattern
    embedding: Vector(1536)    # pgvector embedding for similarity search
    tags: list[str]            # User or AI-assigned tags
    notes: str                 # User notes
```

### Industry Standards Relevance

- **ISO 20022:** Defines semantic data models for financial messaging. Relevant fields: party identifiers, account details, transaction purpose, remittance info. Overly complex for a personal finance app, but useful as reference for field naming conventions.
- **FIBO (Financial Industry Business Ontology):** Open-source industry standard for financial concepts and relationships. Good reference for category taxonomies.
- **PSD2 / Open Banking (EU/UK):** Mandates standardized data formats. The Account Information Service (AIS) transaction format is a useful reference model.
- **MCC (Merchant Category Code):** Monobank provides MCC codes with each transaction -- this is the primary input for AI-based categorization. ISO 18245 defines the standard.

### Practical Recommendations

1. **Store raw Monobank data** in a `raw_transactions` table/JSONB column for auditability
2. **Normalize into the internal model** with enriched fields
3. **Use MCC codes as primary categorization input**, supplemented by description parsing
4. **Generate embeddings** for transaction descriptions to enable semantic search and similarity-based pattern detection via pgvector

### Sources
- [ISO 20022 Standards - SWIFT](https://www.swift.com/standards/iso-20022/iso-20022-standards)
- [ISO 20022 Data Field Dictionary](https://www.iso20022.org/data-field-dictionary)
- [Universal Data Model for Fintech - PortX](https://portx.io/open-banking-api-building-a-universal-data-model-for-fintech-integration-to-the-core/)
- [Banking Data Model - Bank Ontology](https://bankontology.com/banking-data-model/)
- [Open Banking Explained - Stripe](https://stripe.com/resources/more/open-banking-explained)

---

## 4. Event-Driven Architecture for AI Processing

**Confidence: HIGH**

### Recommended Stack: Celery + Redis

For a Python/LangGraph backend, **Celery with Redis as broker** is the recommended pattern:

- **Celery** handles task distribution, retries, and workflow orchestration
- **Redis** serves triple duty: message broker, result backend, and cache
- **LangGraph** agents run inside Celery workers

### Architecture Pattern

```
[Monobank Webhook] --> [FastAPI] --> [Redis Queue] --> [Celery Workers]
                                                            |
                                                    [LangGraph Agent]
                                                            |
                                                    [PostgreSQL + pgvector]
                                                            |
                                                    [SSE to Frontend]
```

### Task Design for AI Pipeline

```python
from celery import chain, group, chord

# Individual tasks
@app.task(bind=True, max_retries=3)
def categorize_transaction(self, transaction_id):
    """Run LangGraph categorization agent"""
    loop = asyncio.get_event_loop()
    result = loop.run_until_complete(
        categorization_graph.ainvoke({"transaction_id": transaction_id})
    )
    return result

@app.task
def generate_insight(self, transaction_ids):
    """Generate Teaching Feed insight from batch of transactions"""
    ...

@app.task
def generate_embedding(self, transaction_id):
    """Generate vector embedding for semantic search"""
    ...

# Workflow orchestration
def process_new_transactions(transaction_ids):
    workflow = chord(
        group(categorize_transaction.s(tid) for tid in transaction_ids),
        generate_insight.s()  # Runs after all categorizations complete
    )
    workflow.apply_async()
```

### Job Status Tracking

Use Redis for real-time job status with SSE delivery to frontend:

```python
# Track progress in Redis
redis_client.hset(f"job:{job_id}", mapping={
    "status": "processing",
    "progress": 45,
    "total_steps": 100,
    "current_step": "Categorizing transactions"
})

# SSE endpoint streams status updates
@app.get("/api/jobs/{job_id}/status")
async def job_status_stream(job_id: str):
    async def event_generator():
        while True:
            status = redis_client.hgetall(f"job:{job_id}")
            yield f"data: {json.dumps(status)}\n\n"
            if status.get("status") in ("completed", "failed"):
                break
            await asyncio.sleep(1)
    return StreamingResponse(event_generator(), media_type="text/event-stream")
```

### Key Considerations

- **Thread safety:** Running LangGraph inside Celery at scale (10-20 parallel nodes) can hit "can't start a new thread" errors. Mitigate with `worker_concurrency` settings and prefork pool.
- **Temporal as alternative:** For very complex multi-step workflows with durable execution guarantees, Temporal is worth considering over Celery, but adds infrastructure complexity.
- **Retry logic:** Use exponential backoff for LLM API calls (rate limits, transient failures).

### Sources
- [Event-Driven Architecture with Celery & Redis - Medium](https://medium.com/flux-it-thoughts/switching-from-monolithic-to-event-driven-architecture-with-celery-redis-6b4d84ecaf4d)
- [Modern Queueing: Celery vs RabbitMQ vs Redis vs Temporal - Medium](https://medium.com/@pranavprakash4777/modern-queueing-architectures-celery-rabbitmq-redis-or-temporal-f93ea7c526ec)
- [Event-Driven AI Architectures - Gcore](https://gcore.com/blog/event-driven-ai-architectures)
- [Orchestrating AI: Event-Driven Architectures - The New Stack](https://thenewstack.io/orchestrating-ai-event-driven-architectures-for-complex-ai-workflows/)
- [Redis + Celery for Long-Running AI Jobs - Markaicode](https://markaicode.com/redis-celery-long-running-ai-jobs/)
- [Saga Pattern with Python Celery 2025](https://johal.in/event-driven-architecture-implementing-saga-pattern-with-python-celery-2025/)
- [Distributed LangGraph Workflow Engine - Medium](https://medium.com/@mukshobhit/scaling-ai-powered-agents-building-a-distributed-langgraph-workflow-engine-13e57e368953)
- [LLM-Driven API Orchestration with LangChain, Celery & Redis - Jellyfish](https://www.jellyfishtechnologies.com/llm-driven-api-orchestration-using-langchain-celery-redis-queue/)

---

## 5. Frontend-Backend Integration for AI Products

**Confidence: HIGH**

### SSE for Streaming AI Results

**SSE is the recommended protocol** for streaming LLM-generated Teaching Feed content to the Next.js frontend.

**Backend (FastAPI):**
- Use `StreamingResponse` with `text/event-stream` media type
- Or use `sse-starlette` library for `EventSourceResponse` with automatic keepalive
- The `fastapi-ai-sdk` package provides Vercel AI SDK-compatible streaming

**Frontend (Next.js):**
- Vercel AI SDK provides `useChat()` and `useCompletion()` hooks for automatic SSE consumption
- For custom SSE streams, use `EventSource` API or `fetch` with `ReadableStream`
- Next.js App Router has native streaming support via React Suspense boundaries

### Optimistic UI Patterns for Teaching Feed

1. **Skeleton cards:** Show placeholder cards immediately while AI generates insights
2. **Progressive enhancement:** Display basic transaction data first, then stream in AI-generated analysis
3. **Optimistic status updates:** When user rates/saves a card, update UI immediately, sync to backend asynchronously

### Caching AI-Generated Insights

**Multi-layer caching strategy:**

| Layer | Technology | TTL | Purpose |
|---|---|---|---|
| Browser | React Query / SWR | 5-15 min | Avoid re-fetching on navigation |
| CDN/Edge | Vercel Edge / Cloudflare | 1-60 min | Cache stable insights |
| API | Redis | 1-24 hours | Cache completed AI analysis |
| DB | PostgreSQL | Permanent | Store all generated insights |

**Key principle:** AI-generated insights are **write-once, read-many**. Once generated, they rarely change. Cache aggressively.

- Use `stale-while-revalidate` pattern: serve cached insights immediately, regenerate in background if stale
- Invalidate cache only when new transactions arrive that affect the insight

### Sources
- [SSE Still Wins in 2026 - Procedure.tech](https://procedure.tech/blogs/the-streaming-backbone-of-llms-why-server-sent-events-(sse)-still-wins-in-2025)
- [Streaming LLM Responses Complete Guide - DEV Community](https://dev.to/pockit_tools/the-complete-guide-to-streaming-llm-responses-in-web-applications-from-sse-to-real-time-ui-3534)
- [SSE for LLM Streaming at Scale - Medium](https://medium.com/@daniakabani/how-we-used-sse-to-stream-llm-responses-at-scale-fa0d30a6773f)
- [Streaming AI Responses: WebSockets vs SSE vs gRPC - Medium](https://medium.com/@pranavprakash4777/streaming-ai-responses-with-websockets-sse-and-grpc-which-one-wins-a481cab403d3)
- [SSE with LLM in Next.js - Upstash](https://upstash.com/blog/sse-streaming-llm-responses)
- [Real-Time AI in Next.js with Vercel AI SDK - LogRocket](https://blog.logrocket.com/nextjs-vercel-ai-sdk-streaming/)
- [Consuming Streamed LLM Responses on Frontend - Tamas Piros](https://tpiros.dev/blog/streaming-llm-responses-a-deep-dive/)

---

## 6. Freemium/Subscription Integration for Ukrainian Market

**Confidence: MEDIUM**

### Critical Context: Stripe Is NOT Available in Ukraine

Stripe does **not** officially support Ukraine. The National Bank of Ukraine confirmed (November 2025) that Stripe has never requested a license to operate in Ukraine.

**Workarounds for Stripe:**
- Register a company abroad (USA via Stripe Atlas, Estonia, UK) and use that entity's Stripe account
- This adds legal/tax complexity but is common among Ukrainian SaaS founders

### Recommended Payment Architecture

**Two-track approach:**

#### Track 1: Ukrainian Users (Domestic)
Use a **local payment gateway**:

| Provider | Subscription Support | Key Features |
|---|---|---|
| **Fondy** | Yes (recurring billing) | API integration, Apple/Google Pay, multi-currency, 200+ countries, anti-fraud |
| **WayForPay** | Yes (recurring payments) | Popular in Ukraine since 2014, one-click payments, installments |
| **LiqPay (PrivatBank)** | Yes | Deep integration with PrivatBank, widely trusted |
| **Monobank Acquiring** | Basic | The `monopay-ruby` repo suggests acquiring capabilities exist |

**Fondy is the strongest candidate** for SaaS subscription billing in Ukraine: mature API, built-in recurring billing, and webhook support for subscription lifecycle events.

#### Track 2: International Users
**LemonSqueezy** is the recommended option:
- Acts as **Merchant of Record** (handles global tax compliance, VAT, sales tax)
- No need for a foreign company registration
- Supports 100+ countries, 150+ currencies
- Built-in subscription management, dunning, tax compliance
- 5% + $0.50 per transaction (higher than Stripe's 2.9% + $0.30, but includes MoR services)
- In 2026, LemonSqueezy integrated with Stripe for managed payments under the hood

**Key advantage of LemonSqueezy for a Ukrainian founder:** You don't need a US/EU company to accept global payments. LemonSqueezy is the merchant of record, so they handle international tax obligations.

### Freemium Tier Implementation

```
Free Tier:
- Basic transaction categorization
- Monthly spending summary
- Limited Teaching Feed (3 insights/week)

Premium Tier (subscription):
- Full AI analysis pipeline
- Unlimited Teaching Feed
- Custom categories and rules
- Export and analytics
- Priority processing
```

**Implementation pattern:**
1. Store subscription status in PostgreSQL
2. Check tier on API endpoints (middleware/decorator pattern)
3. Webhook from Fondy/LemonSqueezy updates subscription status
4. Grace period handling for failed payments

### Sources
- [Stripe Global Availability](https://stripe.com/global)
- [Stripe Not in Ukraine - OneSafe](https://www.onesafe.io/blog/does-stripe-work-in-ukraine)
- [NBU on Stripe/PayPal - dev.ua](https://dev.ua/en/news/nbu-zaiavyv-shcho-stripe-i-paypal-zhodnoho-razu-ne-prosyly-litsenziiu-dlia-roboty-v-ukraini-1764321864)
- [How to Open Stripe in Ukraine - LinkedIn](https://www.linkedin.com/pulse/how-open-stripe-account-ukraine-2024-mazino-oyolo-fobtf)
- [LemonSqueezy + Stripe 2026 Update](https://www.lemonsqueezy.com/blog/2026-update)
- [SaaS Payment Providers Comparison - Supastarter](https://supastarter.dev/blog/saas-payment-providers-stripe-lemonsqueezy-polar-creem-comparison)
- [Stripe vs LemonSqueezy 2025 - GetNextKit](https://getnextkit.com/blog/stripe-vs-lemonsqueezy-for-saas-which-payment-provider-should-you-choose-in-2025)
- [Ukrainian Payment Services Comparison - KITAPP](https://kitapp.pro/en/ukrainian-payment-services-comparison/)
- [Fondy Payment Platform](https://fondy.io/gb/)
- [WayForPay Payment Solutions](https://wayforpay.com/en)

---

## 7. Supplementary: pgvector for Financial AI Data

**Confidence: HIGH**

### Why pgvector Fits This Architecture

Using PostgreSQL + pgvector provides a **unified data store** for:
- Transactional data (accounts, transactions, categories)
- Vector embeddings (transaction description embeddings, insight embeddings)
- Relational queries and vector similarity searches in the same query

### Key Benefits for Financial AI
- **Single database** eliminates infrastructure sprawl and simplifies ACID compliance
- **Fraud/anomaly detection** via vector similarity on transaction embeddings
- **Semantic search** across transaction history ("find transactions similar to this one")
- **pgvector 0.8.0** delivers up to 9x faster query processing vs earlier versions

### Storage Considerations
- 1536-dimension OpenAI embeddings: ~6KB per vector
- For 100K transactions: ~600MB of vector data (manageable)
- Use HNSW index for approximate nearest neighbor search (faster than IVFFlat for most workloads)

### Sources
- [PostgreSQL as Vector Database - Airbyte](https://airbyte.com/data-engineering-resources/postgresql-as-a-vector-database)
- [pgvector GitHub](https://github.com/pgvector/pgvector)
- [pgvector + Supabase Docs](https://supabase.com/docs/guides/database/extensions/pgvector)
- [Postgres with pgvector AI Use Cases - EDB](https://www.enterprisedb.com/postgres-with-pgvector-ai-use-cases)

---

## Summary: Recommended Integration Architecture

```
                          +------------------+
                          |   Next.js App    |
                          |  (Teaching Feed) |
                          +--------+---------+
                                   |
                          SSE (streaming) + GraphQL (queries)
                                   |
                          +--------+---------+
                          |    FastAPI       |
                          | (REST + GraphQL) |
                          +---+----+----+---+
                              |    |    |
                    +---------+    |    +---------+
                    |              |              |
              +-----+-----+ +----+----+  +------+------+
              |   Redis    | |PostgreSQL|  | Celery      |
              | (broker +  | |+ pgvector|  | Workers     |
              |  cache)    | |          |  | (LangGraph) |
              +------------+ +----------+  +-------------+
                                                |
                                          +-----+-----+
                                          | LLM APIs  |
                                          | (OpenAI/  |
                                          | Anthropic)|
                                          +-----------+

External Integrations:
  - Monobank API (webhook + polling with 60s rate limit)
  - Fondy (Ukrainian payments, recurring billing)
  - LemonSqueezy (international payments, MoR)
```

### Key Design Decisions Summary

| Decision | Recommendation | Confidence |
|---|---|---|
| API style | Hybrid REST + GraphQL | HIGH |
| LLM streaming | SSE via FastAPI StreamingResponse | HIGH |
| Feed pagination | Cursor-based (GraphQL connections) | HIGH |
| Monobank sync | Webhook (real-time) + batch polling (historical) | HIGH |
| Task queue | Celery + Redis | HIGH |
| Vector store | pgvector (same PostgreSQL instance) | HIGH |
| UA payments | Fondy (recurring billing) | MEDIUM-HIGH |
| Intl payments | LemonSqueezy (Merchant of Record) | MEDIUM |
| Frontend framework | Next.js + Vercel AI SDK | HIGH |
