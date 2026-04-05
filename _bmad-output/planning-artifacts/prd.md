---
stepsCompleted:
  - step-01-init
  - step-02-discovery
  - step-02b-vision
  - step-02c-executive-summary
  - step-03-success
  - step-04-journeys
  - step-05-domain
  - step-06-innovation
  - step-07-project-type
  - step-08-scoping
  - step-09-functional
  - step-10-nonfunctional
  - step-11-polish
classification:
  projectType: web_app
  domain: fintech
  complexity: high
  projectContext: greenfield
inputDocuments:
  - product-brief-kopiika-ai-2026-03-15.md
  - market-smart-financial-intelligence-research-2026-03-15.md
  - rag-vs-finetuning-ukrainian-financial-research-2026-03-15.md
  - vector-store-options-financial-rag-research-2026-03-15.md
  - monobank-csv-ukrainian-bank-parsing-research-2026-03-15.md
  - integration-patterns-rag-multi-agent-pipeline-research-2026-03-15.md
  - api-design-data-format-integration-research-2026-03-15.md
  - technical-ai-financial-data-pipeline-research-2026-03-15.md
  - brainstorming-session-2026-02-23.md
  - design-thinking-2026-02-23.md
documentCounts:
  briefs: 1
  research: 7
  brainstorming: 2
  projectDocs: 0
workflowType: 'prd'
lastEdited: '2026-04-05'
editHistory:
  - date: '2026-04-05'
    changes: 'Integrated User Feedback System (4-layer design) — Layers 0-1 in MVP, Layer 2 in Phase 1.5, Layer 3 in Phase 2. Added FR45-FR55, updated Executive Summary, Success Criteria, User Journeys (Anya/Viktor/Dmytro), Product Scope, Domain Requirements, and Phased Development sections.'
    inputDocuments:
      - design-thinking-2026-04-05.md
---

# Product Requirements Document - kōpiika

**Author:** Oleh
**Date:** 2026-03-16

## Executive Summary

kōpiika (AI Financial Coach) is an AI-powered personal finance platform that transforms raw bank statement data into personalized financial education and actionable insights. The product targets Ukraine's 9.88M+ Monobank users and 90% digital banking penetration — a market where no AI-powered, education-first personal finance tool exists.

Users upload bank statements (CSV/PDF) through a trust-first model requiring no bank credentials. A multi-agent AI pipeline processes transactions and delivers personalized insights wrapped in progressive educational content via a card-based Teaching Feed. MVP launches with a streamlined 3-agent pipeline (Ingestion → Categorization → Education) to validate the core hypothesis, expanding to the full 5-agent pipeline (adding Pattern Detection and Triage severity ranking) in Phase 1.5. The system builds a cumulative financial profile with each upload, making insights more accurate and education more relevant over time.

Three primary personas drive the design: Anya (financially inexperienced, needs to learn), Viktor (moderate literacy, wants deeper analytics and optimization), and Dmytro (high literacy, needs blind spots surfaced). All three are served by the same pipeline with adaptive education depth — progressive disclosure layers that expand or compress based on the user's growing financial vocabulary.

The north star metric is **Education-to-Action Conversion Rate** — the percentage of educational insights that result in measurable behavioral change in subsequent uploads. Revenue model is freemium: free tier with basic categorization and top 3 insights, premium at 99-149 UAH/month for the full Teaching Feed, Financial Health Score, predictive forecasts, and subscription detection.

### What Makes This Special

**Education IS the product, not a feature.** Every insight teaches. Every interaction builds financial literacy. The product occupies an empty competitive quadrant — high personalization combined with high education — that neither analytics tools (Cleo, Monarch) nor education platforms (Zogo, Greenlight) have claimed.

**Triage-first prioritization** (Phase 1.5) borrowed from healthcare ER methodology will rank insights by financial impact severity, making the product immediately actionable for users who would be overwhelmed by traditional dashboards. **Cumulative intelligence** creates natural retention: the system visibly gets smarter with each upload, increasing switching costs through growing profile depth and progressively personalized education. A lightweight feedback loop — implicit behavioral signals (card engagement, expansion depth) combined with optional thumbs up/down on insight cards — continuously improves RAG education quality without interrupting the user experience.

**Trust-first architecture** (CSV/PDF upload, no bank credentials) removes the #1 adoption barrier in Ukraine's high-distrust environment. **Ukrainian-native positioning** (UAH, Monobank/PrivatBank formats, local merchant recognition, culturally appropriate framing) provides first-mover advantage with zero direct competitors in-market.

## Project Classification

| Attribute | Value |
|---|---|
| **Project Type** | Web Application (Next.js SPA frontend, FastAPI backend, responsive mobile) |
| **Domain** | Fintech (personal finance, transaction analysis, financial education) |
| **Complexity** | High (financial data sensitivity, GDPR-harmonization compliance, multi-agent AI pipeline, bilingual UK/EN, encryption requirements) |
| **Project Context** | Greenfield (new product from scratch) |
| **Tech Stack** | Next.js, FastAPI, PostgreSQL + pgvector, LangGraph, BGE-M3 embeddings, Redis + Celery, Fondy/LemonSqueezy payments |

## Success Criteria

### User Success

**Anya (The Learner) — Success = Understanding + Saving**
- Identifies her top 3 spending categories after 2 uploads
- Sets first savings goal within 3 months of first upload
- Saves more from product insights than subscription cost (net value positive)
- Expands 40%+ of education layers on insight cards
- Measurable Financial Health Score improvement after 3+ uploads
- Uses thumbs up/down on insight cards that resonate — highest feedback participation rate among personas

**Viktor (The Optimizer) — Success = Actionable Insights + Exploration**
- Receives at least 1 new actionable insight per monthly upload
- Acts on 30%+ of triage-ranked recommendations
- Measurable savings rate improvement over 3-month period
- Provides categorized thumbs-down feedback (reason chips) when insights miss the mark — sparse but high-signal

**Dmytro (The Discoverer) — Success = Blind Spot Discovery + Action**
- Product surfaces at least 1 previously unknown pattern per upload
- Acts on 20%+ of discovered blind spots
- Completes monthly deep-dive in under 15 minutes
- Returns monthly for 6+ consecutive months
- Reports factual errors or miscategorizations via the report-issue mechanism — corrective feedback only

### Business Success

**Phase 1: Capstone Validation (0-3 months)**
- MVP launched and functional end-to-end (upload -> insights -> education)
- First users onboarded and uploading real data
- Cumulative profiles building across active users
- First paid subscriptions (any number — signals willingness to pay)

**Phase 2: Commercial Validation (3-12 months)**
- Growing user base month-over-month
- >25% annual retention (vs. 16% industry average)
- 5-8% freemium-to-paid conversion (above 2-5% industry average)
- Measurable financial literacy improvement in active users

**Validation Gate:** Organic word-of-mouth — users spontaneously recommending the product without prompting. Strong signal = organic referrals + >50% repeat uploads + positive sentiment.

### Technical Success

- **Pipeline processing time:** Full pipeline (3-agent MVP, 5-agent post-Phase 1.5) completes within 60 seconds for a typical monthly statement (~200-500 transactions)
- **Categorization accuracy:** >85% correct classification on first pass (improving with user corrections over time)
- **RAG retrieval quality:** >80% relevance score on retrieved financial education content (graded docs pass threshold)
- **System uptime:** 99.5% availability for core upload and feed functionality
- **Data security:** Zero data breaches, encryption at rest (AES-256) and in transit (TLS 1.3) verified
- **API response times:** <500ms for Teaching Feed card retrieval, <2s for Financial Health Score calculation

### Measurable Outcomes

| KPI | Target | Frequency |
|---|---|---|
| First-upload completion rate | >80% (upload -> view at least 1 insight) | Per new user |
| First-week retention | >30% (vs. 14.9% industry average) | Weekly cohort |
| First-month retention | >50% upload a 2nd statement | Monthly cohort |
| Teaching Feed interaction | 60%+ interact with at least 1 card per session | Per session |
| Education layer expansion | 30%+ of cards have education expanded | Per session |
| Trust score | >3.5/5 average | Post-upload survey |
| Thumbs interaction rate | >5% of viewed cards receive a vote | Monthly (after Layer 1 launch) |
| Implicit-explicit signal correlation | >0.5 correlation between engagement_score and thumb ratio per topic cluster | After 3 months of data |
| Premium conversion (Phase 2) | 5-8% of free users | Monthly |

## Product Scope

### MVP — Minimum Viable Product (0-3 months)

1. **Statement Upload & Parsing** — Drag-and-drop CSV/PDF, Monobank primary, flexible parser for other banks
2. **User Authentication & Data Persistence** — Accounts, secure auth, encrypted storage, one-click deletion
3. **3-Agent AI Pipeline** — Ingestion, Categorization, Education (RAG). Pattern Detection and Triage deferred to Phase 1.5
4. **Teaching Feed (Primary UX)** — Card-based insight feed with progressive disclosure education (triage severity ranking added in Phase 1.5)
5. **Cumulative Financial Profile** — Database-backed growing profile, Financial Health Score (0-100)
6. **Bilingual Support** — English and Ukrainian interface and AI-generated content
7. **Graceful Error Handling** — Format detection, validation, actionable error messages
8. **User Feedback (Layers 0-1)** — Implicit card engagement tracking (time, expansion, velocity) + thumbs up/down on Teaching Feed cards + in-context issue reporting

### Growth Features (Post-MVP Fast Follow, 1-2 months post-launch)

- Enhanced financial literacy level assessment: replace heuristic-based detection with an onboarding quiz or manual level selection by the user (beginner / intermediate / advanced), improving education content calibration accuracy (relates to FR17)
- Feedback Layer 2: contextual follow-up on thumbs-down (preset reason chips), occasional thumbs-up follow-up (1 in 10)
- Basic predictive forecasts (next-month spending predictions)
- Pre-built data queries (curated question set for querying financial data)
- Supplementary dashboard with traditional spending charts
- Natural language chat interface for querying financial data
- User correction feedback loop for categorization improvement
- Monthly "mise en place" prep briefing

### Vision (Future — V2/V3)

- Feedback Layer 3: milestone feedback cards in the feed (3rd upload, Health Score change, quarterly NPS)
- Developer feedback dashboard (aggregate signals, topic cluster quality scores)
- RAG corpus auto-flagging based on aggregated feedback signals
- Savings strategies and passive income education (deposits, government bonds)
- Receipt scanning for itemized transaction detail
- Family mode with age-appropriate financial education
- Gamification (streaks, badges, Financial Health Score milestones)
- Periodic knowledge quizzes based on learned material (daily check-ups on mobile) to reinforce learning and boost engagement
- Bank API integration through partnerships (Monobank, PrivatBank)
- Eastern European expansion (Bulgaria, Croatia, Romania, Georgia)
- Mobile native app

## User Journeys

### Journey 1: Anya's First Upload — From Avoidance to Understanding

**Persona:** Anya, 26, Ukrainian freelancer with irregular income. Low financial literacy. Checks her Monobank balance to see what's left but never analyzes where money goes. Feels stress, guilt, and avoidance around money.

**Opening Scene:** It's the end of the month and Anya's Monobank balance is lower than expected — again. A friend shares an Instagram story showing a financial insight card with the caption "I had no idea I was spending this much on delivery." Anya is curious but skeptical — she doesn't trust finance apps with her data, and she's tried manual trackers before and abandoned them.

**Rising Action:** She visits the site. No account required to see a demo. She decides to try — downloads her Monobank CSV (she's never opened this file before) and drags it into the upload zone. The screen says "Your data stays encrypted and you can delete it anytime." While the pipeline processes, she sees: "Did you know? Tracking spending is the #1 habit of financially healthy people. You just started."

**Climax:** The Teaching Feed appears. Three cards, sorted by severity. The red card says: "You have 4 active subscriptions totaling 1,200 UAH/month. 2 of them had zero activity this month." She taps "Why this matters" and reads a plain-language explanation of subscription creep — no jargon, no judgment. For the first time, she understands where a chunk of her money goes without anyone making her feel bad about it.

**Resolution:** Anya creates an account to save her profile. She cancels one forgotten subscription that evening. Before leaving, she taps the thumbs-up icon on the subscription card — a quiet acknowledgment that it helped. Two weeks later, she gets a gentle email reminder after her next freelance payment lands. She uploads again. The Financial Health Score ticks up from 48 to 53. The Teaching Feed says "Based on your 2 months of data, I can now see your income pattern — your best months are when..." She feels something unfamiliar: a sense of control.

**Requirements revealed:** Upload flow with zero friction, CSV parsing (Monobank), progressive disclosure education cards, triage severity ranking, Financial Health Score, email reminders timed to income patterns, account creation with data persistence, one-click subscription cancellation insights, thumbs up/down on insight cards.

---

### Journey 2: Viktor's Monthly Optimization Ritual

**Persona:** Viktor, 29, software developer in Kyiv. Stable salary, saves regularly, uses Monobank daily. Financially literate but wants deeper analytics than Monobank provides. Curious about optimizing spending and exploring passive income options.

**Opening Scene:** Viktor sees the product mentioned in a DOU (Ukrainian dev community) thread. Someone posted a screenshot of a spending pattern Monobank never surfaced. He's intrigued — he's been exporting CSVs occasionally but never gets further than scanning the numbers.

**Rising Action:** He uploads 3 months of Monobank statements at once. The pipeline processes them and his cumulative profile builds immediately. The Teaching Feed is denser than Anya's — Viktor's education layers are more concise because his literacy level is detected as higher (fewer basic concept expansions). He scrolls through the triage cards quickly, reading headlines.

**Climax:** A yellow card catches his eye: "Your transport spending increased 34% month-over-month. You took 47 taxi rides this month vs. 28 last month — that's an extra 2,100 UAH." He hadn't noticed. The education layer shows his transport-to-income ratio compared to his historical pattern. Below it, a green card confirms his grocery spending is stable and efficient. He feels validated and informed simultaneously.

**Resolution:** Viktor makes this a monthly ritual. After each payday, he uploads the new statement. Each month the insights sharpen — the system knows his patterns better than he does. One month, a card tells him his grocery spending is "above average" — he thumbs it down and taps "Not relevant to me" because he bulk-buys intentionally. The system registers the signal. He starts checking the Financial Health Score like a game. He shares a particularly surprising insight with a colleague — "You should try this."

**Requirements revealed:** Multi-month upload and cumulative processing, adaptive education depth based on literacy detection, month-over-month trend comparison, transport/category breakdown analysis, Financial Health Score gamification, share/export insight capability, thumbs down with categorized reason feedback.

---

### Journey 3: Dmytro Discovers His Blind Spot

**Persona:** Dmytro, 38, marketing manager. Higher income, financially confident. Relies on gut feel and memory for financial decisions. Doesn't think he needs a finance tool.

**Opening Scene:** A colleague mentions the product over lunch: "It found a subscription I'd been paying for 8 months without using." Dmytro is mildly curious — he's confident in his finances but the idea of a quick check appeals to his competitive nature.

**Rising Action:** He uploads one month of his statement expecting confirmation of what he already knows. The processing takes 30 seconds. He scans the triage feed — most cards are green (healthy). He almost closes the tab.

**Climax:** Then he sees the red card: "You have 6 recurring charges totaling 3,400 UAH/month. One subscription (890 UAH/month) has had no related activity in 4 months." He's stunned — he'd completely forgotten about it. That's 3,560 UAH wasted. The education layer doesn't lecture him; it simply shows the annual impact and a one-line action step. His overconfidence cracks.

**Resolution:** He cancels the subscription immediately. Next month he uploads again — this time proactively. The system catches a gradually increasing dining category he hadn't noticed. One card miscategorizes a bank transfer as "entertainment" — Dmytro taps the flag icon and selects "Incorrect info" from the report menu. Takes 3 seconds. Dmytro becomes the product's most vocal advocate at work — not because he needed help, but because the product showed him what he couldn't see. His monthly check-in takes 8 minutes.

**Requirements revealed:** Fast single-upload processing, subscription detection with inactivity flagging, concise high-literacy insight presentation, annual cost impact calculations, fast session experience (<15 min target), in-context issue reporting mechanism.

---

### Journey 4: Self-Service Error Recovery — Failed Parse

**Persona:** Any user uploading a statement that fails to process correctly.

**Opening Scene:** A user downloads a PrivatBank statement (XLS format converted to CSV) and uploads it. The Ingestion Agent detects an unrecognized format — column headers don't match expected patterns.

**Rising Action:** Instead of a cryptic error, the Teaching Feed shows a single card: "We couldn't fully process this file. It looks like a PrivatBank statement — we support Monobank CSV as our primary format. Here's what you can do." The card offers: (1) Try re-exporting as CSV from your bank, (2) Check that the file is a .csv with transaction data, (3) Try uploading a Monobank statement instead.

**Climax:** The user realizes they exported the wrong format. They re-export from PrivatBank in CSV and upload again. This time it partially parses — 80% of transactions are categorized, but some merchant descriptions are unrecognized. The Teaching Feed shows insights for what it could process, with a note: "12 transactions couldn't be categorized automatically. You can review them."

**Resolution:** The user sees that even partial data provides value. They get insights on what was processed and a clear path to improve accuracy on future uploads. Trust is maintained because the system was transparent about what it could and couldn't do.

**Requirements revealed:** Format detection and validation, graceful error handling with actionable guidance, partial parse support, unrecognized transaction flagging, user-facing error messages (not technical errors), multi-bank format flexibility.

---

### Journey 5: Admin Monitoring via Logs (MVP)

**Persona:** Oleh (developer/operator), monitoring system health during early launch.

**Opening Scene:** MVP is live with first beta users. Oleh checks application logs and database to monitor system health.

**Rising Action:** He reviews: pipeline processing times (are they within the 60s target?), categorization accuracy (how many user corrections are happening?), failed upload attempts (what formats are failing?), error rates per agent in the pipeline, user signup and upload counts.

**Climax:** Logs reveal the Pattern Detection Agent is timing out on users with 500+ transactions per upload. He identifies the bottleneck and optimizes the query.

**Resolution:** For MVP, direct log access and database queries provide sufficient operational visibility. Structured logging with correlation IDs (job_id, user_id) enables tracing any upload through the full pipeline. A proper admin dashboard is deferred to post-MVP when user volume justifies it.

**Requirements revealed:** Structured logging with correlation IDs across all pipeline agents, error tracking per agent, processing time metrics, upload success/failure rates, database-queryable job status.

---

### Journey Requirements Summary

| Capability Area | Revealed By Journeys | MVP Priority |
|---|---|---|
| **CSV Upload & Parsing** | Anya, Viktor, Error Recovery | Must have |
| **Multi-month Cumulative Processing** | Viktor, Dmytro | Must have |
| **Teaching Feed with Triage Cards** | All primary journeys | Must have |
| **Progressive Disclosure Education** | Anya, Viktor | Must have |
| **Financial Health Score** | Anya, Viktor | Must have |
| **Subscription Detection** | Anya, Dmytro | Must have |
| **Adaptive Education Depth** | Viktor vs. Anya (different literacy) | Must have |
| **Email Reminders** | Anya (payday-timed) | Phase 1.5 |
| **Graceful Error Handling** | Error Recovery journey | Must have |
| **Format Detection & Validation** | Error Recovery journey | Must have |
| **Structured Pipeline Logging** | Admin journey | Must have |
| **User Account & Data Persistence** | Anya (saves profile) | Must have |
| **Thumbs Up/Down on Cards** | Anya (acknowledges helpful insight), Viktor (flags irrelevant) | Must have |
| **Implicit Card Engagement Tracking** | All journeys (behavioral signals: time, expansion, velocity) | Must have |
| **Issue Reporting on Cards** | Dmytro (flags miscategorization) | Must have |
| **Thumbs-Down Reason Chips** | Viktor (categorizes why insight missed) | Phase 1.5 |
| **Milestone Feedback Cards** | All journeys (end-of-feed, non-intrusive) | Phase 2 |
| **Insight Sharing** | Viktor (shares with colleague) | Nice to have |
| **Admin Dashboard** | Admin journey | Post-MVP |

## Domain-Specific Requirements

### Compliance & Regulatory

- **Ukrainian Data Protection Law (No 2297-VI)** — Current baseline. Build to GDPR standards now as Ukraine actively harmonizes toward GDPR equivalence.
- **GDPR-Aligned Practices** — Data minimization, purpose limitation, right to erasure, explicit consent for AI processing of financial data, data processing records.
- **Financial Advice Disclaimer** — Explicit legal disclaimer in product UI: "This product provides financial insights and education, not financial advice." Sufficient for MVP; legal review recommended before commercial scaling.
- **Data Protection Impact Assessment** — Required for high-risk automated processing of financial data. Prepare DPIA documentation before public launch.

### Data Handling & Retention

- **Retention policy:** Indefinite retention of user financial data to support cumulative intelligence. User has full control — one-click data deletion (including derived embeddings and profile data).
- **Right to erasure:** Complete deletion endpoint covering raw transactions, categorized data, vector embeddings, cumulative profile, Financial Health Score history, and user feedback data (votes, reason selections, free-text responses, issue reports).
- **Data minimization:** Only collect and process data necessary for financial analysis and education delivery.
- **Consent management:** Explicit user consent at signup for AI processing of uploaded financial data. Clear explanation of what the pipeline does with their data. Feedback data (votes, text responses) is user-generated content subject to the same data view and deletion rights.

### Security Requirements

- **Encryption at rest:** AES-256 for all stored financial data (PostgreSQL, pgvector tables, file storage).
- **Encryption in transit:** TLS 1.3 for all API communication. HTTPS everywhere.
- **Authentication:** JWT tokens with short expiry, refresh token rotation. Email + password minimum, social login optional.
- **Authorization:** RBAC — users can only access their own financial data. Tenant isolation in pgvector queries (user-scoped).
- **Zero Trust:** Validate every request, even from internal services.

### AI-Specific Security

- **Prompt injection mitigation:** Input sanitization before LLM processing. Uploaded CSV/PDF content treated as untrusted input.
- **Data leakage prevention:** Output filtering to prevent PII leakage in education responses. No cross-user data contamination in RAG retrieval.
- **Knowledge base integrity:** Financial education content validated and provenance-tracked before ingestion into RAG corpus. Prevent model poisoning through content review.
- **Embedding privacy:** Tenant-isolated pgvector queries prevent embedding inversion attacks across user boundaries.

### Payment Integration

- **PCI-DSS:** Not in scope — card data handled entirely by Fondy (Ukrainian users) and LemonSqueezy (international users). No card numbers, CVVs, or payment credentials touch our system.
- **Webhook security:** Validate webhook signatures from payment providers. Idempotent processing of payment lifecycle events.
- **Subscription state:** Store subscription status in PostgreSQL. Grace period handling for failed payments.

### Fraud Prevention (MVP Scope)

- **Account security:** Rate limiting on login attempts, password strength requirements, optional 2FA.
- **Session management:** Secure session handling, automatic timeout on inactivity.
- **Upload abuse prevention:** File size limits, rate limiting on uploads, format validation before pipeline processing.
- **Monitoring:** Structured logging of authentication events, failed access attempts, and anomalous upload patterns.

### Risk Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Data breach of financial data | Critical | AES-256 encryption, tenant isolation, regular security audits |
| AI hallucination in financial education | High | RAG grounding with verified knowledge base, confidence thresholds on generated content |
| Cross-user data leakage | Critical | User-scoped database queries, tenant-isolated pgvector, no shared state between users |
| GDPR non-compliance | High | Build to GDPR standards from day one, implement full deletion pipeline, maintain processing records |
| Payment provider failure | Medium | Webhook retry handling, grace periods, clear user communication on payment issues |
| Monobank CSV format changes | Medium | Flexible parser architecture, format version detection, graceful degradation on unrecognized columns |

## Innovation & Novel Patterns

### Detected Innovation Areas

**1. Empty Competitive Quadrant: High Personalization + High Education**
No existing product combines personal financial data analysis with contextual, personalized financial education. Analytics tools (Cleo, Monarch, Monobank built-in) analyze without teaching. Education platforms (Zogo, Greenlight) teach without personalizing. This product occupies the intersection — every insight is grounded in the user's actual data and wrapped in education calibrated to their literacy level.

**2. Healthcare Triage Applied to Personal Finance**
Severity-ranked insight prioritization borrowed from ER triage methodology. Financial findings are ranked by impact severity (red/yellow/green), telling users "fix this first." No PFM tool uses this pattern — most present all data equally, overwhelming users who don't know where to start.

**3. Education-as-Architecture (Not Feature)**
The Education Agent is a core pipeline stage, not an optional layer. Even in the MVP 3-agent pipeline, education is inseparable from analysis — and the full 5-agent pipeline (adding Pattern Detection and Triage) only deepens this integration. This is an architectural decision, not a feature toggle — it shapes the entire data flow.

**4. Cumulative Intelligence as Natural Retention**
Each upload makes the system visibly smarter — Financial Health Score evolves, pattern detection improves, education adapts as literacy grows. Retention is driven by increasing value of the accumulated profile, not artificial lock-in. Users stay because leaving means losing their growing financial intelligence.

### Validation Approach

| Innovation | Validation Method | Success Signal |
|---|---|---|
| Education engagement | Progressive disclosure click tracking | >30% of cards have education expanded |
| Triage comprehension | User identifies most important insight without prompting | >80% correctly identify top-priority card |
| Cumulative intelligence value | Return upload rate after 2+ uploads | >50% upload a 2nd statement |
| Behavioral change from education | Spending pattern shifts in subsequent uploads | Detectable change in at least 1 category after 3+ uploads |

### Risk Mitigation

| Innovation Risk | Fallback |
|---|---|
| Users skip education layers entirely | Triage insights provide standalone value as smart analytics — product degrades gracefully |
| Education content feels generic despite personalization | Increase RAG corpus specificity, add user correction loop to improve relevance |
| Cumulative intelligence not visible enough | Add explicit "based on your X months of data..." messaging and before/after comparisons |
| Triage severity feels arbitrary | Ground severity in concrete financial impact (UAH amounts, annual projections) |

## Web Application Specific Requirements

### Project-Type Overview

Single-page application (SPA) built with Next.js, serving an authenticated financial analysis experience. No public-facing SEO requirements — the entire product lives behind authentication. Primary interaction model is upload-then-browse: users upload bank statements and explore AI-generated insights through the Teaching Feed.

### Technical Architecture Considerations

**Frontend Architecture:**
- **Framework:** Next.js with App Router (SPA behavior, client-side navigation)
- **Rendering:** Client-side rendering for all authenticated routes. Static generation only for landing/marketing page if needed later.
- **State management:** React Query / TanStack Query for server state (Teaching Feed cards, Financial Health Score, upload status). Local state for UI interactions.
- **Streaming:** Vercel AI SDK for SSE consumption from FastAPI backend (pipeline progress, streamed insight generation)

**Browser Support:**
- Modern evergreen browsers only: Chrome, Firefox, Safari, Edge (latest 2 versions)
- No IE11 or legacy browser support
- Mobile browser support: Chrome Mobile, Safari iOS (responsive design, not native)

**Responsive Design:**
- Mobile-first responsive layout targeting the Teaching Feed as the primary mobile experience
- Breakpoints: mobile (< 768px), tablet (768-1024px), desktop (> 1024px)
- Touch-optimized card interactions (swipe, tap to expand education layers)
- File upload via native file picker on mobile (no drag-and-drop required)

**Accessibility:**
- WCAG 2.1 AA compliance baseline
- Keyboard navigation for all interactive elements (Teaching Feed cards, upload, menus)
- Screen reader support for insight cards (aria-labels for triage severity, progressive disclosure)
- Color contrast ratios meeting AA standards (critical for red/yellow/green triage indicators — don't rely on color alone)
- Focus management during upload processing and SSE streaming updates

**Real-Time Features (MVP):**
- SSE for pipeline progress during upload processing (the only real-time feature)
- Polling fallback for clients that don't support SSE
- No WebSocket requirements for MVP

**Performance Targets:**
See Non-Functional Requirements > Performance for complete targets. Key frontend metrics:
- Lighthouse performance score: > 80
- Touch-optimized interactions with no perceptible input delay

### Implementation Considerations

**API Integration:**
- Hybrid REST + GraphQL backend (per API design research)
- REST for: file upload, authentication, payment webhooks, health checks
- GraphQL for: Teaching Feed queries (heterogeneous card types), user dashboard, flexible insight queries
- Cursor-based pagination for Teaching Feed (handles async card generation)

**Caching Strategy:**
- React Query cache: 5-15 min TTL for Teaching Feed cards (write-once, read-many)
- Stale-while-revalidate: serve cached insights immediately, refresh in background
- Cache invalidation: only when new upload completes and generates new insights
- No CDN/edge caching needed for MVP (all content is authenticated and personalized)

**File Upload UX:**
- Drag-and-drop zone on desktop
- Native file picker on mobile
- Client-side validation before upload: file type (.csv, .pdf), file size limit (10MB), basic format sniffing
- Progress indicator during upload (HTTP progress) + SSE for pipeline processing progress
- Educational content shown during processing wait time

**Authentication Flow:**
- JWT-based auth with short-lived access tokens + refresh token rotation
- Login / Register pages (email + password)
- Protected route wrapper for all app routes
- Token refresh handled transparently via interceptor

**Bilingual UI:**
- i18n framework (next-intl or similar) for Ukrainian and English
- Language selector in user settings
- AI-generated content language follows user preference
- Static UI strings in both languages from translation files

## Project Scoping & Phased Development

### MVP Strategy & Philosophy

**MVP Approach:** Problem-Solving MVP — prove that AI-powered education through personal financial data changes user behavior. Ship the minimum that delivers the core "aha moment": upload a statement, see personalized insights wrapped in education.

**Resource Requirements:** Solo developer (Oleh), 0-3 month timeline. This constraint drives aggressive scope reduction: every feature must directly serve the core value proposition or be deferred.

**Key Scoping Decision: Simplified 3-Agent Pipeline for MVP**
The full 5-agent pipeline (Ingestion -> Categorization -> Pattern Detection -> Triage -> Education) is reduced to 3 agents for initial launch:
- **Ingestion Agent** — Parse CSV, extract and structure transactions
- **Categorization Agent** — AI-powered transaction classification with MCC codes
- **Education Agent** — RAG-powered insights and education based on categorized data

Pattern Detection and Triage are deferred to Phase 1.5 (fast follow). Rationale: the core innovation hypothesis ("education through personal data changes behavior") can be validated with categorization + education alone. Users still get personalized insights based on their spending categories — pattern detection and severity ranking enhance but aren't required to prove the concept.

### MVP Feature Set (Phase 1: 0-3 months)

**Core User Journeys Supported:**
- Anya's First Upload (simplified — categorized insights without triage ranking)
- Self-Service Error Recovery (format validation, graceful errors)
- Admin Monitoring via Logs

**Must-Have Capabilities:**

| # | Feature | Justification |
|---|---|---|
| 1 | **Statement Upload & Parsing** | Core entry point — without upload, nothing works |
| 2 | **User Authentication & Data Persistence** | Cumulative intelligence requires persistent profiles |
| 3 | **3-Agent AI Pipeline** (Ingestion, Categorization, Education) | Minimum pipeline to deliver personalized financial education |
| 4 | **Teaching Feed** | Primary UX — card-based insights with progressive disclosure education (without triage severity ranking in MVP) |
| 5 | **Cumulative Financial Profile** | Database-backed growing profile, Financial Health Score |
| 6 | **Bilingual Support** | Ukrainian + English — core to market positioning |
| 7 | **Graceful Error Handling** | Format detection, validation, actionable error messages |
| 8 | **User Feedback (Layers 0-1)** | Implicit engagement tracking + thumbs up/down + issue reporting — closes the education quality loop |

**Explicitly Deferred from MVP:**

| Feature | Reason | Target Phase |
|---|---|---|
| Pattern Detection Agent | Not required to validate core education hypothesis | Phase 1.5 |
| Triage Agent (severity ranking) | Enhances but not essential for first upload value | Phase 1.5 |
| Subscription Detection | Depends on Pattern Detection Agent | Phase 1.5 |
| Feedback Layer 2 (reason chips on thumbs-down) | Enhances quality signal but not essential for initial data collection | Phase 1.5 |
| Email Notifications | Not critical for initial validation; users can return manually | Phase 1.5 |
| Freemium Payment Integration | Validate value before monetizing; manual upgrade initially if needed | Phase 2 |

### Post-MVP Features

**Phase 1.5: Pipeline Completion (1-2 months post-launch)**
- Pattern Detection Agent (trends, anomalies, recurring charges, month-over-month)
- Triage Agent (severity-ranked prioritization by financial impact)
- Subscription Detection (dependent on Pattern Detection)
- Email Notifications (upload reminders, new insights available)
- Triage severity colors on Teaching Feed cards (red/yellow/green)
- Feedback Layer 2: contextual follow-up on thumbs-down (4 preset reason chips), occasional thumbs-up follow-up (1 in 10)

**Phase 2: Growth (3-6 months post-launch)**
- Feedback Layer 3: milestone feedback cards (3rd upload, Health Score change, quarterly NPS)
- Developer feedback dashboard (aggregate quality signals per topic cluster)
- RAG corpus auto-flagging based on aggregated thumbs-down rates (>30% threshold, minimum 10 votes)
- Freemium payment integration (Fondy for UA, LemonSqueezy for international)
- Basic predictive forecasts
- Pre-built data queries
- Supplementary dashboard with charts
- Natural language chat interface
- User correction feedback loop for categorization
- Monthly "mise en place" prep briefing

**Phase 3: Expansion (6-12 months post-launch)**
- Savings strategies and passive income education
- Receipt scanning
- Family mode
- Gamification
- Bank API integration (Monobank, PrivatBank partnerships)
- Eastern European expansion
- Mobile native app

### Risk Mitigation Strategy

**Technical Risks:**

| Risk | Impact | Probability | Mitigation |
|---|---|---|---|
| RAG education quality is poor — content feels generic or irrelevant | Critical (core differentiator fails) | Medium | Start with manually curated, high-quality Ukrainian financial literacy corpus (20-30 core concepts). Test retrieval quality before launch. Fallback: hand-written insight templates with data interpolation. |
| LangGraph pipeline too slow (>60s) | High | Low-Medium | 3-agent pipeline is significantly faster than 5-agent. Profile and optimize during development. Async processing with SSE makes perceived wait acceptable. |
| Monobank CSV parsing edge cases | Medium | Medium | Build parser against real Monobank exports. Handle encoding (Windows-1251), semicolons, embedded newlines. Test with multiple months and accounts. |
| BGE-M3 Ukrainian embedding quality insufficient | Medium | Low | Benchmark retrieval quality on Ukrainian financial content early. Fallback: Jina-embeddings-v3 or Qwen3-Embedding as alternatives. |

**Market Risks:**

| Risk | Impact | Mitigation |
|---|---|---|
| Users don't engage with education layers | Critical | Progressive disclosure means education doesn't block core value. Track expansion rates. If <10% expand education, pivot to pure analytics positioning. |
| Users don't return for 2nd upload | High | Focus first-upload experience on delivering immediate, surprising value. "Your finances in 30 seconds" — the aha must happen on upload #1. |
| Trust barrier prevents uploads | High | Trust-first messaging, no bank credentials, encryption transparency, one-click deletion. Test trust signals with early users. |

**Resource Risks:**

| Risk | Impact | Mitigation |
|---|---|---|
| Solo developer hits 2-month mark behind schedule | High | Reduced 3-agent pipeline is the primary mitigation. Further fallback: launch with Ingestion + Categorization only (no Education Agent) — still provides value as a smart categorizer with data persistence. |
| RAG corpus curation takes too long | Medium | Start with 20-30 core financial concepts. Quality over quantity — a small, excellent corpus beats a large mediocre one. |

## Functional Requirements

### Statement Upload & Data Ingestion

- **FR1:** Users can upload bank statement files (CSV, PDF) via drag-and-drop or file picker
- **FR2:** System can auto-detect the bank format of an uploaded statement (Monobank, PrivatBank, other)
- **FR3:** System can parse Monobank CSV files including handling Windows-1251 encoding, semicolon delimiters, and embedded newlines
- **FR4:** System can parse additional bank CSV formats where column structure is recognizable
- **FR5:** System can validate uploaded files before processing (file type, size, format structure) and return actionable error messages
- **FR6:** System can partially process statements where some transactions are unrecognizable, providing value from what it can parse
- **FR7:** Users can upload multiple statements (covering different time periods) to build cumulative history

### AI Processing Pipeline

- **FR8:** System can extract and structure raw transactions from parsed bank statements (Ingestion Agent)
- **FR9:** System can classify transactions into spending categories using AI and MCC codes (Categorization Agent)
- **FR10:** System can generate personalized financial education content based on categorized transaction data using RAG over a financial literacy knowledge base (Education Agent)
- **FR11:** System can generate education content in the user's selected language (Ukrainian or English)
- **FR12:** System can process a typical monthly statement (200-500 transactions) through the full pipeline asynchronously
- **FR13:** Users can view real-time progress of pipeline processing via SSE streaming

### Teaching Feed & Insights

- **FR14:** Users can view a card-based Teaching Feed displaying AI-generated financial insights
- **FR15:** Each insight card displays a headline fact with progressive disclosure education layers (headline → "why this matters" → deep-dive)
- **FR16:** Users can expand and collapse education layers on each insight card
- **FR17:** System can adapt education content depth based on the user's detected financial literacy level
- **FR18:** Users can view insights from current and previous uploads in a unified feed
- **FR19:** Teaching Feed supports cursor-based pagination for browsing insights

### Cumulative Financial Profile

- **FR20:** System can build and maintain a persistent financial profile from all uploaded statements
- **FR21:** System can calculate and display a Financial Health Score (0-100) based on cumulative data
- **FR22:** Users can view how their Financial Health Score changes over time across uploads
- **FR23:** System can detect and display month-over-month spending changes when multiple periods are available
- **FR24:** System can display spending breakdowns by category from cumulative data

### User Management & Authentication

- **FR25:** Users can create an account with email and password
- **FR26:** Users can log in and log out securely
- **FR27:** System can protect all application routes, requiring authentication
- **FR28:** Users can only access their own financial data (tenant isolation)
- **FR29:** Users can select their preferred language (Ukrainian or English)
- **FR30:** Users can view and manage their account settings

### Data Privacy & Trust

- **FR31:** Users can delete all their data with a single action (account, transactions, embeddings, profile, Financial Health Score)
- **FR32:** System can display a clear data privacy explanation during onboarding
- **FR33:** System can obtain explicit user consent for AI processing of financial data at signup
- **FR34:** System can encrypt all stored financial data at rest
- **FR35:** Users can view what data the system has stored about them
- **FR36:** System can display a financial advice disclaimer ("insights and education, not financial advice")

### Error Handling & Recovery

- **FR37:** System can detect unrecognized file formats and suggest corrective actions to the user
- **FR38:** System can flag uncategorized transactions and display them separately for user awareness
- **FR39:** System can recover gracefully from pipeline processing failures without data loss
- **FR40:** System can display user-friendly error messages (not technical errors) for all failure scenarios

### User Feedback — Layers 0-1 (MVP)

- **FR45:** System can track implicit card interaction signals per Teaching Feed card: time_on_card_ms, education_expanded, education_depth_reached, swipe_direction, card_position_in_feed
- **FR46:** System can aggregate implicit signals into a per-card engagement score (0-100) using a weighted formula
- **FR47:** Users can rate any Teaching Feed card with thumbs up or thumbs down; vote state persists and is visible when returning to the card
- **FR48:** Users can report an issue on any Teaching Feed card via an in-context mechanism (flag icon in card overflow menu) with category selection (Bug, Incorrect info, Confusing, Other) and optional free-text field
- **FR49:** Feedback data (votes, reports, free-text) is included in the user's data export (FR35) and one-click deletion (FR31)

### User Feedback — Layer 2 (Phase 1.5)

- **FR50:** On thumbs-down, system presents a compact slide-up panel with 4 preset reason chips: "Not relevant to me", "Already knew this", "Seems incorrect", "Hard to understand" — dismissible, one-tap selection
- **FR51:** On thumbs-up, system presents an optional follow-up (triggered 1 in 10 occurrences) with preset chips: "Learned something", "Actionable", "Well explained"

### User Feedback — Layer 3 (Phase 2)

- **FR52:** System can display milestone feedback cards at the end of the Teaching Feed: after 3rd upload (one-time), after significant Financial Health Score change (+/- 5 points)
- **FR53:** Milestone feedback cards use the same card component and gestures as education cards — swipeable, skippable, no new UI pattern
- **FR54:** System can enforce feedback card frequency caps: max 1 feedback card per session, max 1 per month, milestone cards never repeat once dismissed
- **FR55:** System can auto-flag RAG topic clusters with >30% thumbs-down rate when a minimum of 10 votes has been reached on the cluster

### Operational Monitoring (MVP)

- **FR41:** System can produce structured logs with correlation IDs (job_id, user_id) across all pipeline agents
- **FR42:** System can track and log pipeline processing times per agent
- **FR43:** System can track and log upload success/failure rates and error types
- **FR44:** Operator can query job status and pipeline health via database queries

## Non-Functional Requirements

### Performance

| Metric | Target | Context |
|---|---|---|
| Page load (authenticated) | < 3 seconds on 3G | Mobile-first Ukrainian users, variable network quality |
| Teaching Feed card render | < 500ms after data fetch | Perceived responsiveness of primary UI |
| Financial Health Score calculation | < 2 seconds | User-facing metric displayed on profile |
| Full pipeline processing (3 agents) | < 60 seconds for 200-500 transactions | Async with SSE progress — perceived wait is acceptable |
| API response (REST/GraphQL) | < 500ms for read operations | Standard web app responsiveness |
| File upload acknowledgment | < 2 seconds (HTTP 202 returned) | User must know upload was received before async processing begins |
| Concurrent users | Support 100 concurrent users at MVP | Sufficient for initial launch and early validation |

### Security

All security requirements from the Domain-Specific Requirements section (encryption, authentication, AI security, fraud prevention) apply as NFRs. The following specify measurable targets:

- **Authentication token expiry:** JWT access tokens < 15 minutes, with refresh token rotation
- **Session timeout:** Automatic expiry after 30 minutes of inactivity
- **Rate limiting:** Max 10 login attempts per IP per 15 minutes; max 20 file uploads per user per hour
- **Input validation:** All uploaded file content treated as untrusted; sanitized before AI pipeline processing
- **Dependency security:** Automated vulnerability scanning for Python and Node.js dependencies

### Scalability

| Dimension | MVP Target | Growth Target |
|---|---|---|
| Registered users | 500 | 10,000 |
| Concurrent uploads being processed | 5 | 50 |
| Transactions stored per user | 10,000 (~ 2 years) | 50,000 (~ 10 years) |
| RAG knowledge base documents | 50-100 | 500+ |
| Vector embeddings (pgvector) | 50,000 | 500,000 |

- System must support 10x user growth with < 20% performance degradation by adding horizontal resources (Celery workers, read replicas)
- PostgreSQL + pgvector performance is sufficient up to ~1M vectors; migration path to Qdrant documented in research for beyond that threshold
- Celery workers can be scaled independently of API servers

### Accessibility

- **WCAG 2.1 AA** compliance baseline for all UI components
- Keyboard navigable: all interactive elements reachable and operable via keyboard
- Screen reader compatible: semantic HTML, ARIA labels for triage severity indicators and progressive disclosure controls
- Color independence: triage severity (red/yellow/green) conveyed through icons and text labels, not color alone
- Minimum color contrast: 4.5:1 for normal text, 3:1 for large text (AA standard)
- Focus indicators: visible focus rings on all interactive elements
- Responsive text: support browser zoom up to 200% without horizontal scrolling

### Integration

| Integration | Protocol | Reliability Requirement |
|---|---|---|
| Monobank CSV import | File upload (CSV parsing) | Graceful degradation on format changes; partial parsing supported |
| Monobank API (future Phase 2+) | REST + webhook | Not in MVP scope; architecture should not preclude future integration |
| Fondy payments (Phase 2) | Webhook | Idempotent processing; 3-retry tolerance before flagging |
| LemonSqueezy payments (Phase 2) | Webhook | Same as Fondy |
| LLM API (Claude/GPT) | REST API | Retry with exponential backoff; circuit breaker after 3 consecutive failures; graceful error to user |
| BGE-M3 embedding model | Local inference or API | Self-hosted preferred for cost and latency; fallback to API-based embedding |

### Reliability

- **Uptime:** 99.5% availability for core functionality (upload, Teaching Feed, authentication)
- **Data durability:** Zero data loss for uploaded financial data — PostgreSQL WAL + regular backups
- **Pipeline recovery:** Failed pipeline jobs can be retried without re-upload; checkpoint state preserved per agent
- **Graceful degradation:** If Education Agent (RAG) fails, display categorized data without education layers rather than showing nothing
- **Backup frequency:** Daily automated database backups with 30-day retention
