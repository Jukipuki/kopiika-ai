# RAG Financial Literacy Corpus

## Purpose

This directory contains the curated financial education knowledge base used by the RAG-powered Education Agent (Story 3.3). The corpus provides the source material that gets embedded into pgvector for retrieval-augmented generation.

The content is **educational only** — no financial advice. All documents follow a consistent structure optimized for section-level chunking during embedding.

## Directory Structure

```
backend/data/rag-corpus/
├── en/                  # English documents
│   ├── budgeting-basics.md
│   ├── emergency-fund.md
│   └── ...
├── uk/                  # Ukrainian documents
│   ├── budgeting-basics.md
│   ├── emergency-fund.md
│   └── ...
└── README.md
```

**Language pairing:** Each topic has matching filenames in both `en/` and `uk/` directories (e.g., `en/budgeting-basics.md` and `uk/budgeting-basics.md`). This enables language-matched retrieval based on user preference.

## Document Format Specification

Every corpus document follows this markdown structure:

```markdown
# [Topic Title]

## Overview
[2-3 sentence beginner-friendly introduction]

## Key Concepts
- **[Concept 1]**: [Plain-language definition]
- **[Concept 2]**: [Plain-language definition]
[3-5 concepts minimum]

## Practical Examples
[2-3 realistic scenarios with specific amounts]

### Example: [Scenario Name]
[Concrete scenario with numbers]

## Actionable Takeaways
1. [Educational step — not advice]
2. [Educational step]
3. [Educational step]
[3-5 takeaways]

## Related Topics
- [topic-slug] — [one-line description]
```

### Section Guidelines

- **Target length:** ~200 words per H2 section (100-300 word range)
- **Chunking:** Story 3.3 chunks by H2 sections for embedding — consistent headers are critical
- **Cross-references:** Use kebab-case filename slugs (without `.md`) in Related Topics

### Content Rules

- **No financial advice:** Use educational framing ("Many people find...", "Some approaches include...")
- **Ukrainian amounts:** Use `₴` symbol or "грн" with realistic 2025-2026 values
- **English amounts:** Include UAH with approximate USD context for cross-lingual alignment
- **Language quality:** Ukrainian documents use natural Ukrainian (not word-for-word translations)

## Encoding

All files: UTF-8, LF line endings, no BOM.

## Topics Covered (20 core + supplemental)

| # | Topic Slug | EN | UK |
|---|-----------|----|----|
| 1 | budgeting-basics | yes | yes |
| 2 | emergency-fund | yes | yes |
| 3 | savings-strategies | yes | yes |
| 4 | debt-management | yes | yes |
| 5 | subscription-tracking | yes | yes |
| 6 | spending-categories | yes | yes |
| 7 | investment-basics | yes | yes |
| 8 | 50-30-20-rule | yes | yes |
| 9 | groceries-food-spending | yes | yes |
| 10 | transport-spending | yes | yes |
| 11 | utilities-bills | yes | yes |
| 12 | healthcare-spending | yes | yes |
| 13 | entertainment-spending | yes | yes |
| 14 | shopping-habits | yes | yes |
| 15 | understanding-inflation | yes | yes |
| 16 | interest-and-credit | yes | yes |
| 17 | financial-goals | yes | yes |
| 18 | cash-vs-digital-payments | yes | yes |
| 19 | spending-patterns | yes | yes |
| 20 | financial-literacy-levels | yes | yes |
| S1 | hryvnia-basics | yes | yes |
| S2 | ukrainian-tax-basics | yes | yes |
| S3 | monobank-ecosystem | yes | yes |
