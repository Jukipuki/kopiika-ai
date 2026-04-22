# Story 9.1: RAG Evaluation Harness

Status: done
Created: 2026-04-22
Epic: 9 — AI Infra Readiness (Bedrock Provider, RAG Eval Harness, Embedding Decision)

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **developer**,
I want a repeatable offline evaluation harness that measures RAG retrieval quality and answer quality across UA + EN corpus topics,
so that any future change to embeddings, retriever, or Education Agent prompt can be gated against an objective baseline before merge (embedding-model decision in Story 9.3, migration in Story 9.6).

## Acceptance Criteria

1. **Given** a labelled eval set of representative financial-literacy questions paired to ground-truth corpus docs **When** the fixture is authored **Then** `backend/tests/fixtures/rag_eval/eval_set.jsonl` contains at least 40 questions covering every core topic in `backend/data/rag-corpus/{en,uk}/` (minimum 1 EN + 1 UA question per topic slug; `budgeting-basics`, `emergency-fund`, `debt-management`, `savings-strategies`, `subscription-tracking`, `spending-categories`, `investment-basics`, `50-30-20-rule`, `groceries-food-spending`, `transport-spending`, `utilities-bills`, `healthcare-spending`, `entertainment-spending`, `shopping-habits`, `understanding-inflation`, `interest-and-credit`, `financial-goals`, `cash-vs-digital-payments`, `spending-patterns`, `financial-literacy-levels`) plus at least 1 EN + 1 UA question for each supplemental topic (`hryvnia-basics`, `ukrainian-tax-basics`, `monobank-ecosystem`). Each row has: `id`, `language` (`en`|`uk`), `question`, `expected_doc_ids` (list of `{language}/{slug}` strings — at least one gold doc), `topic` (slug), `question_type` (`factual`|`applied`|`definitional`), `notes`

2. **Given** the harness is invoked **When** it runs against the live `document_embeddings` pgvector table seeded from `backend/app/rag/seed.py` **Then** it computes, for each eval question, retrieval metrics from `retrieve_relevant_docs(query=question, language=question.language, top_k=5)`: `precision@1`, `precision@3`, `precision@5`, `recall@5`, and `mrr` (mean reciprocal rank) — with a hit defined as `retrieved.doc_id ∈ expected_doc_ids`

3. **Given** the retrieval pass produces top-k chunks **When** the answer-quality pass runs **Then** for each question the harness (a) builds a bilingual-aware prompt using the same retrieval concatenation pattern as `app/agents/education/node.py` and calls the LLM via `app.agents.llm.get_llm_client()` to generate a candidate answer, (b) invokes an LLM-as-judge (separate call via `get_llm_client()` with a scoring rubric prompt) that returns a structured JSON score `{groundedness: 0-2, relevance: 0-2, language_correctness: 0-2, overall: 0-4, rationale: str}`, and (c) aggregates judge scores per question

4. **Given** the full harness run completes **When** the report is written **Then** `backend/tests/fixtures/rag_eval/runs/<timestamp>.json` is produced containing: overall aggregates (retrieval metrics + mean judge scores + token counts), per-language breakdown (en vs uk), per-topic breakdown (one row per corpus topic slug showing retrieval metrics + answer score), per-question_type breakdown, and a list of the worst 10 cases (lowest judge `overall` score, with retrieved doc_ids, expected doc_ids, candidate answer, judge rationale)

5. **Given** the harness is the authoritative gate for embedding/prompt changes **When** it runs in CI **Then** a cheap schema-validation test runs on every `pytest` sweep (validates the fixture JSONL shape + topic coverage, no LLM, no DB) AND the full harness is gated behind `@pytest.mark.integration` + `@pytest.mark.eval` so it does NOT run by default — invoked explicitly via `uv run pytest tests/eval/rag/ -v -m eval` locally and as a dedicated manually-triggered CI job (`workflow_dispatch` + optional nightly schedule) in a new `.github/workflows/ci-backend-eval.yml`

6. **Given** Story 9.1 is delivered **When** Story 9.2 (baseline) runs the harness against the current `text-embedding-3-small` corpus **Then** the run report from Story 9.2 is saved as the reference artifact that Stories 9.3 and 9.6 are measured against — Story 9.1 only installs the harness; it does NOT assert absolute pass/fail thresholds on retrieval or judge scores (no `assert precision_at_5 >= X`), it only asserts the run completed and wrote a structurally-valid report

7. **Given** `pgvector` is required for the eval run **When** the harness starts **Then** it auto-skips with a clear message if `document_embeddings` is empty (no rows) or if the DB is unreachable — so a developer who has not seeded the corpus can still run the rest of the suite without a cryptic failure

## Tasks / Subtasks

- [x] Task 1: Author eval fixture (AC: #1)
  - [x] 1.1 Create directory `backend/tests/fixtures/rag_eval/` and `backend/tests/fixtures/rag_eval/runs/` (with `.gitkeep`). Add `backend/tests/fixtures/rag_eval/runs/*.json` to `.gitignore` (mirrors the Story 11.1 categorization golden-set pattern).
  - [x] 1.2 Create `backend/tests/fixtures/rag_eval/README.md` documenting authoring methodology: how questions were chosen (1 EN + 1 UA per topic for core 20 + supplemental 3), topic/slug mapping, redaction policy (questions are synthetic — no real user data), expansion policy, and how `expected_doc_ids` are chosen (read the corpus `.md` file; select the canonical doc for the topic; multi-doc if a question spans topics).
  - [x] 1.3 Author `eval_set.jsonl` with ≥ 40 questions. Walk every core + supplemental topic in `backend/data/rag-corpus/{en,uk}/` and produce at least one question per (topic, language) pair. Split question types roughly 40% factual ("What is the 50/30/20 rule?"), 35% applied ("If I spend 40% of my income on rent, what should I adjust?"), 25% definitional ("Define emergency fund in 1 sentence"). `id` values follow pattern `rag-NNN`.
  - [x] 1.4 For each question, set `expected_doc_ids` to the `{language}/{slug}` of the canonical corpus doc covering the topic (e.g., `en/budgeting-basics`, `uk/emergency-fund`). Include a secondary doc when the question clearly spans two topics.
  - [x] 1.5 Use the JSONL convention `one JSON object per line` (strict JSONL — unlike the categorization golden set, there is no reason for pretty-print here). Validate with `python -c "import json; [json.loads(l) for l in open('eval_set.jsonl')]"`.

- [x] Task 2: Fixture schema + coverage assertions (AC: #1, #5 — cheap gate)
  - [x] 2.1 Create `backend/tests/eval/__init__.py` and `backend/tests/eval/rag/__init__.py` (empty, for pytest discovery).
  - [x] 2.2 Create `backend/tests/eval/rag/test_eval_fixture.py` with two non-LLM, non-DB tests that run on the default `pytest` sweep:
    - `test_eval_set_schema()` — iterate every row, assert all 7 required fields present + correct types (lists for `expected_doc_ids`, `language ∈ {"en","uk"}`, `question_type ∈ {"factual","applied","definitional"}`).
    - `test_topic_coverage()` — verify every core + supplemental topic slug has ≥ 1 EN question AND ≥ 1 UA question. Build the expected topic set by `glob("backend/data/rag-corpus/en/*.md")` — if the corpus grows, the test auto-checks the new topic.
  - [x] 2.3 These tests MUST NOT be marked `integration` or `eval` — they run every push and catch fixture regressions.

- [x] Task 3: Build the retrieval-metrics module (AC: #2)
  - [x] 3.1 Create `backend/tests/eval/rag/metrics.py` — pure functions, no deps:
    - `precision_at_k(retrieved_ids: list[str], expected_ids: list[str], k: int) -> float`
    - `recall_at_k(retrieved_ids, expected_ids, k) -> float`
    - `reciprocal_rank(retrieved_ids, expected_ids) -> float` (first hit position; 0 if no hit)
  - [x] 3.2 Unit-test these in `backend/tests/eval/rag/test_metrics.py` with hand-rolled cases (runs on default sweep — no LLM, no DB).

- [x] Task 4: Build the LLM-as-judge module (AC: #3)
  - [x] 4.1 Create `backend/tests/eval/rag/judge.py`:
    - `build_candidate_answer(question, retrieved_chunks, language) -> tuple[str, int]` returning `(answer, tokens_used)`. Reuse the Education-Agent prompt pattern from `backend/app/agents/education/prompts.py` — concat retrieved chunk `content` under a `RAG Context:` header, instruct the model to answer ONLY from the context, in the target language.
    - `judge_answer(question, candidate_answer, expected_doc_content, language) -> tuple[dict, int]` returning `(score_dict, tokens_used)`. Prompt the LLM to output strict JSON matching schema `{"groundedness": 0|1|2, "relevance": 0|1|2, "language_correctness": 0|1|2, "overall": 0-4, "rationale": str}`. Include the rubric inline. Parse with `json.loads`; on parse failure return `{"overall": 0, "rationale": "parse-error", ...}` and log.
  - [x] 4.2 Use `app.agents.llm.get_llm_client()` for BOTH candidate generation and judge — per AgentCore decision (memory: project_agentcore_decision.md) this remains on Anthropic Claude Haiku primary / GPT-4o-mini fallback. Story 9.5b will later add Bedrock; the harness automatically picks up whatever `llm.py` returns, so no per-provider branching is needed here.
  - [x] 4.3 Track total tokens by summing `response.usage_metadata` from each langchain call. Surface in the run report (operator needs to know the cost per harness run — relevant for CI budget).

- [x] Task 5: Build the harness orchestrator (AC: #2, #3, #4, #7)
  - [x] 5.1 Create `backend/tests/eval/rag/test_rag_harness.py` (pytest entry point).
  - [x] 5.2 Mark it `@pytest.mark.integration` AND `@pytest.mark.eval` (define `eval` marker in `backend/pyproject.toml` markers list). The default `pytest` sweep (`addopts = "-m 'not integration'"`) will skip it.
  - [x] 5.3 Auto-skip logic: at test start, open a sync session (`app.core.database.get_sync_session`) and `SELECT COUNT(*) FROM document_embeddings`. If it raises (DB unreachable) or returns 0, `pytest.skip("RAG corpus not seeded — run `python -m app.rag.seed` first")`. AC #7.
  - [x] 5.4 Load `eval_set.jsonl` via `_load_eval_set` helper (pathlib-relative to `__file__`, not absolute).
  - [x] 5.5 For each question: call `retrieve_relevant_docs(question, language, top_k=5)` (from `app.rag.retriever`), extract `retrieved.doc_id` list, compute retrieval metrics, generate candidate answer (`judge.build_candidate_answer`), load expected doc content from corpus file(s), invoke judge (`judge.judge_answer`), accumulate scores + tokens.
  - [x] 5.6 Aggregate: overall means, per-language (en vs uk), per-topic (group by `row.topic`), per-question_type. Build `worst_10` by sorting by judge `overall` ascending.
  - [x] 5.7 Write report to `runs/<timestamp>.json` using `%Y%m%dT%H%M%S%fZ` microsecond precision (mirrors 11.1 — avoids filename collisions in back-to-back runs). Use `Path(__file__).parent.parent.parent / "fixtures/rag_eval/runs"`. `mkdir(parents=True, exist_ok=True)`.
  - [x] 5.8 Assert ONLY that: (a) the report file exists, (b) it contains all expected aggregate keys, (c) every eval question produced a retrieval result (even if empty), (d) every question produced a judge score (even if `overall=0` on parse error). No absolute-threshold assertions — Story 9.2 captures the baseline (AC #6).

- [x] Task 6: CI wiring (AC: #5)
  - [x] 6.1 Create `.github/workflows/ci-backend-eval.yml`. Triggers: `workflow_dispatch` (manual) + `schedule: cron: '0 5 * * *'` (nightly 05:00 UTC — run out of business hours; comment the cron in if cost-prohibitive, leaving manual-only as default). Mirrors `ci-backend.yml` setup (uv, Python 3.12, install).
  - [x] 6.2 The eval job needs: `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, a Postgres+pgvector service (reuse the pattern from `ci-backend.yml` if it already provisions one; else add `services: postgres: image: pgvector/pgvector:pg16`), and a seed step `uv run python -m app.rag.seed` before the eval step.
  - [x] 6.3 Eval step: `uv run pytest backend/tests/eval/rag/ -v -m eval`. Upload `backend/tests/fixtures/rag_eval/runs/*.json` as a workflow artifact (retention 90 days) so historical runs are diff-able from the GitHub UI.
  - [x] 6.4 Confirm the default `ci-backend.yml` (`uv run pytest tests/ -v`) still picks up the fixture-schema + metrics unit tests from Task 2 + Task 3.2 (they are not `integration`/`eval` marked) and that the full harness stays excluded.

- [x] Task 7: Documentation + developer ergonomics (AC: #5)
  - [x] 7.1 Add a `make eval-rag` target to `backend/Makefile` (or `docs/developer-guide.md` if Makefile absent) that runs `uv run pytest tests/eval/rag/ -v -m eval -s`.
  - [x] 7.2 Update `backend/tests/fixtures/rag_eval/README.md` (already created in 1.2) with: how to run locally, how to interpret a run report, how to add a new topic question, and an explicit pointer to `app.rag.retriever.retrieve_relevant_docs` (the unit-under-test) and `app.agents.llm.get_llm_client` (the judge invocation path).
  - [x] 7.3 Add a short section to the root `README.md` or `docs/testing.md` under "Evaluation harnesses" that cross-links to both Story 11.1 categorization harness and this Story 9.1 RAG harness — two different harnesses, two different CI strategies, same "fixture + runs/ + gitignored reports" template.

## Dev Notes

### Relationship to surrounding stories

Story 9.1 builds the **instrument**; it does not capture a baseline and does not pick a winner.

- **Story 9.2** = run this harness once on production corpus with current `text-embedding-3-small`, commit the run report as the baseline, and record the numbers in the 9.2 story file.
- **Story 9.3** = re-run this harness against alternative embedding models (`text-embedding-3-large`, Titan V2, Cohere `embed-multilingual-v3`); produce a recommendation based on *this harness's* per-topic and per-language breakdown.
- **Story 9.6** = if 9.3 picks a non-current winner, the migration PR re-runs this harness post-cutover to prove metrics match or beat the 9.2 baseline.

Therefore AC #6 is deliberate: Story 9.1 asserts only that the report was produced, not a specific precision@5 number. Absolute thresholds would be premature (we do not yet know what is achievable) and would tightly couple a brand-new instrument to subjective numbers.

### Mirroring Story 11.1's golden-set harness pattern

This is the project's second evaluation harness. Story 11.1 established the template:
- Fixture directory (`tests/fixtures/<harness>/`) with `eval_set.jsonl` + `runs/` + `README.md`.
- `.gitignore` the run reports; commit the fixture.
- Cheap non-LLM fixture-schema test runs on every sweep; expensive LLM-driven test gated by markers.
- `@pytest.mark.integration` excluded via `pyproject.toml` `addopts = "-m 'not integration'"`.
- Structured JSON run report with timestamp, aggregate metrics, and worst-N failure list.

Re-use every pattern. The only structural delta is that Story 9.1 uses an ADDITIONAL `eval` marker and a SEPARATE CI workflow (not merged into `ci-backend.yml`) because: (a) it needs a seeded pgvector corpus which the default test run does not provision, (b) it is expected to be slow (40+ questions × 2 LLM calls each = ~80 LLM invocations per run), and (c) it is expected to be run on-demand when embedding changes are proposed, not on every PR.

### Key integration points

- `app.rag.retriever.retrieve_relevant_docs(query, language, top_k)` is the unit under retrieval test. It returns a list of dicts with `doc_id`, `language`, `chunk_type`, `content`, `similarity`. The `doc_id` format is `{language}/{slug}` (e.g., `en/budgeting-basics`) — match `expected_doc_ids` exactly against this. See [retriever.py](../../backend/app/rag/retriever.py).
- `app.agents.llm.get_llm_client()` returns a `ChatAnthropic` (Claude Haiku 4.5) and `get_fallback_llm_client()` returns `ChatOpenAI` (GPT-4o-mini). Both are `langchain` clients — invoke with `.invoke([HumanMessage(content=prompt)])`. Use `response.usage_metadata.input_tokens + output_tokens` to track cost. See [llm.py](../../backend/app/agents/llm.py).
- `app.rag.seed.py` is the corpus seeding CLI: `python -m app.rag.seed` reads every `backend/data/rag-corpus/{en,uk}/*.md` file, chunks by `## ` H2 headers, embeds with `text-embedding-3-small`, upserts into `document_embeddings` keyed on `(doc_id, chunk_type)`. Idempotent.
- The corpus already has 23 topic files per language (20 core + 3 supplemental) — see `ls backend/data/rag-corpus/{en,uk}/`.
- `FinancialPipelineState` is NOT used here — the harness hits the retriever and LLM directly; it does not construct a pipeline state. This differs from Story 11.1 which invokes the full `categorization_node`.

### Judge prompt scoring rubric (for `judge.py`)

Rubric (inline in the judge prompt):
- `groundedness` — 0 = answer contains claims not in the retrieved context; 1 = partially grounded; 2 = fully grounded.
- `relevance` — 0 = off-topic; 1 = partially addresses the question; 2 = directly answers.
- `language_correctness` — 0 = wrong language or machine-translated artifacts; 1 = right language, awkward phrasing; 2 = natural target-language answer.
- `overall` — integer `0..4` (judge's summary holistic score; can differ from sum of axes if judge decides one axis dominates — the rubric asks for judgment, not arithmetic).
- `rationale` — one-sentence reason; stored for the worst-10 table.

**Critical**: instruct the judge to return ONLY strict JSON, no markdown fences, no prose preamble. The Education Agent already hits this exact failure mode (see Story 3.3 code-review notes) — reuse the "respond with JSON only" phrasing.

### Fixture ethics / PII

Questions are **synthetic** — authored by the developer, not taken from production. The corpus is public financial-literacy content; the questions reference it. No user data, no transactions, no amounts from real statements. This is unlike Story 11.1's golden set which is redacted real Monobank data. Document the synthetic-only policy in `README.md` (Task 1.2) so future authors do not paste real user questions in.

### Memory / policy references

- The project memory `project_agentcore_decision.md` states Bedrock/AgentCore is not in use for batch agents yet — so the harness stays on the current Anthropic+OpenAI stack. Story 9.5b adds Bedrock routing; the harness is provider-agnostic via `llm.py`, so it picks up Bedrock automatically when 9.5b lands — no change needed here.
- The project memory `project_observability_substrate.md` confirms there is no Grafana in scope; run reports are local JSON artifacts + CI workflow artifacts. Do not wire metric emission to CloudWatch in this story (out of scope).
- Tech-debt register (memory `reference_tech_debt.md`) at `docs/tech-debt.md` — if any harness shortcut is taken (e.g., skipping a topic, using a smaller eval set), register it with a `TD-NNN` ID and cross-link from this story's Completion Notes. None expected, but the option exists.

### Project Structure Notes

- New directory: `backend/tests/eval/` (evaluation harnesses — this is the first one under this root; the categorization harness lives under `tests/agents/categorization/`, a pre-existing pattern. Putting RAG eval under `tests/eval/rag/` opens the door for future harnesses like `tests/eval/insights/` — see Story 12.1 which is a separate LLM-output eval).
- New directory: `backend/tests/fixtures/rag_eval/` + `runs/` (gitignored reports).
- New file: `.github/workflows/ci-backend-eval.yml` — separate from `ci-backend.yml`.
- New marker: `eval` in `backend/pyproject.toml` markers list (does NOT need to be excluded from default sweep because `integration` exclusion already catches it; adding it as a secondary marker purely for clarity and for "run ONLY eval" selectivity).
- Existing `backend/tests/agents/categorization/test_golden_set.py` (Story 11.1) is the reference for harness shape — do not modify it; only copy the pattern.

### Testing Standards

Follow the established project test conventions:
- `pytest` with markers for selective runs.
- Synchronous SQLAlchemy sessions (`get_sync_session`) — the retriever runs in Celery worker context which is sync; the harness mirrors that.
- No mocking of retriever or LLM inside the harness itself — real calls, real DB. The cheap fixture/metrics tests (Task 2, 3.2) need neither.
- Bilingual test cases: every test in `test_eval_fixture.py` that asserts coverage must handle BOTH languages — see Task 2.2's `test_topic_coverage`.

### References

- Epic 9 goal & stories: [epics.md#Epic 9](../_bmad-output/planning-artifacts/epics.md) lines 2021–2078
- Architecture — RAG decision rationale: [architecture.md#Architectural-Decisions](../_bmad-output/planning-artifacts/architecture.md) lines 69–101
- Architecture — pgvector + embeddings model: [architecture.md#Primary-Database](../_bmad-output/planning-artifacts/architecture.md) line 288, 294
- Architecture — RAG pipeline & file structure: [architecture.md#File-Structure](../_bmad-output/planning-artifacts/architecture.md) lines 718–720, 1189–1196
- RAG retriever under test: [backend/app/rag/retriever.py](../../backend/app/rag/retriever.py)
- RAG embeddings wrapper: [backend/app/rag/embeddings.py](../../backend/app/rag/embeddings.py)
- RAG corpus seeder: [backend/app/rag/seed.py](../../backend/app/rag/seed.py)
- RAG corpus: [backend/data/rag-corpus/](../../backend/data/rag-corpus/)
- Education Agent node (candidate-answer prompt reference): [backend/app/agents/education/node.py](../../backend/app/agents/education/node.py)
- LLM client factory: [backend/app/agents/llm.py](../../backend/app/agents/llm.py)
- Golden-set harness precedent: [backend/tests/agents/categorization/test_golden_set.py](../../backend/tests/agents/categorization/test_golden_set.py)
- Golden-set fixture pattern: [backend/tests/fixtures/categorization_golden_set/README.md](../../backend/tests/fixtures/categorization_golden_set/README.md)
- Story 11.1 (golden-set harness) story file: [11-1-golden-set-evaluation-harness-for-categorization.md](./11-1-golden-set-evaluation-harness-for-categorization.md)
- Story 3.3 (RAG KB & Education Agent): [3-3-rag-knowledge-base-education-agent.md](./3-3-rag-knowledge-base-education-agent.md)
- Existing backend CI: [.github/workflows/ci-backend.yml](../../.github/workflows/ci-backend.yml)

## Dev Agent Record

### Agent Model Used

claude-opus-4-7 (1M context)

### Debug Log References

- Default sweep (`uv run pytest tests/ -q`): **861 passed, 10 deselected** — no regressions. New cheap tests (`tests/eval/rag/test_eval_fixture.py`, `tests/eval/rag/test_metrics.py`) run on the default sweep; the expensive harness (`test_rag_harness.py`) is correctly excluded via the `integration` marker.
- `uv run ruff check tests/eval/` — clean.

### Completion Notes List

- Instrument-only delivery, per AC #6: harness asserts structural validity of the run report and that every question produced retrieval + judge records. No absolute retrieval or judge thresholds are asserted — Story 9.2 will capture the baseline.
- Eval fixture has **46 rows** (≥40 required): 23 EN + 23 UA, one question per (topic, language) pair covering every core and supplemental corpus topic. Question-type mix ≈ 39% factual / 35% applied / 26% definitional.
- Cheap, non-LLM, non-DB tests gate every default sweep: schema shape, topic coverage (globbed from the corpus directory so new corpus topics auto-break the test), and a reference-integrity check that every `expected_doc_ids` entry resolves to a real `backend/data/rag-corpus/{lang}/{slug}.md` file.
- Harness uses the same `app.agents.llm.get_llm_client()` path as the Education Agent, so Story 9.5b's future Bedrock routing is picked up automatically — no per-provider branching here (per memory `project_agentcore_decision.md`).
- Judge returns strict JSON; parse failures degrade gracefully to a zeroed score with a `parse-error: ...` rationale so the run report stays structurally valid even if the judge misbehaves.
- Auto-skip via `SELECT COUNT(*) FROM document_embeddings` — protects developers who run `pytest -m eval` without seeding the corpus (AC #7).
- Run reports live under `backend/tests/fixtures/rag_eval/runs/<timestamp>.json` and are gitignored (mirrors Story 11.1 pattern). CI uploads them as artifacts with 90-day retention.
- Nightly cron in `ci-backend-eval.yml` is commented out by default (manual `workflow_dispatch` only) — enable when team budgets for recurring cost. Decision trade-off called out in the workflow file.
- No tech-debt entries needed for this story (no shortcuts taken).

### Code Review (2026-04-22)

Adversarial senior-dev review; all HIGH + MEDIUM findings fixed in-line.

- **[HIGH] H1 — Judge groundedness axis was scored against the gold reference, not the retrieved context.** Hallucinated answers that happened to match gold could score 2 while faithful answers over imperfect retrievals scored 0, baking retrieval accuracy into the wrong axis. Fixed: `judge_answer` now takes `retrieved_chunks` and scores `groundedness` against the retrieved context; `relevance` remains scored against the gold reference. Rubric in `_JUDGE_PROMPT` rewritten to make the split explicit. Files: `backend/tests/eval/rag/judge.py`, `backend/tests/eval/rag/test_rag_harness.py`.
- **[HIGH] H2 — `precision@k` divided by `len(retrieved[:k])` instead of `k`,** inflating the metric when the retriever returned fewer than `k` rows (the cross-lingual fallback doesn't always fill top-5). Fixed: denominator is now `k` per standard IR convention; the misleading unit test was rewritten to lock in `0.2`, not `0.5`. Files: `backend/tests/eval/rag/metrics.py`, `backend/tests/eval/rag/test_metrics.py`.
- **[MEDIUM] M3 — Judge prompt's schema example was literal zeros,** priming the model to mimic. Replaced with `<int 0-2>` / `<one sentence>` placeholders. File: `backend/tests/eval/rag/judge.py`.
- **[MEDIUM] M4 — Entire corpus doc was passed as gold content to the judge, untruncated.** Capped at 6000 chars per row via `_EXPECTED_CONTENT_MAX_CHARS` with a shared budget across multi-doc questions. File: `backend/tests/eval/rag/test_rag_harness.py`.
- **[MEDIUM] M5 — Per-row `except Exception` silently converted LLM failures to zeroed scores,** letting a fully-broken run pass AC #6's structural assertions. Added `error_rows` counter (covers both `llm-error:` and `parse-error:` rationales) and a `_MAX_ERROR_FRACTION = 0.2` assertion; `error_rows` is also recorded in the report. File: `backend/tests/eval/rag/test_rag_harness.py`.
- **[MEDIUM] M6 — Dead `SYNC_DATABASE_URL` env var in the CI workflow.** `Settings.SYNC_DATABASE_URL` is a computed `@property`; env override has no effect. Removed. File: `.github/workflows/ci-backend-eval.yml`.
- **[MEDIUM] M7 — CI `DATABASE_URL` used `postgresql+psycopg://`,** which `Settings.SYNC_DATABASE_URL` doesn't transform, so CI diverged from local dev. Changed to `postgresql+asyncpg://` so the derivation path is exercised. File: `.github/workflows/ci-backend-eval.yml`.
- **[LOW] L8 — Run report written without explicit `encoding="utf-8"`.** Risk of mojibake on non-UTF locales with Cyrillic content. Added `encoding="utf-8"`. File: `backend/tests/eval/rag/test_rag_harness.py`.
- **[LOW] L9 — `docs/testing.md` claimed the categorization harness is run by `ci-backend.yml`,** but the default sweep excludes the `integration` marker. Corrected the row. File: `docs/testing.md`.

Post-fix: default sweep `861 passed, 10 deselected` (no regressions); `ruff check tests/eval/` clean.

### File List

- backend/tests/fixtures/rag_eval/README.md
- backend/tests/fixtures/rag_eval/eval_set.jsonl
- backend/tests/fixtures/rag_eval/runs/.gitkeep
- backend/tests/eval/__init__.py
- backend/tests/eval/rag/__init__.py
- backend/tests/eval/rag/metrics.py
- backend/tests/eval/rag/judge.py
- backend/tests/eval/rag/test_eval_fixture.py
- backend/tests/eval/rag/test_metrics.py
- backend/tests/eval/rag/test_rag_harness.py
- backend/pyproject.toml (added `eval` pytest marker)
- backend/Makefile (new; `eval-rag` + `eval-categorization` targets)
- .github/workflows/ci-backend-eval.yml
- .gitignore (added `backend/tests/fixtures/rag_eval/runs/*.json`)
- docs/testing.md (new; cross-links both harnesses)
- VERSION (1.30.0 → 1.31.0)
- _bmad-output/implementation-artifacts/sprint-status.yaml (ready-for-dev → review)

## Change Log

- 2026-04-22 — Story 9.1 implemented: RAG evaluation harness (46-question bilingual fixture, retrieval metrics, LLM-as-judge, structured run reports, dedicated CI workflow). Version bumped from 1.30.0 to 1.31.0 per story completion.
- 2026-04-22 — Code review fixes applied: judge rubric split (groundedness vs retrieved context, relevance vs gold), `precision@k` denominator corrected to `k`, judge schema-example de-biased, gold-content truncation, LLM-error budget assertion, CI env cleanup, UTF-8 report write, docs fix. See "Code Review (2026-04-22)" above. Status: review → done.
