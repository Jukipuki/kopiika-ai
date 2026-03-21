# Vector Store Options for Financial Literacy RAG Knowledge Base

**Research Date:** 2026-03-15
**Scope:** Vector database comparison for RAG applications, pricing, performance, multilingual support, framework integrations, and embedding models for Ukrainian text

---

## 1. Executive Summary

For a startup building a financial literacy RAG system targeting Ukrainian-speaking users with a corpus of ~10K-100K documents, **pgvector** emerges as the strongest initial choice, with **Qdrant** as the recommended upgrade path. The combination of pgvector (for vector storage) with **BGE-M3** or **Cohere embed-multilingual-v3.0** (for Ukrainian-capable embeddings) provides the best balance of cost, simplicity, multilingual support, and production readiness.

---

## 2. Vector Database Comparison Table

| Feature | pgvector | Chroma | Qdrant | Weaviate | Pinecone | Milvus |
|---|---|---|---|---|---|---|
| **Type** | PG Extension | Embedded/Cloud | Standalone DB | Standalone DB | Managed SaaS | Standalone DB |
| **Language** | C (PG ext) | Rust (rewrite 2025) | Rust | Go | Proprietary | Go/C++ |
| **License** | PostgreSQL License | Apache 2.0 | Apache 2.0 | BSD-3 | Proprietary | Apache 2.0 |
| **Self-hosted** | Yes (any PG) | Yes | Yes | Yes | No | Yes |
| **Managed cloud** | Via Supabase/Neon/AWS RDS | Chroma Cloud | Qdrant Cloud | Weaviate Cloud | Yes (only option) | Zilliz Cloud |
| **Free tier** | Free (self-hosted) | $5 free credits (cloud); free self-hosted | 1GB RAM + 4GB disk free cluster | 14-day sandbox only | 2GB storage, 2M writes, 1M reads/mo | Free (self-hosted) |
| **HNSW index** | Yes | Yes | Yes | Yes | Yes | Yes |
| **Hybrid search** | Manual (with tsvector) | No | Yes (sparse+dense) | Yes (best-in-class) | Yes | Yes |
| **Metadata filtering** | SQL WHERE clauses | Basic | Advanced (Rust-optimized) | GraphQL-based | Moderate | Moderate |
| **Multi-tenancy** | Via PG schemas/RLS | Limited | Yes | Yes | Yes | Yes |
| **Max recommended scale** | <1M vectors | <10M vectors | Billions | Billions | Billions | Billions |
| **Query latency (100K vectors)** | ~1-2ms (HNSW, in-memory) | ~5-15ms | <5ms | <10ms | <50ms | <5ms |
| **LangChain integration** | Yes (partner pkg) | Yes (native) | Yes (partner pkg) | Yes (partner pkg) | Yes (partner pkg) | Yes |
| **LlamaIndex integration** | Yes | Yes | Yes | Yes | Yes | Yes |
| **Best for** | PG-native teams, startups | Prototyping, MVPs | Production + filters | Hybrid search, knowledge graphs | Zero-ops scale | Massive scale |

**Confidence: HIGH** -- based on multiple corroborating 2025-2026 comparison guides.

Sources:
- [LiquidMetal AI - Vector Database Comparison 2025](https://liquidmetal.ai/casesAndBlogs/vector-comparison/)
- [Firecrawl - Best Vector Databases 2026](https://www.firecrawl.dev/blog/best-vector-databases)
- [Digital One Agency - Best Vector Database for RAG 2025](https://digitaloneagency.com.au/best-vector-database-for-rag-in-2025-pinecone-vs-weaviate-vs-qdrant-vs-milvus-vs-chroma/)
- [Latenode - Best Vector Databases for RAG 2025](https://latenode.com/blog/ai-frameworks-technical-infrastructure/vector-databases-embeddings/best-vector-databases-for-rag-complete-2025-comparison-guide)
- [Rost Glukhov - Vector Stores for RAG Comparison](https://www.glukhov.org/post/2025/12/vector-stores-for-rag-comparison/)

---

## 3. Pricing Analysis

### 3.1 Free / Near-Free Options

| Database | Free Tier Details | Limitations |
|---|---|---|
| **pgvector** | Completely free as PG extension. Cloud PG providers (Supabase, Neon) have free tiers. | Must manage PG infrastructure or use cloud PG provider. Supabase free = 500MB DB. |
| **Chroma** | Free self-hosted; $5 free cloud credits | Cloud credits deplete quickly. Self-hosted requires own infra. |
| **Qdrant** | Free 1GB RAM + 4GB disk cloud cluster (no credit card) | Limited to small datasets (~50K-100K vectors at 1024d). No HA. |
| **Weaviate** | 14-day sandbox only. Open-source for self-hosting. | No permanent free cloud tier. Self-hosted = own infra. |
| **Pinecone** | 2GB storage, 2M write units, 1M read units/mo | AWS us-east-1 only. 1 project, 2 users. Paused after 3 weeks inactivity. |
| **Milvus** | Free self-hosted | Complex to operate. Requires etcd + MinIO. |

### 3.2 Paid Pricing for Small-to-Medium Scale (~100K documents)

| Database | Estimated Monthly Cost (100K docs) | Pricing Model |
|---|---|---|
| **pgvector** (self on Supabase Pro) | $25/mo | Fixed DB plan |
| **pgvector** (AWS RDS t3.medium) | ~$30-50/mo | Instance-based |
| **Chroma Cloud** | ~$10-25/mo (usage-based) | Usage-based after free credits |
| **Qdrant Cloud** | $0-27/mo (with quantization) | Resource-based (CPU, RAM, disk) |
| **Weaviate Serverless** | $25-45/mo minimum | Dimension + query based |
| **Pinecone Standard** | $50/mo minimum commitment | Usage-based (storage + read/write units) |
| **Milvus** (Zilliz Cloud) | ~$65+/mo | Resource-based |

**Confidence: HIGH** for pricing structures, MEDIUM for exact cost estimates (depend on actual usage patterns).

Sources:
- [Pinecone Pricing](https://www.pinecone.io/pricing/)
- [Qdrant Pricing](https://qdrant.tech/pricing/)
- [Weaviate Pricing](https://weaviate.io/pricing)
- [Chroma Pricing](https://www.trychroma.com/pricing)
- [Weaviate Cloud Pricing Update Blog](https://weaviate.io/blog/weaviate-cloud-pricing-update)
- [MetaCTO - True Cost of Pinecone](https://www.metacto.com/blogs/the-true-cost-of-pinecone-a-deep-dive-into-pricing-integration-and-maintenance)
- [Xenoss - Pinecone vs Qdrant vs Weaviate](https://xenoss.io/blog/vector-database-comparison-pinecone-qdrant-weaviate)

---

## 4. Performance Benchmarks at Small-to-Medium Scale (10K-100K documents)

### 4.1 pgvector Performance

- **Query latency with HNSW index**: ~1-2ms for top-K nearest neighbor queries on 100K vectors (1536d) when index is in memory
- **HNSW vs sequential scan**: HNSW is approximately 5,250x faster than sequential scan
- **HNSW vs IVFFlat**: HNSW is ~1.5x faster than well-tuned IVFFlat for similar recall
- **Small tables (10K-50K vectors)**: Sequential scans may provide better recall with minimal performance impact; HNSW becomes more beneficial above 50K vectors
- **Dimensionality impact**: Lower-dimensional embeddings (384d vs 1536d) can boost pgvector throughput by 200%+ without significant accuracy loss
- **Index build time**: ~30 seconds for 58K records (pgvector 0.6.0+)
- **Sub-10ms queries achievable** with proper HNSW configuration and hybrid search

### 4.2 Comparison at 100K-Vector Scale

At this scale, all databases perform well. The differences become significant only at 1M+ vectors:

| Database | Approx. Query Latency (100K, top-10) | Recall @ default settings |
|---|---|---|
| pgvector (HNSW) | 1-2ms | 95-99% |
| Qdrant | <5ms | 99%+ |
| Chroma | 5-15ms | 95%+ |
| Weaviate | <10ms | 95-99% |
| Pinecone | <50ms (network overhead) | 99%+ |

**Key Insight**: For 10K-100K documents, pgvector performs comparably to purpose-built vector databases. Performance differentiation becomes relevant at 10M+ vectors.

**Confidence: HIGH** for pgvector benchmarks (well-documented by AWS, Google Cloud, Crunchy Data). MEDIUM for cross-database comparison at small scale (fewer direct benchmarks at this size).

Sources:
- [Mastra Blog - Benchmarking pgvector RAG performance](https://mastra.ai/blog/pgvector-perf)
- [Markaicode - Production RAG System with pgvector <10ms Queries](https://markaicode.com/pgvector-rag-production/)
- [AWS - Supercharging vector search with pgvector 0.8.0](https://aws.amazon.com/blogs/database/supercharging-vector-search-performance-and-relevance-with-pgvector-0-8-0-on-amazon-aurora-postgresql/)
- [Crunchy Data - HNSW Indexes with pgvector](https://www.crunchydata.com/blog/hnsw-indexes-with-postgres-and-pgvector)
- [Google Cloud - Faster similarity search with pgvector](https://cloud.google.com/blog/products/databases/faster-similarity-search-performance-with-pgvector-indexes)
- [Instaclustr - pgvector Performance Benchmarks](https://www.instaclustr.com/education/vector-database/pgvector-performance-benchmark-results-and-5-ways-to-boost-performance/)

---

## 5. Ukrainian / Multilingual Text Support

### 5.1 Vector Store Multilingual Handling

Vector stores themselves are language-agnostic -- they store and retrieve numerical vectors regardless of the source language. The multilingual capability depends entirely on the **embedding model** used to create the vectors. All six databases (pgvector, Chroma, Qdrant, Weaviate, Pinecone, Milvus) handle multilingual embeddings equally well because they operate on the numerical vectors, not the text.

**Confidence: HIGH** -- this is a fundamental architectural fact of vector search.

### 5.2 Embedding Models with Ukrainian Support

| Model | Ukrainian Support | Dimensions | Context Length | Cost | Open Source | Notes |
|---|---|---|---|---|---|---|
| **BGE-M3** (BAAI) | Yes (100+ languages) | 1024 | 8192 tokens | Free (self-hosted) | Yes (Apache 2.0) | Best open-source multilingual. Dense + sparse + multi-vector retrieval. Based on XLM-RoBERTa. |
| **Cohere embed-multilingual-v3.0** | Yes (100+ languages) | 1024 | 512 tokens | API-based (~$0.10/1M tokens) | No | Strong multilingual perf. Cohere's Aya model explicitly optimized for Ukrainian. |
| **OpenAI text-embedding-3-small** | Yes (multilingual) | 1536 (configurable) | 8191 tokens | $0.02/1M tokens | No | 13-point gain on multilingual tasks vs predecessors. MIRACL: 44.0%. |
| **OpenAI text-embedding-3-large** | Yes (multilingual) | 3072 (configurable) | 8191 tokens | $0.13/1M tokens | No | Higher quality, higher cost. |
| **ukr-paraphrase-multilingual-mpnet-base** | Ukrainian-specific fine-tuning | 768 | 512 tokens | Free (self-hosted) | Yes | Fine-tuned on Ukrainian data. Smaller model, potentially best for Ukrainian-specific tasks. |
| **Qwen3-Embedding** | Yes (explicitly lists Ukrainian) | 1024 | 32768 tokens | Free (self-hosted) | Yes (Apache 2.0) | Very long context. New model family. |
| **E5-large / E5-multilingual** | Yes (100+ languages) | 1024 | 512 tokens | Free (self-hosted) | Yes (MIT) | Strong multilingual baseline. |

### 5.3 Recommended Embedding Strategy for Ukrainian Financial Literacy

1. **Primary recommendation: BGE-M3** -- Free, open-source, 100+ languages including Ukrainian, 1024 dimensions (good balance of quality and pgvector performance), supports 8192 tokens (handles long financial documents), and supports dense + sparse retrieval for hybrid search.

2. **Alternative: Cohere embed-multilingual-v3.0** -- If you prefer a managed API and Cohere explicitly prioritizes Ukrainian in their Aya model family.

3. **Ukrainian-specific fine-tuning**: Consider fine-tuning BGE-M3 or using `ukr-paraphrase-multilingual-mpnet-base` as a starting point if general multilingual models underperform on Ukrainian financial terminology.

**Confidence: HIGH** for model availability and specs. MEDIUM for Ukrainian-specific quality rankings (limited head-to-head benchmarks on Ukrainian financial text specifically).

Sources:
- [HuggingFace - BGE-M3](https://huggingface.co/BAAI/bge-m3)
- [HuggingFace - ukr-paraphrase-multilingual-mpnet-base](https://huggingface.co/lang-uk/ukr-paraphrase-multilingual-mpnet-base)
- [Cohere Embed Models Documentation](https://docs.cohere.com/docs/cohere-embed)
- [Zilliz - Guide to embed-multilingual-v3.0](https://zilliz.com/ai-models/embed-multilingual-v3.0)
- [OpenAI Embedding Models](https://platform.openai.com/docs/models/text-embedding-3-small)
- [BentoML - Best Open-Source Embedding Models 2026](https://www.bentoml.com/blog/a-guide-to-open-source-embedding-models)
- [Elephas - 13 Best Embedding Models 2026](https://elephas.app/blog/best-embedding-models)

---

## 6. LLM Framework Integration

All major vector stores have first-class integrations with LangChain and LlamaIndex. Here is the current status:

| Database | LangChain | LlamaIndex | Haystack | Semantic Kernel | Custom SDK |
|---|---|---|---|---|---|
| pgvector | Partner package (`langchain-postgres`) | Yes (`llama-index-vector-stores-postgres`) | Yes | Yes | psycopg2/asyncpg + SQL |
| Chroma | Native integration | Yes | Yes | Yes | chromadb Python client |
| Qdrant | Partner package (`langchain-qdrant`) | Yes | Yes | Yes | qdrant-client (Python, Rust, Go, JS) |
| Weaviate | Partner package | Yes | Yes | Yes | weaviate-client |
| Pinecone | Partner package | Yes | Yes | Yes | pinecone-client |
| Milvus | Partner package | Yes | Yes | Limited | pymilvus |

### Key Integration Notes:

- **LangChain** uses a retriever abstraction that plugs into any of these vector stores. Switching between them requires minimal code changes.
- **LlamaIndex** provides VectorStoreIndex that works with all listed stores. Migration between stores is relatively straightforward.
- **pgvector** benefits from using standard SQL, meaning any ORM (SQLAlchemy, Django ORM, Prisma) can work alongside the vector functionality.

**Confidence: HIGH** -- verified from official documentation of LangChain, LlamaIndex, and each vector store.

Sources:
- [Qdrant - LangChain Integration](https://qdrant.tech/documentation/frameworks/langchain/)
- [LangChain - Qdrant Integration Docs](https://docs.langchain.com/oss/python/integrations/vectorstores/qdrant)
- [LlamaIndex - Vector Stores Documentation](https://developers.llamaindex.ai/python/framework/community/integrations/vector_stores/)
- [GeeksforGeeks - Vector Stores in LangChain](https://www.geeksforgeeks.org/artificial-intelligence/vector-stores-in-langchain/)

---

## 7. pgvector as a Practical Choice for Startups

### 7.1 Why pgvector Makes Sense for a Financial Literacy Startup

**Advantages:**

1. **No new infrastructure**: If you already use PostgreSQL (very likely for a startup), adding pgvector is just `CREATE EXTENSION vector;`. No new database to deploy, monitor, back up, or secure.

2. **Unified data model**: Store user profiles, financial content metadata, access logs, AND vector embeddings in one database. Join vector similarity results with relational data in a single SQL query (e.g., "find similar financial articles that this user hasn't read yet").

3. **Cost**: Incremental cost over existing PostgreSQL -- potentially $0 additional if your current PG instance has headroom. Compared to Pinecone's $50/mo minimum or Weaviate's $45/mo minimum.

4. **ACID transactions**: Financial data requires consistency guarantees. pgvector inherits PostgreSQL's full ACID compliance.

5. **Security and compliance**: PostgreSQL has mature row-level security, encryption, and audit logging -- critical for financial data.

6. **Ecosystem**: Works with every PG tool -- pgAdmin, pg_dump, logical replication, Supabase, Neon, AWS RDS, etc.

7. **Performance is sufficient**: At 10K-100K documents with HNSW indexes, expect 1-2ms query latency -- more than adequate for a RAG application.

**Disadvantages / Risks:**

1. **Resource contention**: Vector indexes consume significant memory. A heavy vector workload could affect your transactional database performance. Mitigation: use a read replica or separate PG instance for vector search.

2. **No GPU acceleration**: Purpose-built databases like Milvus support GPU-accelerated indexing. Not relevant at <1M vectors.

3. **Scaling ceiling**: If you grow beyond ~1M vectors or need sub-millisecond latency at scale, you may need to migrate. Mitigation: at 10K-100K documents, this is not an immediate concern.

4. **Slower index builds**: HNSW index creation is slower than in purpose-built engines. At 100K vectors, this means ~30-60 seconds (acceptable for batch updates).

5. **No native hybrid search**: You need to manually combine tsvector (full-text search) with vector similarity for hybrid search. Qdrant and Weaviate handle this natively.

### 7.2 pgvector Migration Path

If you outgrow pgvector, the migration path is straightforward:
- **pgvector -> Qdrant**: Both use HNSW, Qdrant has excellent filtering, and is the natural next step for production scale.
- **pgvector -> Pinecone**: If you want fully managed and are willing to pay premium pricing.
- **Architecture**: Use LangChain/LlamaIndex abstractions from day one to make the vector store swappable.

**Confidence: HIGH** -- well-supported by multiple sources and practical engineering analysis.

Sources:
- [Encore Blog - You Probably Don't Need a Vector Database](https://encore.dev/blog/you-probably-dont-need-a-vector-database)
- [CodeAwake - PostgreSQL with pgvector as a Vector Database for RAG](https://codeawake.com/blog/postgresql-vector-database)
- [DEV Community - Vector Databases vs PostgreSQL with pgvector for RAG](https://dev.to/simplr_sh/vector-databases-vs-postgresql-with-pgvector-for-rag-setups-1lg2)
- [DBA Dataverse - PostgreSQL vs Vector Database: Why PostgreSQL Wins 2025](https://dbadataverse.com/poetry/2025/12/postgresql-beat-vector-databases-dba-perspective)
- [EnterpriseDB - RAG App with Postgres and pgvector](https://www.enterprisedb.com/blog/rag-app-postgres-and-pgvector)
- [Scieneers - From Zero to Hero: Implementing RAG using PostgreSQL](https://www.scieneers.de/en/from-zero-to-hero-implementing-rag-using-postgresql/)
- [Instaclustr - pgvector Key Features and Pros/Cons 2026 Guide](https://www.instaclustr.com/education/vector-database/pgvector-key-features-tutorial-and-pros-and-cons-2026-guide/)

---

## 8. Financial Domain Considerations

### 8.1 Structured + Unstructured Data

Financial literacy content has both structured data (budgeting categories, tax brackets, interest rates) and unstructured data (articles, explanations, Q&A). pgvector uniquely allows joining these in a single query:

```sql
SELECT a.title, a.content, a.category,
       1 - (a.embedding <=> query_embedding) AS similarity
FROM articles a
JOIN categories c ON a.category_id = c.id
WHERE c.topic = 'budgeting'
  AND a.language = 'uk'
ORDER BY a.embedding <=> query_embedding
LIMIT 10;
```

### 8.2 Knowledge Graph Consideration

For financial literacy, a hybrid approach combining vector search with knowledge graphs may yield better results for questions involving relationships (e.g., "How does compound interest affect a mortgage?"). Neo4j + vector search or Weaviate's knowledge graph capabilities could be valuable as the system matures.

**Confidence: MEDIUM** -- knowledge graph benefits are domain-specific and may be over-engineering for an initial MVP.

Sources:
- [Neo4j - Knowledge Graph vs Vector RAG Financial Analysis](https://neo4j.com/blog/developer/knowledge-graph-vs-vector-rag/)
- [FinSage - Multi-aspect RAG for Financial Filings](https://arxiv.org/html/2504.14493v1)

---

## 9. Recommendations for a Financial Literacy RAG Startup

### Phase 1: MVP / Prototype (0-6 months)

| Component | Recommendation | Rationale |
|---|---|---|
| **Vector Store** | **pgvector** on existing PostgreSQL | Zero additional infrastructure cost; 1-2ms query latency at 10K-100K vectors; ACID compliance for financial data |
| **Embedding Model** | **BGE-M3** (self-hosted) or **OpenAI text-embedding-3-small** (API) | BGE-M3: free, 100+ languages including Ukrainian, 1024d. OpenAI: simpler API, $0.02/1M tokens |
| **Framework** | **LangChain** or **LlamaIndex** | Both have pgvector integration; makes vector store swappable later |
| **Hosting** | Supabase (free tier) or existing PG | Supabase includes pgvector out of the box |

**Estimated cost: $0-25/month** for vector storage component.

### Phase 2: Production Scale (6-18 months)

| Component | Recommendation | Rationale |
|---|---|---|
| **Vector Store** | **Qdrant** (cloud or self-hosted) or continue pgvector | Qdrant if you need advanced filtering, hybrid search, or hit pgvector scaling limits |
| **Embedding Model** | **BGE-M3** (fine-tuned on Ukrainian financial corpus) | Fine-tuning improves domain-specific retrieval quality |
| **Hybrid Search** | Add BM25/sparse retrieval alongside dense vectors | Financial queries often contain specific terms (e.g., tax codes) that benefit from keyword matching |

**Estimated cost: $25-100/month** for vector storage component.

### Phase 3: Scale (18+ months)

| Component | Recommendation | Rationale |
|---|---|---|
| **Vector Store** | **Qdrant Cloud** or **Weaviate** | If corpus grows to 1M+ vectors or you need multi-tenant support |
| **Architecture** | Consider knowledge graph augmentation | Financial relationships benefit from graph-based reasoning |

---

## 10. Decision Matrix Summary

**For a startup building a Ukrainian-language financial literacy RAG system with ~10K-100K documents:**

| Criterion | Winner | Runner-up |
|---|---|---|
| **Lowest cost** | pgvector (free on existing PG) | Chroma (free self-hosted) |
| **Easiest setup** | Chroma (pip install, no config) | pgvector (one SQL command on existing PG) |
| **Best for production** | Qdrant | Weaviate |
| **Best PostgreSQL integration** | pgvector (native) | -- |
| **Best hybrid search** | Weaviate | Qdrant |
| **Best metadata filtering** | Qdrant | pgvector (SQL WHERE) |
| **Best for Ukrainian text** | All equal (depends on embedding model) | -- |
| **Best embedding for Ukrainian** | BGE-M3 (free, open-source) | Cohere embed-multilingual-v3.0 |
| **Best managed service** | Pinecone | Qdrant Cloud |
| **Best for financial data compliance** | pgvector (PG security ecosystem) | Pinecone (SOC2) |
| **Overall recommendation** | **pgvector** (start) -> **Qdrant** (scale) | -- |

---

## 11. Confidence Assessment

| Finding | Confidence | Basis |
|---|---|---|
| pgvector performance at 10K-100K vectors | **HIGH** | AWS, Google Cloud, and Crunchy Data benchmarks |
| Pricing comparisons | **HIGH** | Official pricing pages accessed March 2026 |
| BGE-M3 Ukrainian language support | **HIGH** | Model documentation lists 100+ languages |
| Ukrainian-specific embedding quality | **MEDIUM** | Limited head-to-head benchmarks on Ukrainian financial text |
| Framework integration availability | **HIGH** | Verified from official documentation |
| pgvector as recommended starting choice | **HIGH** | Consistent recommendation across 10+ sources for startup/small-scale RAG |
| Qdrant as scale-up path | **HIGH** | Strong performance + pricing + features consensus |
| Knowledge graph augmentation value for finance | **MEDIUM** | Supported by Neo4j research but may be premature for MVP |

---

## 12. All Sources Referenced

### Vector Database Comparisons
- [LiquidMetal AI - Vector Database Comparison 2025](https://liquidmetal.ai/casesAndBlogs/vector-comparison/)
- [Firecrawl - Best Vector Databases 2026](https://www.firecrawl.dev/blog/best-vector-databases)
- [DataCamp - 7 Best Vector Databases 2026](https://www.datacamp.com/blog/the-top-5-vector-databases)
- [Elisheba Anderson/Medium - Choosing the Right Vector Database](https://medium.com/@elisheba.t.anderson/choosing-the-right-vector-database-opensearch-vs-pinecone-vs-qdrant-vs-weaviate-vs-milvus-vs-037343926d7e)
- [Digital One Agency - Best Vector Database for RAG 2025](https://digitaloneagency.com.au/best-vector-database-for-rag-in-2025-pinecone-vs-weaviate-vs-qdrant-vs-milvus-vs-chroma/)
- [Latenode - Best Vector Databases for RAG 2025](https://latenode.com/blog/ai-frameworks-technical-infrastructure/vector-databases-embeddings/best-vector-databases-for-rag-complete-2025-comparison-guide)
- [Rost Glukhov - Vector Stores for RAG Comparison](https://www.glukhov.org/post/2025/12/vector-stores-for-rag-comparison/)
- [AIMultiple - Top Vector Database for RAG](https://research.aimultiple.com/vector-database-for-rag/)
- [Liveblocks - Best Vector Database for AI Products](https://liveblocks.io/blog/whats-the-best-vector-database-for-building-ai-products)
- [SysDebug - Vector Database Comparison Guide 2025](https://sysdebug.com/posts/vector-database-comparison-guide-2025/)
- [Xenoss - Pinecone vs Qdrant vs Weaviate](https://xenoss.io/blog/vector-database-comparison-pinecone-qdrant-weaviate)
- [ZenML - 10 Best Vector Databases for RAG](https://www.zenml.io/blog/vector-databases-for-rag)
- [Azumo - Top 6 Vector Database Solutions for RAG 2026](https://azumo.com/artificial-intelligence/ai-insights/top-vector-database-solutions)

### Pricing
- [Pinecone Pricing](https://www.pinecone.io/pricing/)
- [Pinecone Pricing and Limits Docs](https://docs.pinecone.io/guides/assistant/pricing-and-limits)
- [PE Collective - Pinecone Pricing 2026](https://pecollective.com/tools/pinecone-pricing/)
- [Qdrant Pricing](https://qdrant.tech/pricing/)
- [Weaviate Pricing](https://weaviate.io/pricing)
- [Weaviate Serverless Pricing](https://weaviate.io/pricing/serverless)
- [Weaviate Pricing Update Blog](https://weaviate.io/blog/weaviate-cloud-pricing-update)
- [Chroma Pricing](https://www.trychroma.com/pricing)
- [MetaCTO - True Cost of Pinecone](https://www.metacto.com/blogs/the-true-cost-of-pinecone-a-deep-dive-into-pricing-integration-and-maintenance)

### pgvector Performance and Usage
- [AWS - pgvector 0.8.0 on Aurora PostgreSQL](https://aws.amazon.com/blogs/database/supercharging-vector-search-performance-and-relevance-with-pgvector-0-8-0-on-amazon-aurora-postgresql/)
- [Crunchy Data - HNSW Indexes with pgvector](https://www.crunchydata.com/blog/hnsw-indexes-with-postgres-and-pgvector)
- [Google Cloud - Faster Similarity Search with pgvector](https://cloud.google.com/blog/products/databases/faster-similarity-search-performance-with-pgvector-indexes)
- [Mastra Blog - Benchmarking pgvector RAG Performance](https://mastra.ai/blog/pgvector-perf)
- [Markaicode - Production RAG with pgvector <10ms Queries](https://markaicode.com/pgvector-rag-production/)
- [Instaclustr - pgvector Performance Benchmarks](https://www.instaclustr.com/education/vector-database/pgvector-performance-benchmark-results-and-5-ways-to-boost-performance/)
- [Instaclustr - pgvector Features and Pros/Cons 2026](https://www.instaclustr.com/education/vector-database/pgvector-key-features-tutorial-and-pros-and-cons-2026-guide/)
- [Encore Blog - You Probably Don't Need a Vector Database](https://encore.dev/blog/you-probably-dont-need-a-vector-database)
- [CodeAwake - PostgreSQL with pgvector for RAG](https://codeawake.com/blog/postgresql-vector-database)
- [DEV Community - Vector Databases vs pgvector for RAG](https://dev.to/simplr_sh/vector-databases-vs-postgresql-with-pgvector-for-rag-setups-1lg2)
- [DBA Dataverse - PostgreSQL vs Vector Database 2025](https://dbadataverse.com/poetry/2025/12/postgresql-beat-vector-databases-dba-perspective)
- [EnterpriseDB - RAG App with pgvector](https://www.enterprisedb.com/blog/rag-app-postgres-and-pgvector)
- [Scieneers - RAG using PostgreSQL](https://www.scieneers.de/en/from-zero-to-hero-implementing-rag-using-postgresql/)
- [Ronak Rathore/Medium - pgvector Benchmarks and Reality Check](https://medium.com/@DataCraft-Innovations/postgres-vector-search-with-pgvector-benchmarks-costs-and-reality-check-f839a4d2b66f)
- [Clarvo - Optimizing Filtered Vector Queries in PostgreSQL](https://www.clarvo.ai/blog/optimizing-filtered-vector-queries-from-tens-of-seconds-to-single-digit-milliseconds-in-postgresql)

### Multilingual Embeddings and Ukrainian Support
- [HuggingFace - BAAI/bge-m3](https://huggingface.co/BAAI/bge-m3)
- [HuggingFace - ukr-paraphrase-multilingual-mpnet-base](https://huggingface.co/lang-uk/ukr-paraphrase-multilingual-mpnet-base)
- [Cohere Embed Models](https://docs.cohere.com/docs/cohere-embed)
- [Zilliz - embed-multilingual-v3.0 Guide](https://zilliz.com/ai-models/embed-multilingual-v3.0)
- [OpenAI - text-embedding-3-small](https://platform.openai.com/docs/models/text-embedding-3-small)
- [OpenAI - New Embedding Models](https://openai.com/index/new-embedding-models-and-api-updates/)
- [BentoML - Best Open-Source Embedding Models 2026](https://www.bentoml.com/blog/a-guide-to-open-source-embedding-models)
- [Elephas - 13 Best Embedding Models 2026](https://elephas.app/blog/best-embedding-models)
- [Elastic - Multilingual Vector Search with E5](https://www.elastic.co/search-labs/blog/multilingual-vector-search-e5-embedding-model)
- [Primer AI - Language Agnostic Multilingual Embeddings](https://primer.ai/developer/language-agnostic-multilingual-sentence-embedding-models-for-semantic-search/)

### Framework Integrations
- [Qdrant - LangChain Integration](https://qdrant.tech/documentation/frameworks/langchain/)
- [LangChain - Qdrant Docs](https://docs.langchain.com/oss/python/integrations/vectorstores/qdrant)
- [LlamaIndex - Vector Stores](https://developers.llamaindex.ai/python/framework/community/integrations/vector_stores/)
- [Contabo - LlamaIndex vs LangChain 2026](https://contabo.com/blog/llamaindex-vs-langchain-which-one-to-choose-in-2026/)

### Financial RAG
- [Neo4j - Knowledge Graph vs Vector RAG Financial Analysis](https://neo4j.com/blog/developer/knowledge-graph-vs-vector-rag/)
- [FinSage - Multi-aspect RAG for Financial Filings](https://arxiv.org/html/2504.14493v1)
- [Writer - RAG Vector Database Limitations](https://writer.com/engineering/rag-vector-database/)
