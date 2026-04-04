# Story 3.2: RAG Financial Literacy Corpus Creation

Status: done
Created: 2026-04-04
Epic: 3 - AI-Powered Financial Insights & Teaching Feed

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **user**,
I want the system to have a curated financial education knowledge base,
so that the AI can teach me about personal finance using quality, relevant content.

## Acceptance Criteria

1. **Given** the RAG system needs source material, **When** the corpus is prepared, **Then** 20-30 core financial literacy documents are created covering key personal finance concepts: budgeting, savings, debt management, subscription tracking, spending categories, emergency funds, investment basics, and Ukrainian-specific financial topics (hryvnia, Monobank ecosystem, Ukrainian tax basics)

2. **Given** the target audience includes Ukrainian users, **When** the corpus documents are written, **Then** each document exists in both Ukrainian and English versions, using natural language appropriate for the target literacy levels (beginner to intermediate)

3. **Given** the corpus documents, **When** they are structured, **Then** each document has: a clear topic title, key concepts section, practical examples with realistic Ukrainian financial scenarios (amounts in UAH), and actionable takeaways

4. **Given** the corpus is complete, **When** it is reviewed, **Then** content is factually accurate, avoids financial advice (education only), and is stored in a structured format ready for embedding (markdown files in a designated `backend/data/rag-corpus/` directory)

## Tasks / Subtasks

- [x] Task 1: Create the corpus directory structure (AC: #4)
  - [x] 1.1 Create `backend/data/rag-corpus/en/` directory for English documents
  - [x] 1.2 Create `backend/data/rag-corpus/uk/` directory for Ukrainian documents
  - [x] 1.3 Create `backend/data/rag-corpus/README.md` documenting the corpus purpose, structure, and document format spec

- [x] Task 2: Create English (EN) corpus documents — 20 topics (AC: #1, #2, #3, #4)
  - [x] 2.1 `en/budgeting-basics.md` — What budgeting is, why it matters, simple monthly budget framework
  - [x] 2.2 `en/emergency-fund.md` — Purpose of emergency fund, 3-6 months rule, how to build it incrementally
  - [x] 2.3 `en/savings-strategies.md` — Pay-yourself-first, auto-savings, setting savings goals
  - [x] 2.4 `en/debt-management.md` — Types of debt, avalanche vs snowball methods, avoiding debt traps
  - [x] 2.5 `en/subscription-tracking.md` — Subscription creep, how to audit subscriptions, cancellation strategy
  - [x] 2.6 `en/spending-categories.md` — How spending categories work, why tracking categories reveals patterns
  - [x] 2.7 `en/investment-basics.md` — Difference between saving and investing, risk vs return basics, NOT advice
  - [x] 2.8 `en/50-30-20-rule.md` — The 50/30/20 budget rule, needs vs wants vs savings, practical application
  - [x] 2.9 `en/groceries-food-spending.md` — Common food spending patterns, meal planning for savings, bulk buying
  - [x] 2.10 `en/transport-spending.md` — Car vs public transport costs, fuel tracking, ride-sharing economics
  - [x] 2.11 `en/utilities-bills.md` — Reducing utility costs, understanding bill structure, payment scheduling
  - [x] 2.12 `en/healthcare-spending.md` — Budgeting for health, preventive care vs reactive spending
  - [x] 2.13 `en/entertainment-spending.md` — Balancing entertainment in a budget, free vs paid options
  - [x] 2.14 `en/shopping-habits.md` — Impulse buying psychology, wishlist strategy, sales cycle awareness
  - [x] 2.15 `en/understanding-inflation.md` — What inflation does to purchasing power, real vs nominal values
  - [x] 2.16 `en/interest-and-credit.md` — How interest works, APR vs APY, the true cost of credit cards
  - [x] 2.17 `en/financial-goals.md` — SMART financial goals, short vs long-term goals, tracking progress
  - [x] 2.18 `en/cash-vs-digital-payments.md` — Pros/cons of cash vs digital, spending psychology differences
  - [x] 2.19 `en/spending-patterns.md` — How to read your own spending data, seasonal patterns, anomaly detection
  - [x] 2.20 `en/financial-literacy-levels.md` — What beginner/intermediate/advanced financial literacy looks like

- [x] Task 3: Create Ukrainian (UK) corpus documents — same 20 topics with Ukrainian context (AC: #1, #2, #3, #4)
  - [x] 3.1 `uk/budgeting-basics.md` — Ukrainian version with UAH examples, local cost-of-living context
  - [x] 3.2 `uk/emergency-fund.md` — Ukrainian context: hryvnia volatility, local savings options
  - [x] 3.3 `uk/savings-strategies.md` — Ukrainian banking options, deposit rates, savings tools
  - [x] 3.4 `uk/debt-management.md` — Ukrainian credit landscape, NBU rate context, avoiding predatory lenders
  - [x] 3.5 `uk/subscription-tracking.md` — Popular Ukrainian digital subscriptions (Netflix UA, Spotify UA, etc.)
  - [x] 3.6 `uk/spending-categories.md` — Ukrainian spending category context (ринок vs супермаркет, etc.)
  - [x] 3.7 `uk/investment-basics.md` — Ukrainian investment context, ОВДП (government bonds), NOT advice
  - [x] 3.8 `uk/50-30-20-rule.md` — Adapted for Ukrainian average salary ranges and cost-of-living
  - [x] 3.9 `uk/groceries-food-spending.md` — Ukrainian food prices, ринок vs ATB vs Silpo comparison
  - [x] 3.10 `uk/transport-spending.md` — Kyiv metro/bus vs private car, fuel prices UAH context
  - [x] 3.11 `uk/utilities-bills.md` — Ukrainian utility structure (ЖКП), tariffs, subsidy awareness
  - [x] 3.12 `uk/healthcare-spending.md` — Ukrainian healthcare system, private vs public, insurance basics
  - [x] 3.13 `uk/entertainment-spending.md` — Ukrainian entertainment costs (cinema, cafes, events in UAH)
  - [x] 3.14 `uk/shopping-habits.md` — Ukrainian retail context, Rozetka/OLX habits, seasonal sales
  - [x] 3.15 `uk/understanding-inflation.md` — UAH inflation history, hryvnia purchasing power erosion
  - [x] 3.16 `uk/interest-and-credit.md` — Ukrainian credit rates (often 30-60% APR), Monobank credit context
  - [x] 3.17 `uk/financial-goals.md` — Goal-setting in UAH, realistic targets for Ukrainian income levels
  - [x] 3.18 `uk/cash-vs-digital-payments.md` — Monobank/PrivatBank digital ecosystem, cashless Ukraine
  - [x] 3.19 `uk/spending-patterns.md` — Seasonal patterns in Ukraine (holidays, utility season, etc.)
  - [x] 3.20 `uk/monobank-ecosystem.md` — Monobank-specific: cashback categories, Рахунки, Банки (savings pots)

- [x] Task 4: Create Ukrainian-specific supplemental documents (AC: #1, #4)
  - [x] 4.1 `uk/hryvnia-basics.md` — UAH currency fundamentals, kopiykas, exchange rate awareness
  - [x] 4.2 `uk/ukrainian-tax-basics.md` — ФОП basics, ПДФО (income tax), ЄСВ — educational overview only
  - [x] 4.3 `en/monobank-ecosystem.md` — English equivalent: Monobank overview for non-Ukrainian-speaking users
  - [x] 4.4 `en/ukrainian-tax-basics.md` — English overview of Ukrainian tax system for context

- [x] Task 5: Quality review of all documents (AC: #4)
  - [x] 5.1 Verify every document follows the required 4-section format: title, key concepts, practical examples (UAH amounts), actionable takeaways
  - [x] 5.2 Verify no document makes financial advice statements (no "you should invest in X", "buy Y stock"); only educational framing ("some people find that...")
  - [x] 5.3 Verify all UAH amounts are realistic as of 2025-2026 (e.g., average Kyiv salary ~25,000-35,000 UAH/month, coffee ~80-120 UAH, grocery basket ~500-1000 UAH/week)
  - [x] 5.4 Verify all Ukrainian text is grammatically correct Ukrainian (not Russian — use "гроші", "зарплата", not "деньги", "зарплата" — same word but double check other terms)
  - [x] 5.5 Verify document filenames use kebab-case matching topic slugs (consistent with RAG retrieval)

### Review Follow-ups (AI)

- [x] [AI-Review][HIGH] Expand H2 sections to meet 100-300 word target — 96/176 content sections (55%) are under 100 words. Overview sections are worst at 38-59 words. Dev Notes warn "shorter chunks lack context for meaningful embeddings." Requires careful bilingual content expansion across all 44 documents.
  - Overview sections: all 44 docs under 60 words (target: 100-300)
  - Actionable Takeaways: ~30 docs under 100 words
  - Key Concepts and Practical Examples: mostly adequate

## Dev Notes

### What This Story Is

This is a **content creation story** — the deliverable is 40-44 markdown files forming the RAG corpus. There is no application code to write. The corpus documents are created in Step 3.2 so that Story 3.3 (RAG Knowledge Base & Education Agent) can embed them into pgvector.

**This story is NOT about embedding or RAG infrastructure** — that's Story 3.3. Story 3.2 only creates the source markdown files.

### Required Document Format (MUST follow exactly)

Every corpus document MUST follow this exact markdown structure for consistent chunking during embedding (Story 3.3):

```markdown
# [Topic Title in English or Ukrainian]

## Overview
[2-3 sentence introduction to the topic — beginner-friendly, no jargon]

## Key Concepts
- **[Concept 1]**: [Plain-language definition]
- **[Concept 2]**: [Plain-language definition]
- **[Concept 3]**: [Plain-language definition]
[3-5 concepts minimum]

## Practical Examples
[2-3 realistic scenarios with specific UAH amounts for UK documents, or approximate USD-equivalent context for EN documents. Use relatable Ukrainian scenarios: family of 3, freelancer, young professional.]

### Example: [Scenario Name]
[Specific scenario with concrete numbers]

## Actionable Takeaways
1. [Concrete, actionable step — not advice, but educational]
2. [Concrete, actionable step]
3. [Concrete, actionable step]
[3-5 takeaways]

## Related Topics
- [Related topic slug] — [one-line description]
```

**Why this structure matters:** Story 3.3 will chunk documents by H2 sections for embedding. Consistent H2 headers (`## Overview`, `## Key Concepts`, etc.) ensure each section becomes a meaningful embedding unit that the Education Agent can retrieve with precision.

**Target length per section:** Each H2 section should be 100-300 words. Shorter chunks lack context for meaningful embeddings; longer chunks dilute retrieval precision. Aim for ~200 words per section as a sweet spot.

**Populating `## Related Topics`:** Use the kebab-case filename slug (without `.md`) to cross-reference 2-4 related topics. Example for `budgeting-basics.md`:
```markdown
## Related Topics
- 50-30-20-rule — A practical framework for organizing your budget
- spending-categories — Understanding where your money goes
- financial-goals — Setting targets your budget should serve
```

### File Naming Convention

```
backend/data/rag-corpus/
├── en/
│   ├── budgeting-basics.md
│   ├── emergency-fund.md
│   └── ...
├── uk/
│   ├── budgeting-basics.md    ← same slug as EN counterpart
│   ├── emergency-fund.md
│   └── ...
└── README.md
```

**Critical:** Ukrainian and English counterparts MUST share the same filename slug (e.g., `budgeting-basics.md` in both `en/` and `uk/`). This enables Story 3.3 to load language-matched content based on user preference.

**Encoding:** All files must be UTF-8 with LF line endings (no BOM). Critical for Cyrillic text in Ukrainian documents.

### Directory Location Conflict: Architecture vs Epics

The epics.md acceptance criteria specify `backend/data/rag-corpus/` as the corpus location. The architecture document shows `backend/app/rag/content/`. **Use `backend/data/rag-corpus/`** — this is the authoritative spec from the epics file. The architecture's `content/` directory appears to be a rough sketch, not a precise path.

**Story 3.3 MUST load from `backend/data/rag-corpus/`, NOT from `backend/app/rag/content/`.** The architecture also uses `_uk.md`/`_en.md` filename suffixes — ignore that; use language subdirectories (`en/`, `uk/`) with matching slugs as specified below.

### Content Guidelines

**Language requirements:**
- English documents: Clear, accessible language for beginner-to-intermediate financial literacy. Avoid Wall Street jargon. Target reading level: 8th grade.
- Ukrainian documents: Natural Ukrainian (not translated from English word-for-word). Use financial terminology that Ukrainians actually use: "фінансова подушка" (not "фінансовий резервний фонд"), "безготівкові розрахунки", etc.

**Financial advice guardrails (CRITICAL):**
- ✅ OK: "Many financial educators suggest building 3-6 months of expenses as an emergency fund"
- ✅ OK: "Some people find the 50/30/20 rule helpful for organizing their spending"
- ❌ NOT OK: "You should save 20% of your income"
- ❌ NOT OK: "Investing in ОВДП is a good idea"
- ❌ NOT OK: "You need to cancel your subscriptions"

The system displays a financial advice disclaimer (FR36). Corpus content must be educational-only to stay consistent with that disclaimer.

**Ukrainian amounts (realistic as of 2025-2026):**
- Average monthly salary in Kyiv: 25,000–40,000 UAH (net)
- Grocery basket for 1 person/week: 600–1,200 UAH
- Coffee (café): 80–130 UAH
- Cinema ticket: 180–320 UAH
- Monobank credit card APR: typically 35–55% annually
- Utility bill (2-room apartment, Kyiv): 2,500–5,000 UAH/month in winter

### UAH Amounts in Examples

All Ukrainian documents should use UAH amounts with the `₴` symbol or "грн" abbreviation. For English documents, use UAH/UAH equivalents with approximate context (e.g., "~₴800/week on groceries, equivalent to roughly $20 USD at current rates") — this helps the bilingual BGE-M3 model align concepts across languages.

### Testing

There are no automated tests for this story. The "quality review" in Task 5 is manual verification. The real validation of corpus quality happens in Story 3.3 when embedding retrieval precision is tested.

**Current test baseline (must remain unchanged):**
- Backend: ~220 tests (194 pre-3.1 + 26 added in Story 3.1) — must still all pass after this story
- Frontend: 110 tests — must still all pass

Since no code changes are made, test regression is not a concern for this story.

### Corpus Design Decisions That Affect Story 3.3 Embedding Quality

- **Consistent H2 headers** → enables section-level chunking (Story 3.3 chunks by H2)
- **Same slug filenames** → enables language-matched retrieval
- **Topic coverage** → determines what questions the Education Agent can answer
- **Specific UAH examples** → anchors the RAG to Ukrainian financial reality (not generic US/EU finance)

### Previous Story Intelligence (from 3.1)

Learnings relevant to corpus content work:
- The pipeline supports bilingual output via user language preference — corpus documents in both languages must exist for this to work
- Education Agent (3.3) uses BGE-M3 cross-lingual embeddings, meaning a query in Ukrainian can match an English document and vice versa — but having both languages improves precision significantly

### Project Structure Notes

- New top-level `backend/data/` directory will be created — this is for data files, not application code
- The `backend/data/rag-corpus/` path does not conflict with any existing directories
- Git-track the corpus files (they are source material, not build artifacts)
- No `.gitignore` changes needed

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Epic 3, Story 3.2] — acceptance criteria and topic requirements
- [Source: _bmad-output/planning-artifacts/architecture.md#Vector Embeddings — pgvector with BGE-M3 1024 dimensions]
- [Source: _bmad-output/planning-artifacts/architecture.md#Backend Directory Structure — rag/ content/]
- [Source: _bmad-output/planning-artifacts/architecture.md#Bilingual Internationalization — BGE-M3 cross-lingual embeddings]
- [Source: _bmad-output/planning-artifacts/architecture.md#NFR16 — RAG knowledge base supports 50-100 documents at MVP]
- [Source: _bmad-output/implementation-artifacts/3-1-transaction-categorization-agent.md — FinancialPipelineState design, established agent patterns]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6 (claude-opus-4-6)

### Debug Log References

N/A — content creation story, no code debugging required.

### Completion Notes List

- Created 46 markdown corpus files (23 EN + 23 UK) covering 20 core financial literacy topics + 6 supplemental documents (full bilingual parity)
- All documents follow the required 5-section format: Overview, Key Concepts, Practical Examples, Actionable Takeaways, Related Topics
- EN and UK counterparts share matching filename slugs for language-matched retrieval
- All UAH amounts are realistic for 2025-2026 (salary ₴25,000-40,000, groceries ₴600-1,200/week, coffee ₴80-130, etc.)
- No financial advice statements — all content uses educational framing
- Ukrainian documents written in natural Ukrainian (verified no Russian language contamination)
- All filenames use kebab-case convention consistent with RAG retrieval requirements
- Backend tests pass (220/220). Frontend tests have pre-existing failures (15 suites fail on clean main branch as well — unrelated to this story)
- README.md documents corpus purpose, structure, format spec, and topic index
- [Review Fix] Expanded all H2 content sections to meet 100-300 word target. All 184 content sections (excl. Related Topics) now pass the 100-word minimum — 100% pass rate, up from 55%

### Change Log

- 2026-04-04: Created RAG financial literacy corpus — 44 documents (22 EN, 22 UK) covering budgeting, savings, debt, investment basics, spending categories, Ukrainian-specific financial topics (Monobank, hryvnia, tax system)
- 2026-04-04: [Review Fix] Added 2 missing bilingual counterparts (uk/financial-literacy-levels.md, en/hryvnia-basics.md) to achieve full bilingual parity (AC #2). Fixed README misleading topic index. Added USD context to en/debt-management.md for BGE-M3 alignment. Total: 46 documents (23 EN + 23 UK).
- 2026-04-04: [Review Fix] Expanded H2 content sections across all 46 documents to meet 100-300 word target for embedding quality. Primary expansions: Overview sections (all 44 docs expanded from ~40-60 words to 100-150+ words), Actionable Takeaways (~30 docs expanded from ~70-95 words to 130-170+ words). Verified 184/184 content sections now meet the 100-word minimum (100% pass rate, up from 55%).
- 2026-04-04: [Review Fix] Reframed imperative financial advice language in Actionable Takeaways to educational framing across 9 documents (en/interest-and-credit, en/subscription-tracking, en/emergency-fund, en/ukrainian-tax-basics, en/cash-vs-digital-payments, en/groceries-food-spending, en/hryvnia-basics, en/understanding-inflation, uk/financial-literacy-levels). Added missing ending punctuation to 31 takeaway items across 7 EN docs and 1 UK doc. All sections remain within 100-300 word target.

### File List

- backend/data/rag-corpus/README.md (new)
- backend/data/rag-corpus/en/budgeting-basics.md (new)
- backend/data/rag-corpus/en/emergency-fund.md (new)
- backend/data/rag-corpus/en/savings-strategies.md (new)
- backend/data/rag-corpus/en/debt-management.md (new)
- backend/data/rag-corpus/en/subscription-tracking.md (new)
- backend/data/rag-corpus/en/spending-categories.md (new)
- backend/data/rag-corpus/en/investment-basics.md (new)
- backend/data/rag-corpus/en/50-30-20-rule.md (new)
- backend/data/rag-corpus/en/groceries-food-spending.md (new)
- backend/data/rag-corpus/en/transport-spending.md (new)
- backend/data/rag-corpus/en/utilities-bills.md (new)
- backend/data/rag-corpus/en/healthcare-spending.md (new)
- backend/data/rag-corpus/en/entertainment-spending.md (new)
- backend/data/rag-corpus/en/shopping-habits.md (new)
- backend/data/rag-corpus/en/understanding-inflation.md (new)
- backend/data/rag-corpus/en/interest-and-credit.md (new)
- backend/data/rag-corpus/en/financial-goals.md (new)
- backend/data/rag-corpus/en/cash-vs-digital-payments.md (new)
- backend/data/rag-corpus/en/spending-patterns.md (new)
- backend/data/rag-corpus/en/financial-literacy-levels.md (new)
- backend/data/rag-corpus/en/hryvnia-basics.md (new — review fix)
- backend/data/rag-corpus/en/monobank-ecosystem.md (new)
- backend/data/rag-corpus/en/ukrainian-tax-basics.md (new)
- backend/data/rag-corpus/uk/budgeting-basics.md (new)
- backend/data/rag-corpus/uk/emergency-fund.md (new)
- backend/data/rag-corpus/uk/savings-strategies.md (new)
- backend/data/rag-corpus/uk/debt-management.md (new)
- backend/data/rag-corpus/uk/subscription-tracking.md (new)
- backend/data/rag-corpus/uk/spending-categories.md (new)
- backend/data/rag-corpus/uk/investment-basics.md (new)
- backend/data/rag-corpus/uk/50-30-20-rule.md (new)
- backend/data/rag-corpus/uk/groceries-food-spending.md (new)
- backend/data/rag-corpus/uk/transport-spending.md (new)
- backend/data/rag-corpus/uk/utilities-bills.md (new)
- backend/data/rag-corpus/uk/healthcare-spending.md (new)
- backend/data/rag-corpus/uk/entertainment-spending.md (new)
- backend/data/rag-corpus/uk/shopping-habits.md (new)
- backend/data/rag-corpus/uk/understanding-inflation.md (new)
- backend/data/rag-corpus/uk/interest-and-credit.md (new)
- backend/data/rag-corpus/uk/financial-goals.md (new)
- backend/data/rag-corpus/uk/cash-vs-digital-payments.md (new)
- backend/data/rag-corpus/uk/spending-patterns.md (new)
- backend/data/rag-corpus/uk/financial-literacy-levels.md (new — review fix)
- backend/data/rag-corpus/uk/monobank-ecosystem.md (new)
- backend/data/rag-corpus/uk/hryvnia-basics.md (new)
- backend/data/rag-corpus/uk/ukrainian-tax-basics.md (new)
