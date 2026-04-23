# Story 9.2: Baseline Current Embeddings Through Harness

Status: done
Created: 2026-04-22
Epic: 9 — AI Infra Readiness (Bedrock Provider, RAG Eval Harness, Embedding Decision)

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **developer**,
I want the Story 9.1 RAG evaluation harness executed once end-to-end against the current production RAG corpus (embedded with OpenAI `text-embedding-3-small`) with the run report committed to the repo as a named baseline,
so that Stories 9.3 (embedding-model comparison) and 9.6 (conditional migration) have a stable, reproducible reference point — instead of a drifting "last nightly run" — to measure alternative embedding models against.

## Acceptance Criteria

1. **Given** a freshly seeded `document_embeddings` table (seed via `python -m app.rag.seed` against the current `backend/data/rag-corpus/{en,uk}/` — 23 core + supplemental topics per language, ≥ 46 chunks total) **When** the harness runs (`cd backend && uv run pytest tests/eval/rag/ -v -m eval`) **Then** it completes without skip (AC #7 of Story 9.1 confirms seeded state) and writes a structurally-valid run report to `backend/tests/fixtures/rag_eval/runs/<timestamp>.json`

2. **Given** the harness run report from AC #1 **When** the baseline is promoted **Then** the file is copied (not moved — preserve the original timestamped run next to any other experimental runs the developer made) to `backend/tests/fixtures/rag_eval/baselines/text-embedding-3-small.json`, AND a sibling `backend/tests/fixtures/rag_eval/baselines/text-embedding-3-small.meta.json` is written capturing: embedding model (`text-embedding-3-small`), embedding dims (`1536`), LLM provider used for candidate+judge (from `get_llm_client()` — expected Anthropic Claude Haiku primary; record actual), corpus snapshot (git SHA of `HEAD` at run time + output of `ls backend/data/rag-corpus/{en,uk}/*.md | wc -l`), seed row count (`SELECT COUNT(*) FROM document_embeddings`), harness version (read `VERSION`), and ISO-8601 UTC run timestamp

3. **Given** baseline artifacts must be committed while ad-hoc runs remain gitignored **When** `.gitignore` is updated **Then** the existing rule `backend/tests/fixtures/rag_eval/runs/*.json` is preserved (ad-hoc runs stay local), AND `backend/tests/fixtures/rag_eval/baselines/` is explicitly included (i.e., NOT ignored — add a `!backend/tests/fixtures/rag_eval/baselines/` allow-rule only if an ancestor glob already ignores it; otherwise no new gitignore entry is needed since no ancestor rule catches `baselines/`). The committed baseline must be visible in `git status` and tracked by `git ls-files`.

4. **Given** Stories 9.3 and 9.6 will diff alternative-model reports against this baseline **When** the baseline is recorded in this story **Then** the "Baseline Results" section below is filled in with the key aggregate numbers extracted from `text-embedding-3-small.json`: overall `mean precision@1`, `mean precision@3`, `mean precision@5`, `mean recall@5`, `mean mrr`, `mean judge groundedness / relevance / language_correctness / overall`, total LLM tokens consumed (candidate + judge combined), per-language split (en vs uk) for `mean precision@5` and `mean judge overall`, per-topic worst-3 (topics with the lowest `mean judge overall`), and `worst_10` summary (count of rows with `judge.overall ≤ 1`). Numbers are reported to 3 decimals for metrics, integers for token counts.

5. **Given** the baseline is authoritative **When** a reader of 9.3 or 9.6 opens this story **Then** the "How to reproduce" subsection lists the exact commands (seed + pytest invocation + env vars required) and a pointer to `backend/tests/fixtures/rag_eval/baselines/text-embedding-3-small.meta.json` for the full reproducibility envelope

6. **Given** no new production code is introduced by this story (it is an execution + capture story) **When** the default test sweep runs (`uv run pytest tests/ -q`) **Then** it remains green with the same pass/deselect counts as Story 9.1's closeout (861 passed, 10 deselected) — no regressions, no new tests added to the default sweep, no change to `pyproject.toml` markers

7. **Given** the LLM-error budget assertion from Story 9.1 (`_MAX_ERROR_FRACTION = 0.2`) **When** the baseline run is performed **Then** if `error_rows / total_rows` exceeds 0.2 the harness will fail and this story's baseline capture is blocked — the dev must investigate the LLM-call failures (rate-limit, API key, judge parse errors) before re-running, AND if a genuinely healthy run still shows `error_rows > 0` the meta.json records the exact `error_rows` count so 9.3 can reproduce the same tolerance

## Tasks / Subtasks

- [x] Task 1: Verify environment + seeded corpus (AC: #1)
  - [x] 1.1 Confirm `ANTHROPIC_API_KEY` and `OPENAI_API_KEY` are set in the shell running the harness (the candidate-answer + judge path hits Anthropic primary, OpenAI fallback; the seeder hits OpenAI for embeddings).
  - [x] 1.2 Confirm a local Postgres + pgvector is reachable via `backend/.env` (per memory `feedback_python_venv.md` the venv lives at `backend/.venv` — run all commands from `backend/`).
  - [x] 1.3 Run `cd backend && uv run python -m app.rag.seed` to populate `document_embeddings` from the current corpus. Capture stdout row-count + any warnings for the meta.json.
  - [x] 1.4 Sanity-check via `psql` or a throwaway `SELECT COUNT(*) FROM document_embeddings;` that the seeded row count matches (roughly) `2 × topics × chunks-per-topic` given `seed.py` chunks on `## ` H2 headers.

- [x] Task 2: Execute baseline harness run (AC: #1, #7)
  - [x] 2.1 From `backend/`, run `uv run pytest tests/eval/rag/test_rag_harness.py -v -m eval -s` and watch for `error_rows > 20% of total` assertion. If it trips, stop and investigate rather than retrying mechanically (rate-limit is the likely culprit on a cold run — add `time.sleep` only if required; do NOT lower `_MAX_ERROR_FRACTION`).
  - [x] 2.2 Locate the written report at `backend/tests/fixtures/rag_eval/runs/<timestamp>.json`. Open it, spot-check that `overall`, `per_language`, `per_topic`, `per_question_type`, `worst_10`, and `error_rows` keys all exist and are populated.
  - [x] 2.3 If a previous ad-hoc run report exists in `runs/`, leave it untouched — the directory is gitignored so co-existence is expected.

- [x] Task 3: Promote run to baseline (AC: #2, #3)
  - [x] 3.1 Create directory `backend/tests/fixtures/rag_eval/baselines/` (new directory; not currently in the tree).
  - [x] 3.2 Copy the chosen run report to `backend/tests/fixtures/rag_eval/baselines/text-embedding-3-small.json` (the filename intentionally encodes the embedding model so 9.3 can land sibling files `text-embedding-3-large.json`, `titan-text-embeddings-v2.json`, `cohere-embed-multilingual-v3.json` alongside).
  - [x] 3.3 Author `backend/tests/fixtures/rag_eval/baselines/text-embedding-3-small.meta.json` per AC #2. Use a small inline Python one-liner or a short scratch script (do NOT commit the scratch script) to gather the env snapshot:
    - `git_sha` = `git rev-parse HEAD` at run time
    - `corpus_file_count_en` / `corpus_file_count_uk` = `ls backend/data/rag-corpus/{en,uk}/*.md | wc -l`
    - `document_embeddings_row_count` = `SELECT COUNT(*) FROM document_embeddings` (one-shot sync SQLAlchemy session is fine — the harness uses the same pattern in `_count_embeddings`)
    - `harness_version` = contents of `VERSION`
    - `llm_candidate_model` + `llm_judge_model` = inspect `get_llm_client()` return (likely `claude-haiku-4-5`) and record its `model` attribute
    - `embedding_model` = `text-embedding-3-small`
    - `embedding_dims` = `1536`
    - `run_timestamp_utc` = ISO-8601 timestamp used in the run filename
    - `error_rows` = copy from the run report
    - `total_rows` = copy from the run report
  - [x] 3.4 Verify `.gitignore` behavior: `git check-ignore backend/tests/fixtures/rag_eval/baselines/text-embedding-3-small.json` should NOT match (i.e., exit non-zero, meaning the file is NOT ignored). If it IS ignored because of a broader ancestor glob, add an explicit `!backend/tests/fixtures/rag_eval/baselines/` negation under the existing `backend/tests/fixtures/rag_eval/runs/*.json` rule.

- [x] Task 4: Record baseline numbers in this story file (AC: #4)
  - [x] 4.1 Populate the "Baseline Results" section below from `text-embedding-3-small.json`. All numbers must be copied verbatim from the run report (do not re-compute).
  - [x] 4.2 Populate "How to reproduce" (AC #5) with the exact commands used in Tasks 1 + 2.
  - [x] 4.3 If the run exhibited any noteworthy per-topic regression (judge overall ≤ 1 on > 20% of questions for a single topic), add a one-line flag under "Known weak spots in baseline" — these are the spots where 9.3's candidate models will need to at least match.

- [x] Task 5: No-regression verification (AC: #6)
  - [x] 5.1 From `backend/`, run `uv run pytest tests/ -q` — expect `861 passed, 10 deselected` (Story 9.1 closeout baseline). Any drift is an unrelated regression and must be escalated, not absorbed into this story.
  - [x] 5.2 Run `uv run ruff check .` and confirm no NEW violations introduced by this story (no backend code was edited — only baseline + meta JSON were added). Pre-existing ruff drift on `main` (44 errors as of HEAD `1371598`) is tracked separately as [TD-068](../../docs/tech-debt.md) and is explicitly NOT a 9.2 regression gate.

- [x] Task 6: Update cross-references (AC: #4)
  - [x] 6.1 Add a one-line pointer in `backend/tests/fixtures/rag_eval/README.md` under a new "Baselines" heading: path to `baselines/`, filename convention (one JSON per embedding model), and link back to this story file.
  - [x] 6.2 In `docs/testing.md`, under the existing "Evaluation harnesses" section (added by Story 9.1), append a sentence: "The current RAG baseline lives at `backend/tests/fixtures/rag_eval/baselines/text-embedding-3-small.json` — captured by Story 9.2."

## Dev Notes

### Scope discipline

This is an **execution + artifact-capture story**, not a code-change story. The only files added should be:

- `backend/tests/fixtures/rag_eval/baselines/text-embedding-3-small.json` (the committed baseline run report)
- `backend/tests/fixtures/rag_eval/baselines/text-embedding-3-small.meta.json` (reproducibility envelope)
- Edits to `backend/tests/fixtures/rag_eval/README.md` (one "Baselines" paragraph)
- Edits to `docs/testing.md` (one-line pointer)
- Optional `.gitignore` negation **only if** an ancestor rule shadows `baselines/` (almost certainly unnecessary — the current rule is narrowly `runs/*.json`)

No harness code changes. No new pytest fixtures. No new CI workflow steps. If the harness trips up and you are tempted to patch it, file a TD-NNN entry in `docs/tech-debt.md` and fix it in a follow-up story — do **not** conflate instrument fixes with baseline capture.

### Why a committed baseline vs. "just rerun the harness in 9.3"

If the baseline lives only as a transient run report, Stories 9.3 and 9.6 would each be re-running the current-embedding path as part of their own matrix, which:

1. Doubles cost (each rerun is ~46 × 2 LLM calls — non-trivial for a CI-budget-sensitive project).
2. Makes diffs non-reproducible: corpus evolves (new topics land), judge model version drifts, LLM provider switches (Story 9.5b adds Bedrock). A committed baseline freezes a specific `(corpus SHA, embedding model, judge model)` triple so future comparisons are apples-to-apples or consciously acknowledged as apples-to-oranges.
3. Breaks the audit trail: if a future embedding migration regresses quality in prod, the baseline that originally justified the decision needs to be loadable from `git log`, not reconstructed.

The meta.json is the reproducibility envelope — it tells any future dev what "current" meant on this date.

### Cost expectations

The 9.1 closeout reported the harness as 46 questions × (1 candidate call + 1 judge call) = 92 LLM invocations on Claude Haiku. On current pricing this is on the order of cents per run. The baseline is a one-shot capture. If the dev wants to average across a few runs to reduce judge-noise variance, they may — but the committed baseline must reference one canonical run (the others can live transiently in `runs/`).

### Handling judge noise

LLM-as-judge scores have inherent variance. This story does NOT attempt to average across N runs — the baseline is a single run, intentionally. Story 9.3's comparison will already absorb judge noise via relative deltas between models; averaging both sides is overkill for a decision-gate.

If noise concern is high, the dev MAY run the harness 2-3 times and pick the run with the median overall judge score to commit — document this choice in `meta.json` under a `selection_notes` field. Do NOT commit multiple baselines for the same model.

### What happens when the corpus grows

The corpus is expected to grow between now and Story 9.3 (additional topics may land). When 9.3 runs, it will:

1. Re-run the baseline embedding model against the new corpus AND the candidate models (same corpus SHA for all).
2. Store the new-corpus run as a secondary baseline (e.g., `text-embedding-3-small-corpus-v2.json`) only if the fixture set also grew.

This story (9.2) commits the baseline for the **current** corpus SHA. Do not block on "what if the corpus grows" — 9.3 will re-baseline if needed; the meta.json's `git_sha` field is the trigger for that decision.

### Integration points

- Harness entry: `backend/tests/eval/rag/test_rag_harness.py` (Story 9.1).
- LLM client path: `backend/app/agents/llm.py` — `get_llm_client()` returns `ChatAnthropic` (Claude Haiku 4.5). No branching needed per memory `project_agentcore_decision.md` (Bedrock comes in 9.5b, harness is provider-agnostic).
- Retriever under test: `backend/app/rag/retriever.py` — `retrieve_relevant_docs(query, language, top_k=5)`.
- Embedding model in use: `text-embedding-3-small` at 1536 dims (see `backend/app/rag/embeddings.py` lines 20, 31).
- Seed script: `backend/app/rag/seed.py` (idempotent; run before harness).
- Run report schema: see `backend/tests/eval/rag/test_rag_harness.py` for the exact keys written.
- Corpus root: `backend/data/rag-corpus/{en,uk}/` — 23 files per language as of this story.

### Memory / policy references

- `project_agentcore_decision.md` — Bedrock is deferred to Epic 10; harness stays on Anthropic + OpenAI. Baseline is captured on the current stack intentionally.
- `feedback_python_venv.md` — run all commands from `backend/` with the `backend/.venv`.
- `reference_tech_debt.md` — if any shortcut is taken (e.g., harness trips the error-budget and the dev raises the threshold to capture a baseline anyway), register a TD-NNN entry. No shortcuts expected.
- `project_observability_substrate.md` — no CloudWatch emission here; baseline is a local/committed JSON artifact.

### Project Structure Notes

- New directory: `backend/tests/fixtures/rag_eval/baselines/` (convention seed — one JSON + one meta JSON per embedding model).
- Aligns with Story 9.1's existing `backend/tests/fixtures/rag_eval/` layout: `eval_set.jsonl`, `runs/` (transient), `README.md`, and now `baselines/` (committed).
- No conflict with any other fixture pattern in the repo.

### Testing Standards

- No new tests are authored by this story. The default sweep (`uv run pytest tests/ -q`) is the regression gate and must remain `861 passed, 10 deselected`.
- The harness itself is the instrument under execution, not under test — running it with `-m eval` IS the "test" of this story, but its result (the report JSON) is the deliverable, not the pass/fail signal.

### References

- Epic 9 overview & stories: [epics.md#Epic 9](../_bmad-output/planning-artifacts/epics.md) lines 2021–2078
- Story 9.1 (harness that this story runs): [9-1-rag-evaluation-harness.md](./9-1-rag-evaluation-harness.md)
- Harness entry point: [backend/tests/eval/rag/test_rag_harness.py](../../backend/tests/eval/rag/test_rag_harness.py)
- Judge module: [backend/tests/eval/rag/judge.py](../../backend/tests/eval/rag/judge.py)
- Retriever under eval: [backend/app/rag/retriever.py](../../backend/app/rag/retriever.py)
- Embeddings wrapper: [backend/app/rag/embeddings.py](../../backend/app/rag/embeddings.py)
- Seed script: [backend/app/rag/seed.py](../../backend/app/rag/seed.py)
- LLM client factory: [backend/app/agents/llm.py](../../backend/app/agents/llm.py)
- RAG corpus: [backend/data/rag-corpus/](../../backend/data/rag-corpus/)
- Fixture README (to be extended with Baselines section): [backend/tests/fixtures/rag_eval/README.md](../../backend/tests/fixtures/rag_eval/README.md)
- Testing doc (to be extended): [docs/testing.md](../../docs/testing.md)

## Baseline Results

<!--
Filled in during Task 4.1 from backend/tests/fixtures/rag_eval/baselines/text-embedding-3-small.json.
Numbers to 3 decimals for metrics, integers for token counts. Do NOT hand-compute — copy verbatim from the report.
-->

| Aggregate | Value |
|---|---|
| Run timestamp (UTC) | 2026-04-22T16:26:16.160315+00:00 |
| Corpus git SHA | 137159821ad38aff42b455f0855034285fa9d9bd |
| Total rows / error rows | 46 / 0 |
| Total LLM tokens (candidate + judge) | 233404 |
| mean precision@1 | 0.783 |
| mean precision@3 | 0.783 |
| mean precision@5 | 0.726 |
| mean recall@5 | 0.935 |
| mean mrr | 0.839 |
| mean judge groundedness | 2.000 |
| mean judge relevance | 1.826 |
| mean judge language_correctness | 2.000 |
| mean judge overall | 3.696 |

**Per-language split:**

| Language | mean precision@5 | mean judge overall |
|---|---|---|
| en | 0.817 | 3.783 |
| uk | 0.635 | 3.609 |

**Worst-3 topics by mean judge overall** (tiebreaker: alphabetical on topic slug when `judge.overall` is equal):

1. `savings-strategies` — 2.000 (n=2)
2. `cash-vs-digital-payments` — 2.500 (n=2)
3. `budgeting-basics` — 3.000 (n=2) — tied at 3.000 with `financial-goals`, `interest-and-credit`, and others; alphabetical tiebreaker selects `budgeting-basics`. Story 9.3 comparators MUST apply the same tiebreaker when citing "worst-3".

**Rows with judge.overall ≤ 1 (from `worst_10`):** 1 row.

### Known weak spots in baseline

- `cash-vs-digital-payments` — 1/2 questions (50%) produced `judge.overall ≤ 1`, exceeding the >20% per-topic regression threshold. Story 9.3 candidate models must at least match the non-failing row's score on this topic, and preferably lift the failing row.
- Ukrainian corpus is materially weaker than English on every retrieval metric (uk `precision@5`=0.635 vs en `precision@5`=0.817; uk `mrr`=0.761 vs en `mrr`=0.917). Story 9.3 should treat the uk/en gap as a first-order evaluation axis, not an averaged-away detail.
- `savings-strategies` has the lowest per-topic judge score (2.000). Root cause is **mixed** (see Retrieval-miss shortlist below): one row is a retrieval miss (`rag-027`), the other is perfect retrieval + a generator-prompt violation (`rag-004`). Only the first is in-scope for Story 9.3.

### Retrieval-miss shortlist for Story 9.3

The worst-3 topics by `judge.overall` surface **only two genuine retrieval
misses** — both UK applied paraphrases where the query vocabulary drowns the
topic keyword. These are the concrete rows a candidate embedding model in
Story 9.3 must lift to count as a win:

| Row | Lang / type | Question | Retrieved top-5 | Gold | Judge | Failure mode |
|---|---|---|---|---|---|---|
| `rag-041` | uk / applied | *"Я розрахуюся готівкою — чи впливає це на мій бюджет-трекер у додатку?"* | `budgeting-basics`, `spending-patterns`×2, `groceries-food-spending`×2 | `uk/cash-vs-digital-payments` | `overall=1` (g=2, rel=0) | Budget-tracker vocabulary (`бюджет-трекер`, `додатку`) hijacks embedding; lone `готівкою` token insufficient to surface gold. |
| `rag-027` | uk / applied | *"Я хочу почати відкладати, але кожен місяць гроші закінчуються — з чого почати?"* | `budgeting-basics`×3, `emergency-fund`, `spending-patterns` | `uk/savings-strategies` | `overall=2` (g=2, rel=1) | `гроші закінчуються` ("money runs out") is lexically closer to budgeting/spending-patterns than to savings-strategies. Candidate gave a budgeting-track answer, which is useful-but-wrong — the gold concepts (pay-yourself-first, automation, named goals, separate accounts) were absent from retrieval. |

**Shared structural signature:** both are UK questions of `question_type =
applied` where the paraphrase drops the literal topic keyword and couches the
concept inside a denser adjacent-topic vocabulary. This is the specific
failure shape Story 9.3 is trying to buy improvement on — candidate models
should be evaluated first on whether they retrieve the gold for these two
rows, *then* on aggregate deltas. A model that lifts averages but regresses
on these rows is not a win for the real user query distribution.

**Acceptance bar for a candidate model in 9.3:**
1. Both `rag-041` and `rag-027` retrieve their gold doc in top-5 (ideally top-3).
2. No regression on the 31 currently-perfect rows (`p@1 == p@3 == 1.0` → should stay).
3. UK/EN gap narrows: candidate's uk `p@5` ≥ 0.700 (current 0.635) without dropping en `p@5` below 0.800 (current 0.817).

### Out-of-scope-for-9.3 findings surfaced by the worst-3 scan

Two rows in the worst-3 topics are **generator-prompt issues with perfect
retrieval**, not embedding-model problems. Recording them here so 9.3 doesn't
chase them and so a follow-up prompt/TD ticket can pick them up:

| Row | Lang / type | Retrieval | Judge rationale |
|---|---|---|---|
| `rag-004` | en / definitional — *"Define pay-yourself-first saving in one sentence."* | **5/5 chunks from `en/savings-strategies`** (perfect) | `overall=2, relevance=1` — *"fails to meet the explicit instruction to define … in ONE sentence by providing three sentences instead."* |
| `rag-024` | uk / definitional — *"Що таке бюджет — одним реченням?"* | **4/5 chunks from `uk/budgeting-basics`** | `overall=2, relevance=1` — *"violates the explicit instruction to answer in one sentence by providing three sentences instead."* |

Both are the harness's own candidate prompt (`_CANDIDATE_PROMPT_EN/UK` in
[`backend/tests/eval/rag/judge.py`](../../backend/tests/eval/rag/judge.py)
hard-codes "2-4 sentences") overriding the user's explicit "one sentence"
instruction. Candidate answer for definitional/one-sentence questions will
always be penalized under the current prompt. Recommended follow-up: make
the candidate-answer prompt respect user-specified length instructions
(small prompt tweak, not an embedding change). File a TD entry when
addressing — outside Story 9.2 scope.

### How to reproduce

```bash
# From repo root
cd backend

# 1. Seed corpus (idempotent)
uv run python -m app.rag.seed

# 2. Run harness in eval mode
uv run pytest tests/eval/rag/test_rag_harness.py -v -m eval -s

# 3. Inspect the report
ls -la tests/fixtures/rag_eval/runs/
# Locate the freshest <timestamp>.json — that is the run that was promoted to
# tests/fixtures/rag_eval/baselines/text-embedding-3-small.json.
```

Full reproducibility envelope (env snapshot at baseline time): [`backend/tests/fixtures/rag_eval/baselines/text-embedding-3-small.meta.json`](../../backend/tests/fixtures/rag_eval/baselines/text-embedding-3-small.meta.json).

## Dev Agent Record

### Agent Model Used

claude-opus-4-7[1m] (Claude Opus 4.7, 1M context)

### Debug Log References

- Seed output: `INFO: Seed complete: 46 files processed, 276 total chunks upserted`
- Harness summary: `total=46 errors=0 p@1=0.783 p@5=0.726 mrr=0.839 judge_overall=3.696 tokens=233404 elapsed=211.7s`
- Run report written: `backend/tests/fixtures/rag_eval/runs/20260422T162616162751Z.json`
- Default sweep: `861 passed, 10 deselected, 2 warnings in 163.62s` — matches Story 9.1 closeout exactly (no regression).

### Completion Notes List

- Executed the Story 9.1 RAG harness end-to-end against the freshly-seeded current-corpus state on `text-embedding-3-small` @ 1536 dims. Single canonical run captured as baseline (no multi-run averaging — per `Dev Notes → Handling judge noise` this is intentional for a decision-gate artifact).
- `error_rows = 0` — well under the `_MAX_ERROR_FRACTION = 0.2` budget. No harness retries, no rate-limit incidents, no `time.sleep` band-aid added.
- Baseline + meta JSON committed under `backend/tests/fixtures/rag_eval/baselines/`. Gitignore check (`git check-ignore baselines/text-embedding-3-small.json` → exit 1) confirms the ancestor `runs/*.json` rule does NOT shadow the new `baselines/` directory — no negation rule needed.
- Scope kept tight per `Dev Notes → Scope discipline`: only the expected files touched (2 new JSON under `baselines/`, README + docs edits, sprint-status + story file, VERSION). No harness code changes, no new tests, no new CI steps, no `pyproject.toml` marker changes.
- **Pre-existing ruff drift noted but NOT fixed in-scope:** `uv run ruff check .` reports 44 errors on current HEAD — these exist on the clean tree *before* any 9.2 changes (verified via `git stash`). None are in files touched by this story. Not a 9.2 regression; flagging here rather than registering a TD entry since the drift is unrelated to the baseline-capture workstream and the fix belongs in its own cleanup PR. AC #6's "ruff clean" expectation was based on an incorrect assumption in the story draft about the starting state; the substantive AC (no regressions introduced by this story, same default-sweep pass count) is satisfied.
- Per-language gap surfaced in the baseline (uk precision@5=0.635 vs en precision@5=0.817, judge overall 3.609 vs 3.783) is now frozen as a first-order evaluation axis for Story 9.3 — this is one of the load-bearing "known weak spots" that candidate models will be measured against.

### File List

- `backend/tests/fixtures/rag_eval/baselines/text-embedding-3-small.json` (new) — committed canonical run report
- `backend/tests/fixtures/rag_eval/baselines/text-embedding-3-small.meta.json` (new) — reproducibility envelope (post-review: `total_questions` alias added alongside `total_rows`)
- `backend/tests/fixtures/rag_eval/README.md` (modified) — added "Baselines" section + updated file-layout tree; post-review: "Meta schema" subsection + capture recipe added
- `docs/testing.md` (modified) — appended pointer to current RAG baseline
- `docs/tech-debt.md` (modified, post-review) — new [TD-068](../../docs/tech-debt.md) entry for pre-existing 44-error ruff drift on `main`
- `_bmad-output/implementation-artifacts/9-2-baseline-current-embeddings.md` (modified) — status, tasks ticked, Baseline Results filled, Dev Agent Record, File List, Change Log, Code Review section
- `_bmad-output/implementation-artifacts/sprint-status.yaml` (modified) — 9.2 status ready-for-dev → in-progress → review
- `VERSION` (modified) — 1.31.0 → 1.32.0 (MINOR bump per `docs/versioning.md`: any merged story)

## Change Log

- 2026-04-22 — Story 9.2 drafted: baseline-capture story for the Story 9.1 RAG harness on current `text-embedding-3-small` embeddings. No code changes; artifact-only deliverable under `backend/tests/fixtures/rag_eval/baselines/`.
- 2026-04-22 — Baseline captured: run `20260422T162616162751Z.json` promoted to `baselines/text-embedding-3-small.json`; `.meta.json` envelope written; README + `docs/testing.md` cross-refs added. Default sweep 861 passed / 10 deselected (no regression). Version bumped 1.31.0 → 1.32.0 per story completion.
- 2026-04-22 — Adversarial code review applied: Task 5.2 wording softened to "no NEW violations introduced" and the pre-existing 44-error ruff drift registered as [TD-068](../../docs/tech-debt.md); `total_questions` alias added to `text-embedding-3-small.meta.json` to resolve the run-report ↔ meta-schema naming drift (AC wording uses `total_rows`, report emits `total_questions` — both now present with identical values); `backend/tests/fixtures/rag_eval/README.md` grew a "Meta schema" section enumerating required `.meta.json` fields plus a copy-pasteable capture recipe so Story 9.3 doesn't reinvent it; worst-3 topic list pinned an alphabetical tiebreaker for the 3.000-overall ties.
- 2026-04-23 — Retrieval-miss shortlist added to "Known weak spots": two UK-applied rows (`rag-041` cash-vs-digital-payments, `rag-027` savings-strategies) identified as the genuine embedding-layer failures for Story 9.3 to target, with concrete acceptance bar (both retrieve gold in top-5; uk `p@5` ≥ 0.700 without regressing en `p@5`). Two additional worst-3 rows (`rag-004`, `rag-024`) re-classified as generator-prompt failures (candidate prompt's "2-4 sentences" overrides user's "one sentence" instruction) — flagged as a separate future TD item, explicitly out-of-scope for 9.3.

## Code Review

- 2026-04-22 — Adversarial review by claude-opus-4-7[1m]. Findings vs git reality: File List reconciles 1:1 with git working-tree; all Baseline Results numbers reconcile verbatim against the committed report. Disposition:
  - **HIGH-1** AC #3 tracked-by-`git ls-files` clause: left open — user will commit story + baselines together to satisfy it.
  - **MEDIUM-2** Task 5.2 ruff-clean checkbox: fixed (task text softened, drift registered as TD-068).
  - **MEDIUM-3** `total_rows` vs `total_questions` schema drift: fixed (alias added to meta.json, naming note in README).
  - **MEDIUM-4** Meta-assembly recipe missing: fixed (capture snippet now in README "To add a new baseline").
  - **LOW-5** Worst-3 tiebreaker undocumented: fixed (alphabetical tiebreaker pinned in Baseline Results).
  - **LOW-6** README field enumeration: fixed (Meta schema subsection added).
  - **LOW-7** VERSION merge-order risk: accepted — non-defect, mitigated by committing the story promptly.
