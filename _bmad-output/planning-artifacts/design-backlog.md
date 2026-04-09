# Design Backlog — Post-MVP

**Created:** 2026-04-08
**Owner:** Oleh
**Status:** Parked — revisit after MVP

---

## DS-1: 'Other' Category Smart Handling

**Source:** Epic 3 Retro (2026-04-07), Action Item #5

**Problem:** Low-confidence / unrecognized transactions land in `category='other'`. Insight cards for 'other' are low-value but suppressing them completely risks discarding significant spending data.

**Agreed direction (from retro):**
- 'Other' < threshold of total spend → filter silently (no card generated)
- 'Other' >= threshold → second LLM re-categorization pass → user clarification for what remains

**Design questions to explore:**
- What threshold feels right? (needs real-data validation)
- How does the user clarification UX work without adding friction?
- How do clarified categories feed back into future categorization accuracy?
- Impact on all three personas (Anya, Viktor, Dmytro)

---

## DS-2: Locale Switching & Insight Regeneration

**Source:** Epic 3 Retro (2026-04-07), Action Item #6

**Problem:** Insight cards are generated in the user's locale at pipeline time and persisted. Changing language in Settings does not regenerate cards — they stay in the original language.

**Options identified (from retro):**
1. **Dual-language generation** — generate both EN/UK at pipeline time, serve the active one
2. **Lazy regeneration** — regenerate cards on-demand when language is switched
3. **Next-upload regeneration** — cards stay in original language until next upload triggers new pipeline run

**Design questions to explore:**
- Which option best balances UX quality vs. compute cost?
- How often do users actually switch languages?
- Should new cards vs. existing cards be handled differently?
- Impact on cumulative profile and card history

---

## DS-3: AI Quality Control & Observability

**Source:** Epic 3 Retro discussion (2026-04-08), related to DS-1 ('other' category as a symptom)

**Problem:** There is currently no quality control over the AI components of the application. No tests or validation for RAG corpus content, no prompt evaluation, no metrics tracking LLM output quality. The 'other' category issue (DS-1) is partly a symptom of this — there's no way to measure or catch categorization quality degradation, prompt drift, or RAG retrieval relevance.

**Areas to explore:**
- **Prompt evaluation** — automated checks for categorization accuracy, insight quality, key metric conciseness (retro flagged overly dense key metrics)
- **RAG corpus validation** — coverage checks, embedding quality, retrieval relevance scoring
- **Pipeline output metrics** — categorization confidence distribution, 'other' category rate, insight card quality signals
- **Regression detection** — baseline quality benchmarks so model/prompt changes can be validated
- **Production observability** — logging/dashboards for LLM call latency, token usage, error rates, output quality proxies

**Design questions to explore:**
- What's the minimum viable quality gate for MVP vs. post-MVP?
- Which metrics are most actionable early on?
- How do we build evaluation datasets from real user data (Monobank uploads)?
- Should quality checks run in CI, at pipeline runtime, or both?

---

_Items to be picked up via a design thinking session when MVP is complete._
