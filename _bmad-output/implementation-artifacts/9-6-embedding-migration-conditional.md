# Story 9.6: Embedding Migration — text-embedding-3-large (3072-dim halfvec)

Status: done
Created: 2026-04-23
Epic: 9 — AI Infra Readiness (Bedrock Provider, RAG Eval Harness, Embedding Decision)

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **backend developer closing Epic 9's embedding-decision track** (Stories 9.1 → 9.2 → 9.3 → **9.6**),
I want to **migrate the production `document_embeddings` table from OpenAI `text-embedding-3-small` (1536-dim `vector`) to OpenAI `text-embedding-3-large` (3072-dim `halfvec`)** — touching exactly the four code surfaces identified by TD-079's fix shape ([backend/alembic/versions/g3h4i5j6k7l8_create_document_embeddings_table.py](../../backend/alembic/versions/g3h4i5j6k7l8_create_document_embeddings_table.py), [backend/app/models/embedding.py](../../backend/app/models/embedding.py), [backend/app/rag/embeddings.py](../../backend/app/rag/embeddings.py), [backend/app/rag/retriever.py](../../backend/app/rag/retriever.py)), re-seeding the RAG corpus via [backend/app/rag/seed.py](../../backend/app/rag/seed.py), and gating the close on a re-run of Story 9.1's harness that lands the deterministic retrieval metrics within judge-noise of the Story 9.3 spike baseline at [backend/tests/fixtures/rag_eval/baselines/text-embedding-3-large.json](../../backend/tests/fixtures/rag_eval/baselines/text-embedding-3-large.json),
so that **(a)** the +0.122 mean `p@5` / +0.200 uk `p@5` / +0.118 `mrr` retrieval gains quantified in [docs/decisions/embedding-model-comparison-2026-04.md](../../docs/decisions/embedding-model-comparison-2026-04.md) land in production RAG instead of sitting in a committed spike artefact, **(b)** the two known-miss Ukrainian paraphrase rows (`rag-041` `uk/cash-vs-digital-payments`, `rag-027` `uk/savings-strategies`) start retrieving their gold docs at ranks 1 & 2 — unblocking the applied-content slice of Story 3.3's education agent before Epic 10 chat consumes the same corpus, **(c)** TD-079's HIGH-priority pgvector 2000-dim HNSW cap is closed by moving production storage to `halfvec(3072)` + `halfvec_cosine_ops` (the shape the Story 9.3 spike already validated end-to-end), and **(d)** Epic 10's Chat-with-Finances Scope-lock can take a hard dependency on "RAG retrieval is on the winner embedder" without a re-open of the Story 9.3 decision gate.

## Acceptance Criteria

1. **Given** TD-079 ([docs/tech-debt.md:1199](../../docs/tech-debt.md#L1199)) defines the exact six-step fix shape for Story 9.6 and that shape was validated end-to-end by the Story 9.3 spike at [backend/tests/eval/rag/candidates/runner.py:111-157](../../backend/tests/eval/rag/candidates/runner.py#L111-L157), **When** this story ships **Then** each of the four production code surfaces named in TD-079 (Alembic migration, `DocumentEmbedding` SQLModel, `app/rag/embeddings.py`, `app/rag/retriever.py`) is edited exactly once and no other `app/` surface is touched. Specifically:
   - A new Alembic revision file under [backend/alembic/versions/](../../backend/alembic/versions/) named `<hex>_migrate_document_embeddings_to_halfvec_3072.py` with `down_revision = "z2a3b4c5d6e7"` (the current head per Task 1.2's `uv run alembic heads`) — NOT an edit to the existing `g3h4i5j6k7l8_create_document_embeddings_table.py` migration. History is append-only; the old revision stays as a historical record of the 1536-`vector` shape and a `downgrade()` on the new revision restores it (see AC #3).
   - [backend/app/models/embedding.py:24](../../backend/app/models/embedding.py#L24) changes from `Vector(1536)` to `HALFVEC(3072)` (imported from `pgvector.sqlalchemy` — already present on disk per Task 1.3's smoke).
   - [backend/app/rag/embeddings.py](../../backend/app/rag/embeddings.py) — `embed_text` and `embed_batch` switch their `model=` kwarg from `"text-embedding-3-small"` to `"text-embedding-3-large"`. Module docstring at line 1 is updated from *"Thin wrapper around OpenAI text-embedding-3-small API"* to *"Thin wrapper around OpenAI text-embedding-3-large API"*. The line-19 docstring *"returning a 1536-dim vector"* becomes *"returning a 3072-dim vector"*. No other API shape change: the functions still take/return `list[float]` / `list[list[float]]`; callers (`retriever.py`, `seed.py`) are untouched.
   - [backend/app/rag/retriever.py](../../backend/app/rag/retriever.py) — the two `CAST(:embedding AS vector)` occurrences (language-filtered path at line 33 + 36, cross-lingual fallback at line 61 + 64) change to `CAST(:embedding AS halfvec)`. No behavioural change: `MIN_RESULTS=3` fallback trigger preserved, language-filter-first ordering preserved, the `1 - (embedding <=> CAST(...))` cosine-similarity shape preserved (the `<=>` operator is the same for `vector` and `halfvec` — confirmed by the Story 9.3 spike at [runner.py:251-266](../../backend/tests/eval/rag/candidates/runner.py#L251-L266)).

   **Explicit non-scope:** [backend/app/rag/seed.py](../../backend/app/rag/seed.py) is **not edited**. Its `INSERT` at [seed.py:99](../../backend/app/rag/seed.py#L99) uses `'{literal}'::vector` — pgvector parses that literal as `vector` but implicit cast to the column's `halfvec(3072)` type works natively on pgvector 0.8.x (the Story 9.3 spike runner used the same pattern — see [runner.py:214-239](../../backend/tests/eval/rag/candidates/runner.py#L214-L239) which writes `CAST(:embedding AS halfvec)` explicitly because the runner templates `col_type`, but on a table where the column is already `halfvec(3072)` an untyped literal insert resolves the same). If the dev sees an `operator does not exist` error on the seed path, this AC flips to "edit `seed.py:99`'s literal cast from `'...'::vector` to `'...'::halfvec`" and the change stays minimal — see Task 3.4's verification step.

2. **Given** the two distinct Story 9.3 baselines that this migration can be judged against — the pre-registration **AC #7b strict baseline** at [baselines/text-embedding-3-small.9-3-rerun.json](../../backend/tests/fixtures/rag_eval/baselines/text-embedding-3-small.9-3-rerun.json) (control) vs. the **3-large spike expectation** at [baselines/text-embedding-3-large.json](../../backend/tests/fixtures/rag_eval/baselines/text-embedding-3-large.json) (target) — **When** this story's acceptance gate evaluates the post-migration harness re-run **Then** the gate is **structural + deterministic-metric convergence**, not judge-score convergence. Per the decision doc's "Judge-noise caveat" ([embedding-model-comparison-2026-04.md lines 112-140](../../docs/decisions/embedding-model-comparison-2026-04.md#L112-L140)), judge overall drifts ±0.108 across identical inputs, so judge-score gating on a single post-migration run is not reliable. Concretely the gate is:
   - **Deterministic retrieval metrics within ±0.02 of the 3-large spike:** mean `p@5 ≥ 0.828` (spike 0.848), uk `p@5 ≥ 0.815` (spike 0.835), en `p@5 ≥ 0.841` (spike 0.861), mean `mrr ≥ 0.937` (spike 0.957). These metrics are deterministic given the same corpus SHA + same embedder (the spike and production share both after the migration), so a ±0.02 tolerance is effectively "indistinguishable from the spike". A breach of this tolerance on any of the four metrics means the migration changed retrieval behavior vs. the spike — a **hard fail** that must be triaged before close-out.
   - **Shortlist rows retrieve gold at the spike ranks:** `rag-041` gold doc `uk/cash-vs-digital-payments` must appear at **rank 1** in the top-5 (spike = 1); `rag-027` gold doc `uk/savings-strategies` must appear at **rank ≤ 2** in the top-5 (spike = 2). These two rows are the ones the migration exists to fix — if either slips outside the top-5 after migration, the harness re-run has detected a regression against the spike and close-out is blocked until root-caused.
   - **Zero regression on the 31-row "previously-perfect" set:** any eval row that scored `p@1 == p@3 == 1.0` against both the 9.2 baseline and the 9.3 3-large spike must still score `p@1 == p@3 == 1.0` post-migration. The spike's run-report records this row set (`regression rows (of 31)` column in the decision doc's per-row shortlist table — all candidates scored 0 regressions). A non-zero regression count on this axis is a **hard fail**.
   - **Judge score is informational only:** the post-migration judge overall is **recorded** in the run-report and **noted** in the story's Completion Notes, but NOT gated. Expected landing: `3.70 ≤ judge overall ≤ 3.85` (1.5σ around the observed 3-small ↔ 3-large ↔ 3-small-rerun range of 3.696–3.804–3.761). A judge score outside that window is worth a line in Completion Notes ("judge-noise drifted again" or "post-quantization artefact?") but not a blocker.
   - **Halfvec quantization sanity:** `halfvec` is float16 (2 bytes/dim) whereas `vector` is float32 (4 bytes/dim). The 3-large spike stored embeddings as `halfvec(3072)` end-to-end and landed the metrics above — so the ±0.02 tolerance already incorporates quantization loss. No additional "quantization-only ablation" is required.

3. **Given** rollback semantics must exist for a migration that truncates + re-seeds 276 embedding rows (corpus SHA `46f3307` per the spike baseline) — the migration is not reversible in the "flip the revision and get 1536-vector data back" sense because **the 3-small vectors are not preserved**, only the `document_embeddings.content` text column is — **When** the new Alembic revision's `downgrade()` is called **Then** it restores the schema to `vector(1536)` + `vector_cosine_ops` HNSW, and the downgrade's docstring explicitly states **"Schema-only downgrade. The `document_embeddings` table is TRUNCATED and must be re-seeded via `python -m app.rag.seed` after downgrade. The 3-small embeddings that existed pre-migration are not recoverable from the migration alone."** Operational reality: this is the same data-loss shape as an initial table create — the row-level content is re-derivable from the committed corpus markdown at [backend/data/rag-corpus/](../../backend/data/rag-corpus/) under corpus SHA `46f3307`, and the embeddings re-derive from `seed.py` on whichever embedder is wired up at the point of re-seed. If a hypothetical future rollback needs original-tokens-preserved semantics, that's a data-export-step that Story 9.6 does not build — it belongs in a dedicated ops runbook if it's ever actually needed.

4. **Given** the migration's `upgrade()` must produce the exact schema shape the Story 9.3 spike validated — because the spike's retrieval metrics are the only pre-registered expectation we have for the post-migration production table — **When** the migration runs against a Postgres instance with the existing `document_embeddings` table (as will be the case in dev, CI, and production) **Then** `upgrade()`:
   - Executes a single `DROP TABLE document_embeddings CASCADE` followed by a full re-create. **Why DROP instead of `ALTER COLUMN ... TYPE`:** the TD-079 fix shape at [docs/tech-debt.md:1208](../../docs/tech-debt.md#L1208) specifies `ALTER TABLE ... ALTER COLUMN embedding TYPE halfvec(3072) USING NULL`, but that path leaves the HNSW index referencing the old column and the index drop/recreate ends up being 3 separate statements + a `DROP INDEX` that can silently fail if the index name differs from expectation. A clean drop-recreate mirrors the spike's `_ensure_sidecar_table_named` at [runner.py:127-157](../../backend/tests/eval/rag/candidates/runner.py#L127-L157) exactly — which is the **only** halfvec(3072) + HNSW shape that has empirical passing metrics — and the old embeddings are going to be truncated either way per AC #3.
   - The re-create mirrors the original [g3h4i5j6k7l8](../../backend/alembic/versions/g3h4i5j6k7l8_create_document_embeddings_table.py) migration's statement shape exactly (CREATE TABLE → two btree indexes on `doc_id` and `language` → HNSW index), with three deltas: (a) `embedding halfvec(3072) NOT NULL` instead of `vector(1536)`, (b) HNSW index uses `halfvec_cosine_ops` instead of `vector_cosine_ops`, (c) HNSW `(m = 16, ef_construction = 64)` parameters preserved verbatim.
   - `CREATE EXTENSION IF NOT EXISTS vector` is retained at the top of `upgrade()` — the extension serves both `vector` and `halfvec` types, so no new extension load is needed, but the existing create-if-not-exists is cheap and keeps the migration self-contained if a fresh DB replays history from the top.
   - NO partial-migration or "both-tables-live" staging. The migration is a single transaction (implicit Alembic wrapping); either the whole thing applies or none of it does. Rationale: 276 rows at 3072 dims × float16 = ~1.7 MB of embeddings; re-seed time from empty is ~16s end-to-end per the 9.3 spike's `seed_elapsed_seconds=16.177` in [baselines/text-embedding-3-large.meta.json](../../backend/tests/fixtures/rag_eval/baselines/text-embedding-3-large.meta.json). No zero-downtime dual-table dance is justified at this scale.

5. **Given** the acceptance gate at AC #2 requires a **real** harness run against the production table (not a sidecar, not a spike re-run), and that run must be **reproducible enough** that a future reader can re-check the gate **When** Task 4 executes the harness **Then**:
   - The harness invocation is the canonical Story 9.1 command, unchanged: `cd backend && uv run pytest tests/eval/rag/ -v -m eval`. No new pytest marker, no new CLI wrapper. The harness at [tests/eval/rag/test_rag_harness.py:91-99](../../backend/tests/eval/rag/test_rag_harness.py#L91-L99) already auto-skips when `document_embeddings` is empty — after Task 3's re-seed, it will proceed.
   - The resulting run-report at [tests/fixtures/rag_eval/runs/](../../backend/tests/fixtures/rag_eval/runs/) is **promoted** to a new baseline artefact at [tests/fixtures/rag_eval/baselines/](../../backend/tests/fixtures/rag_eval/baselines/) named `production-text-embedding-3-large.9-6-cutover.json` with a sibling `.meta.json`. Shape mirrors existing `.meta.json` files verbatim. The `candidate_of` field is set to `"9.6"` (not 9.3), `candidate_slug` to `"production-text-embedding-3-large"`, `corpus_git_sha` captured from `git rev-parse HEAD` at run-time, `run_timestamp_utc` ISO-8601 UTC.
   - The run-report is committed to the repo — same convention as the four Story 9.3 baselines at [baselines/](../../backend/tests/fixtures/rag_eval/baselines/). This makes the post-migration state a permanent reference point for any future embedding re-visit.
   - The AC #2 gate metrics are recorded in the story's Completion Notes with the observed values (e.g. `mean p@5: 0.852 (target ≥ 0.828 ✓)`), alongside the run-report filename. This is the artifact trail a reviewer checks to confirm the gate passed.

6. **Given** three existing unit-test files assert the old 1536-dim shape — [tests/test_embeddings.py](../../backend/tests/test_embeddings.py) (explicitly, 6 assertions), [tests/test_rag_retrieval.py](../../backend/tests/test_rag_retrieval.py) (4 lines using `[0.1] * 1536`), and indirectly [tests/eval/rag/test_rag_harness.py](../../backend/tests/eval/rag/test_rag_harness.py) (via live DB — covered by AC #5) — **When** this story ships **Then**:
   - `backend/tests/test_embeddings.py` is updated in-place (not deleted): every `1536` literal becomes `3072`; every `model="text-embedding-3-small"` assertion becomes `model="text-embedding-3-large"`; the test function `test_embed_text_returns_1536_floats` is renamed to `test_embed_text_returns_3072_floats` (function name reads as documentation — the dim is part of the contract). Test count stays at 3 functions; semantics stay identical.
   - `backend/tests/test_rag_retrieval.py`'s `[0.1] * 1536` patch values at lines 23, 49, 72, 100 become `[0.1] * 3072`. No other edit — the tests mock `embed_text` and operate on the `retriever` module, so the cast-target change in `retriever.py` (AC #1) is exercised implicitly via the real SQL path only if the test hits a DB, which it does not (pure unit tests with mocked embed). The mock return value's dim is a smoke check of "caller passes what the embedder returns"; increasing it to 3072 keeps the mock consistent with the real embedder's output shape.
   - The default pytest sweep `cd backend && uv run pytest tests/ -q` after this story lands reads **`872 passed, 20 deselected`** (preserving the exact count from Story 9.5c's close) — **OR**, if Story 9.5c's post-close default sweep has drifted, the dev records the new baseline in Task 1.1 and uses that as the expected count. The important invariant: passed-count delta vs. the pre-story baseline is **0** (no new passing tests added, no existing tests broken, only rewritten-in-place).

7. **Given** production seeding is a one-time batch run that must happen after the Alembic migration lands and before the harness-gate re-run (AC #5), **When** this story's cutover path is documented **Then** [backend/app/rag/seed.py](../../backend/app/rag/seed.py)'s module docstring is extended (non-code change, documentation only) with a one-paragraph "Story 9.6 cutover note" referring back to the new Alembic revision and explicitly stating that seeding is **idempotent via `ON CONFLICT DO UPDATE`** (per [seed.py:100-103](../../backend/app/rag/seed.py#L100-L103)) — so running it a second time if the first run partially failed is safe. The canonical cutover sequence, captured in the story's Dev Notes:
   1. `cd backend && uv run alembic upgrade head` → schema is now `halfvec(3072)` + HNSW `halfvec_cosine_ops`, table is empty.
   2. `cd backend && python -m app.rag.seed` → embeds corpus via OpenAI `text-embedding-3-large` and upserts into the empty table. Expected: `276 rows, ~16s` (per 9.3 spike meta).
   3. `cd backend && uv run pytest tests/eval/rag/ -v -m eval` → harness re-run, produces run-report, gate metrics assessed per AC #2.
   4. Run-report promoted to baseline per AC #5, committed to repo.

   No code edit to `seed.py` beyond the docstring note (the module is embedding-model-agnostic by design — it imports `embed_batch` from `app.rag.embeddings` which AC #1 already updates).

8. **Given** cross-provider regression (Story 9.5c's `test_*_matrix` at [tests/agents/providers/](../../backend/tests/agents/providers/)) is categorization/education/schema-detection-LLM-only — **not** an embedding regression — **When** the matrix is considered against this story **Then** there is **no expected interaction**. The provider matrix tests the LLM output shape across `{anthropic, openai, bedrock}`; embeddings are OpenAI-only on both pre- and post-migration. If a future embedding-provider split (e.g. Titan / Cohere) is ever revisited — see the decision doc's "Per-language routing — evaluated and declined" at [lines 283-304](../../docs/decisions/embedding-model-comparison-2026-04.md#L283-L304) for why it isn't now — a new story would introduce an embedding-provider abstraction parallel to `llm.py`'s factory. Story 9.6 deliberately does not lay that foundation because YAGNI applies: the migration picks a single winner (3-large) and bakes it into `embeddings.py` directly, consistent with the decision doc's "Decision: single-model migration to 3-large for both languages".

9. **Given** `docs/tech-debt.md` tracks deferred work with `TD-NNN` IDs (highest existing entry **TD-086** per Story 9.5c's close), **When** this migration surfaces or closes TDs **Then**:
   - **TD-079 is resolved.** Add a `**Resolved (Story 9.6, 2026-04-XX):**` note at the end of the TD-079 block ([docs/tech-debt.md:1199-1215](../../docs/tech-debt.md#L1199-L1215)) pointing to this story file + the new Alembic revision filename + the cutover run-report baseline filename from AC #5. Do NOT delete the TD entry — tech-debt register convention is to preserve the historical record and mark `**Status:** Resolved` rather than remove the block. Precedent: [docs/tech-debt.md](../../docs/tech-debt.md) search for `**Resolved** (Story` to find prior examples.
   - **Expected new TD candidates (add only if they arise):**
     - **(a)** If the AC #1 non-scope for `seed.py` breaks (implicit `::vector` → `halfvec` cast fails at runtime), add **TD-087** [LOW] "`seed.py` SQL literal assumes `vector` cast; harmless given `halfvec`-typed column but explicit cast would be less surprising" with a one-line fix shape (`'{literal}'::halfvec` at [seed.py:99](../../backend/app/rag/seed.py#L99)). If AC #1's fallback path is taken (Task 3.4's verification catches it), the edit lands in this story and no TD is needed — this only becomes a TD if a future edge case (different pgvector version) surfaces it.
     - **(b)** If the harness re-run (AC #5) lands `judge_overall` outside the `[3.70, 3.85]` informational band at AC #2, add **TD-088** [LOW] "Post-migration judge-score drift beyond ±1.5σ noise band; confirm via 3-run median before treating as regression". Not a blocker per AC #2 but worth a register entry so a future Epic-10 grounding-gate tuning story sees the signal.
     - **(c)** If the new Alembic revision's `down_revision` resolution at Task 1.2 reveals that a story landed between 9.5c and 9.6 with an Alembic migration of its own (i.e. head has moved past `z2a3b4c5d6e7`), update Task 2's `down_revision = "<new-head>"` and capture the actual head in Completion Notes. This is not a TD — it's just keeping the migration chain honest.
   - If none of (a)–(c) apply, add no new TD entries. TD-079 resolution is the mandatory change regardless.

10. **Given** ruff + mypy + the default pytest sweep all gate merges per [backend/AGENTS.md](../../backend/AGENTS.md) and [backend/pyproject.toml](../../backend/pyproject.toml), **When** this story ships **Then**:
    - `cd backend && uv run ruff check .` passes on the four edited files (Alembic migration, `embedding.py` model, `embeddings.py`, `retriever.py`) + the two updated test files. Any pre-existing `ruff` drift on unrelated files is **not** in scope per TD-068.
    - `cd backend && uv run mypy app/` passes with zero errors on the edited files. `HALFVEC` has a stub in `pgvector.sqlalchemy` per the 9.3 spike — Task 1.3 confirms `from pgvector.sqlalchemy import HALFVEC` imports cleanly.
    - The default sweep `cd backend && uv run pytest tests/ -q` passed count is **unchanged** from Task 1.1's baseline (see AC #6). The `-m eval` and `-m provider_matrix` markers continue to deselect the harness + the cross-provider matrix by default — neither is touched by this story.
    - `git diff --stat` after this story lands, scoped to `backend/app/`, shows exactly **3 files changed** (`models/embedding.py`, `rag/embeddings.py`, `rag/retriever.py`). Scoped to `backend/alembic/versions/`: **1 file added** (the new revision). Scoped to `backend/tests/`: **2 files changed** (`test_embeddings.py`, `test_rag_retrieval.py`). Scoped to `docs/`: **1 file changed** (`tech-debt.md` TD-079 resolution) + **1 file changed** (optional, `docs/decisions/embedding-model-comparison-2026-04.md` may get a line note under "Follow-ups" pointing at this story's close — this is a nice-to-have, not required).

11. **Given** sprint-status.yaml tracks story state, **When** this story is ready for dev **Then** [_bmad-output/implementation-artifacts/sprint-status.yaml](../../_bmad-output/implementation-artifacts/sprint-status.yaml)'s `9-6-embedding-migration-conditional:` key is flipped `backlog` → `ready-for-dev` by the create-story workflow (this file), and on story close-out the implementing dev flips it to `review` (code-review flips to `done` per the normal flow). The existing multi-line pointer comment above that line (at [sprint-status.yaml:196-206](../../_bmad-output/implementation-artifacts/sprint-status.yaml#L196-L206), starting *"Story 9.6 GATED AS 'MIGRATE' per Story 9.3 decision doc..."* and ending *"Source: docs/decisions/embedding-model-comparison-2026-04.md"*) is **preserved verbatim** — it captures the story's origin signal and post-diagnostic recalibration rationale and is referenced from AC #2 / AC #3 / the decision doc. After story close-out, the dev may append a single-line pointer above the `9-7-bedrock-iam-observability` key (which is the next-up backlog story and does NOT depend on 9.6's deliverables — it's the Epic 10 IAM prep track). Leaving the 9-7 comment block alone is acceptable too.

## Tasks / Subtasks

- [x] Task 1: Baseline + confirm preconditions (AC: #1, #6, #10)
  - [x] 1.1 Baseline captured: **872 passed, 23 deselected** (deselected drifted from 20 → 23 since 9.5c close; passed-count matches story expectation).
  - [x] 1.2 Alembic head observed: `a3b4c5d6e7f8` (`widen_bank_format_registry_hint`) — a newer revision has landed since the story was authored. Used that as the new migration's `down_revision`.
  - [x] 1.3 `HALFVEC` import smoked cleanly: `pgvector.sqlalchemy.halfvec`.
  - [x] 1.4 TD-079 block and the Story 9.3 decision doc were re-read in full before any edit.

- [x] Task 2: Author the Alembic migration (AC: #1, #3, #4)
  - [x] 2.1 Created [backend/alembic/versions/e0f04e4194bc_migrate_document_embeddings_to_halfvec_.py](../../backend/alembic/versions/e0f04e4194bc_migrate_document_embeddings_to_halfvec_.py) with `down_revision = "a3b4c5d6e7f8"`.
  - [x] 2.2 `upgrade()` authored per AC #4: `CREATE EXTENSION IF NOT EXISTS vector`, `DROP TABLE IF EXISTS document_embeddings CASCADE`, re-create with `halfvec(3072)` + two btree indexes + HNSW `halfvec_cosine_ops` (m=16, ef_construction=64).
  - [x] 2.3 `downgrade()` authored per AC #3: schema-only restore to `vector(1536)` + `vector_cosine_ops` HNSW, with the verbatim docstring warning.
  - [x] 2.4 Applied against local Postgres, verified `embedding` column is `halfvec` and the HNSW index uses `halfvec_cosine_ops`; downgrade round-tripped back to `vector` + `vector_cosine_ops`; re-upgraded to leave the DB in the migrated state.

- [x] Task 3: Update app code (AC: #1, #7)
  - [x] 3.1 [backend/app/models/embedding.py](../../backend/app/models/embedding.py) — `Vector` → `HALFVEC`, `Vector(1536)` → `HALFVEC(3072)`.
  - [x] 3.2 [backend/app/rag/embeddings.py](../../backend/app/rag/embeddings.py) — module + function docstrings flipped to `text-embedding-3-large` / `3072-dim`; both `model=` kwargs flipped. Function signatures unchanged.
  - [x] 3.3 [backend/app/rag/retriever.py](../../backend/app/rag/retriever.py) — all four `CAST(:embedding AS vector)` → `CAST(:embedding AS halfvec)`.
  - [x] 3.4 Seed re-run succeeded: **46 files, 276 chunks upserted** via OpenAI `text-embedding-3-large`. **No edit to `seed.py:99` required** — pgvector resolved the untyped `'[...]'::vector` literal against the `halfvec(3072)`-typed column natively (the non-scope path in AC #1 held).
  - [x] 3.5 Story 9.6 cutover note appended to [backend/app/rag/seed.py](../../backend/app/rag/seed.py) module docstring.

- [x] Task 4: Run the harness re-run + gate (AC: #2, #5)
  - [x] 4.1 Row count in `document_embeddings` confirmed at 276.
  - [x] 4.2 Harness executed (`uv run pytest tests/eval/rag/ -v -m eval`) — 1 passed, run report written to [backend/tests/fixtures/rag_eval/runs/20260423T161241671347Z.json](../../backend/tests/fixtures/rag_eval/runs/20260423T161241671347Z.json), elapsed ~203 s, tokens 229,305.
  - [x] 4.3 AC #2 gate evaluated — all four deterministic retrieval gates **pass exactly at the spike baseline**: mean p@5 = 0.848 (≥ 0.828 ✓, spike 0.848), uk p@5 = 0.835 (≥ 0.815 ✓, spike 0.835), en p@5 = 0.861 (≥ 0.841 ✓, spike 0.861), mean mrr = 0.957 (≥ 0.937 ✓, spike 0.957). Shortlist rows: `rag-041` gold at rank 1 ✓, `rag-027` gold at rank 2 ✓. Regression-rows gate: **zero regressions** on the 30-row (9.2 ∩ 9.3-3-large) previously-perfect intersection (9.2 alone had 31 perfect rows, one of which was not perfect in the 9.3 3-large spike, so the intersection — the correct "previously-perfect on both sides" set — is 30). Judge overall = 3.848, at the high edge of the informational [3.70, 3.85] band.
  - [x] 4.4 N/A — no hard-fail breaches.
  - [x] 4.5 Run report promoted to [backend/tests/fixtures/rag_eval/baselines/production-text-embedding-3-large.9-6-cutover.json](../../backend/tests/fixtures/rag_eval/baselines/production-text-embedding-3-large.9-6-cutover.json) with sibling `.meta.json`. `corpus_git_sha` captured as `cccdeff874b32e59cb0983dffe0c341fa6ea72ea` (HEAD at run-time).

- [x] Task 5: Update tests (AC: #6)
  - [x] 5.1 [backend/tests/test_embeddings.py](../../backend/tests/test_embeddings.py) rewritten in-place: `test_embed_text_returns_1536_floats` → `test_embed_text_returns_3072_floats`; all `1536` literals → `3072`; all `model="text-embedding-3-small"` → `model="text-embedding-3-large"`. Test count unchanged at 3.
  - [x] 5.2 [backend/tests/test_rag_retrieval.py](../../backend/tests/test_rag_retrieval.py): four `[0.1] * 1536` → `[0.1] * 3072`.
  - [x] 5.3 Targeted run: 7 passed. Full default sweep: **872 passed, 23 deselected** — exact baseline match.

- [x] Task 6: Close TD-079 + optional follow-ups (AC: #9)
  - [x] 6.1 TD-079 status block in [docs/tech-debt.md](../../docs/tech-debt.md#L1205) flipped to `Resolved (Story 9.6, 2026-04-23)` with the Alembic revision and baseline filename inlined. Fix-shape / Where / Surfaced-in blocks preserved.
  - [x] 6.2 No new TDs surfaced: the AC #1 non-scope for `seed.py` held (no `::vector` → `::halfvec` cast failure), so TD-087 is not needed; judge overall 3.848 landed inside the informational [3.70, 3.85] band, so TD-088 is not needed; the alembic head had moved from `z2a3b4c5d6e7` to `a3b4c5d6e7f8` per AC #9(c) but that is captured in Completion Notes, not a TD.
  - [x] 6.3 Skipped decision-doc append (nice-to-have only; the decision doc does not currently have an "Open risks / follow-ups" section under that exact name).

- [x] Task 7: Close-out (AC: #10, #11)
  - [x] 7.1 Final default-sweep pass: **872 passed, 23 deselected** — exact Task 1.1 baseline match.
  - [x] 7.2 Ruff: all checks passed on the seven edited files.
  - [x] 7.3 Mypy: not part of this project's dev dependencies (only `ruff>=0.15.7` is in `pyproject.toml`). Skipped per actual repo tooling; not blocking per `backend/AGENTS.md` de-facto gate. Documented here rather than silently omitted.
  - [x] 7.4 `git diff --stat` sanity: `backend/app/` shows 4 files modified (`models/embedding.py`, `rag/embeddings.py`, `rag/retriever.py`, `rag/seed.py` — the latter is a docstring-only change required by AC #7; the AC #10 "3 files changed" wording is an internal AC inconsistency with AC #7's seed.py note); `backend/alembic/versions/` adds the new revision; `backend/tests/` modifies two tests; `backend/tests/fixtures/rag_eval/baselines/` adds the two new baseline artefacts (required by AC #5); `docs/tech-debt.md` edits TD-079 status.
  - [x] 7.5 Sprint-status flipped `ready-for-dev` → `review` (via `in-progress` during execution). Multi-line pointer comment preserved verbatim.

## Dev Notes

### Why this story looks like "just a model swap"

Because at the code level, it is: 4 files touched in `app/`, 2 test files updated, 1 Alembic revision added. The actual intellectual work happened in Story 9.3 — four candidate embedders measured end-to-end, a strict AC #7b gate that formally failed, and a post-decision diagnostic (separation ratio + Cohere re-chunk) that recalibrated the gate and flipped the recommendation from "stay on 3-small" to "migrate to 3-large". This story is the **execution** of that decision.

The one technical subtlety is **TD-079**: pgvector's native `vector` type HNSW index caps at 2000 dims, and 3-large is 3072. The spike already worked around this via `halfvec(3072)` + `halfvec_cosine_ops` — so this story inherits a known-working shape rather than discovering a new one. The halfvec storage is float16 (2 bytes/dim) vs. vector's float32 (4 bytes/dim); the spike verified that the quantization is quality-neutral at this dim count. AC #2's ±0.02 tolerance is the empirical noise envelope the spike landed within.

### What this story explicitly does NOT do

- **Does not introduce a new embedding abstraction / factory.** `app/rag/embeddings.py` stays a thin OpenAI-client wrapper. A factory parallel to `llm.py` would be speculative (see AC #8).
- **Does not preserve the pre-migration 1536-dim embeddings for rollback.** The `downgrade()` restores the schema; data is rebuilt via seed. See AC #3.
- **Does not add a new pytest marker or CI workflow.** Re-uses Story 9.1's `-m eval` harness verbatim (AC #5).
- **Does not touch Story 9.5c's cross-provider matrix** ([tests/agents/providers/](../../backend/tests/agents/providers/)) — that's LLM-provider scope, embeddings are OpenAI-only on both sides of the migration (AC #8).
- **Does not re-open the Story 9.3 decision gate.** The winner is pinned as `text-embedding-3-large` per the decision doc's Recommendation section.

### Canonical cutover sequence (reproduced from AC #7)

```
cd backend
uv run alembic upgrade head                  # schema now halfvec(3072) + HNSW
python -m app.rag.seed                       # embeds via text-embedding-3-large, ~16s
uv run pytest tests/eval/rag/ -v -m eval     # harness re-run, ~$0.25
# then: promote runs/<timestamp>.json → baselines/production-text-embedding-3-large.9-6-cutover.json
```

### Gate metrics (quick-reference from AC #2)

Post-migration harness run **must** land:
- `mean p@5 ≥ 0.828` (spike 0.848)
- `uk p@5 ≥ 0.815` (spike 0.835)
- `en p@5 ≥ 0.841` (spike 0.861)
- `mean mrr ≥ 0.937` (spike 0.957)
- `rag-041` gold at rank 1; `rag-027` gold at rank ≤ 2
- Zero regressions on the 31-row previously-perfect set
- Judge overall: informational, expected `[3.70, 3.85]`, outside band → Completion Note, not a fail

### Previous story intelligence (9.5c → 9.6)

Story 9.5c landed `872 passed, 20 deselected` on the default sweep. Task 1.1 verifies that baseline before this story starts; AC #6 + AC #10 preserve it. No cross-story code coupling — 9.5c is LLM-provider, 9.6 is embedding-model, the two slots are orthogonal in `llm.py` vs. `embeddings.py`.

### Project Structure Notes

- Alignment with unified project structure: `app/rag/{embeddings,retriever,seed}.py` is the established RAG module layout from Story 3.3; this story makes minimal point-edits to three of those four files and does not rearrange the module.
- Alembic migration convention: new revision goes under `backend/alembic/versions/` following the existing `<hex-prefix>_<snake_case_description>.py` pattern. No deviation.
- Tests convention: `test_embeddings.py` and `test_rag_retrieval.py` are rewritten in-place; no new test files added.

### References

- Story 9.3 decision doc: [docs/decisions/embedding-model-comparison-2026-04.md](../../docs/decisions/embedding-model-comparison-2026-04.md)
- TD-079 (resolved by this story): [docs/tech-debt.md#L1199](../../docs/tech-debt.md#L1199)
- Story 9.3 spike halfvec reference implementation: [backend/tests/eval/rag/candidates/runner.py:111-157](../../backend/tests/eval/rag/candidates/runner.py#L111-L157)
- 3-large spike baseline (target metrics): [backend/tests/fixtures/rag_eval/baselines/text-embedding-3-large.json](../../backend/tests/fixtures/rag_eval/baselines/text-embedding-3-large.json)
- 3-small re-run control baseline: [backend/tests/fixtures/rag_eval/baselines/text-embedding-3-small.9-3-rerun.json](../../backend/tests/fixtures/rag_eval/baselines/text-embedding-3-small.9-3-rerun.json)
- Story 9.1 harness entry: [backend/tests/eval/rag/test_rag_harness.py](../../backend/tests/eval/rag/test_rag_harness.py)
- Current production migration (to be superseded): [backend/alembic/versions/g3h4i5j6k7l8_create_document_embeddings_table.py](../../backend/alembic/versions/g3h4i5j6k7l8_create_document_embeddings_table.py)
- Epics narrative: [_bmad-output/planning-artifacts/epics.md:2064-2065](../../_bmad-output/planning-artifacts/epics.md#L2064-L2065)
- NFR42 (embedding decision-gate rule): `architecture.md` §Technology Stack L294

## Dev Agent Record

### Agent Model Used

Claude Opus 4.7 (1M context) via Claude Code `/bmad-bmm-dev-story`.

### Debug Log References

- Alembic heads pre-migration: `a3b4c5d6e7f8 (head)` — drifted from story's expected `z2a3b4c5d6e7`; new head captured and used as `down_revision` of the new revision.
- Post-migration row count verified: `SELECT COUNT(*) FROM document_embeddings` → `276`.
- Harness run report: `backend/tests/fixtures/rag_eval/runs/20260423T161241671347Z.json`.
- Ruff on all seven edited files: "All checks passed!".
- Full pytest sweep at close-out: `872 passed, 23 deselected, 2 warnings in 201.53s`.

### Completion Notes List

- **AC #2 gate: PASS (deterministic-retrieval).** Observed metrics hit the Story 9.3 spike exactly — mean p@5 0.848 (target ≥ 0.828 ✓, spike 0.848), uk p@5 0.835 (target ≥ 0.815 ✓, spike 0.835), en p@5 0.861 (target ≥ 0.841 ✓, spike 0.861), mean mrr 0.957 (target ≥ 0.937 ✓, spike 0.957). Exact match is unsurprising: production and spike share corpus + chunker + embedder after the migration, so the deterministic metrics converge without drift. Run report: `tests/fixtures/rag_eval/runs/20260423T161241671347Z.json`; promoted baseline: `tests/fixtures/rag_eval/baselines/production-text-embedding-3-large.9-6-cutover.json`.
- **Shortlist gate: PASS.** `rag-041` (`uk/cash-vs-digital-payments`) at rank 1 ✓; `rag-027` (`uk/savings-strategies`) at rank 2 ✓ — both match the spike exactly.
- **Regression-rows gate: PASS (0 regressions).** Correct "previously-perfect" set is the 9.2 ∩ 9.3-3-large intersection = 30 rows (9.2 alone had 31 perfect rows; one of those was not perfect in the 9.3 spike, so the intersection on which zero-regressions is the right gate is 30, not 31). Zero regressions observed on this 30-row set.
- **Judge overall: 3.848** — at the high edge of the informational `[3.70, 3.85]` band; no action required per AC #2.
- **`seed.py` non-scope held (AC #1).** The implicit `'[...]'::vector` → `halfvec(3072)` cast worked natively on pgvector 0.8.x — no edit to [seed.py:99](../../backend/app/rag/seed.py#L99) was necessary. Seed upserted 46 files / 276 chunks successfully. The `seed.py` edit for this story is docstring-only (Story 9.6 cutover note per AC #7).
- **Alembic chain drift (AC #9(c)).** Story-authored expectation `down_revision = "z2a3b4c5d6e7"` was stale; the actual head at Task 1.2 was `a3b4c5d6e7f8` (`widen_bank_format_registry_hint`). New revision `e0f04e4194bc` wires to that head. Not a TD, just a chain-integrity note.
- **Mypy skip.** `mypy` is not a dev dependency in this project's `pyproject.toml` (only `ruff>=0.15.7`). AC #10 mentions a mypy gate, but that is an AC drafting carry-over, not actual repo tooling. Ruff passes cleanly on all seven edited files.
- **`backend/app/` diff footprint.** Four files modified, not three as AC #10 suggested: `models/embedding.py`, `rag/embeddings.py`, `rag/retriever.py`, **plus** `rag/seed.py` (docstring-only edit mandated by AC #7). The AC #10 vs. AC #7 count is internally inconsistent; the seed.py docstring note is a required AC #7 deliverable and is documentation-only.
- **Baseline passed-count invariant.** 872 passed at both Task 1.1 baseline and Task 7.1 final — no test regressions, no new tests added (AC #6).
- **Version bumped 1.37.0 → 1.38.0** (MINOR: new user-facing behavior — RAG retrieval is now on the 3-large embedder, with measurably better paraphrase handling in UK).

### File List

- `backend/alembic/versions/e0f04e4194bc_migrate_document_embeddings_to_halfvec_.py` (added)
- `backend/app/models/embedding.py` (modified)
- `backend/app/rag/embeddings.py` (modified)
- `backend/app/rag/retriever.py` (modified)
- `backend/app/rag/seed.py` (modified — docstring-only note per AC #7)
- `backend/tests/test_embeddings.py` (modified)
- `backend/tests/test_rag_retrieval.py` (modified)
- `backend/tests/fixtures/rag_eval/baselines/production-text-embedding-3-large.9-6-cutover.json` (added)
- `backend/tests/fixtures/rag_eval/baselines/production-text-embedding-3-large.9-6-cutover.meta.json` (added)
- `docs/tech-debt.md` (modified — TD-079 status flipped to Resolved)
- `VERSION` (modified — 1.37.0 → 1.38.0)
- `_bmad-output/implementation-artifacts/sprint-status.yaml` (modified — 9-6 status flipped ready-for-dev → review)
- `_bmad-output/implementation-artifacts/9-6-embedding-migration-conditional.md` (modified — this file: tasks checked, Dev Agent Record + File List + Change Log populated, Status flipped to review)

## Code Review (2026-04-23)

Adversarial review found 3 MEDIUM and 5 LOW findings. 2 MEDIUM auto-fixed (M1, M2), 1 MEDIUM waived (M3 — needs Postgres CI fixture, routed to tech-debt). 1 LOW auto-fixed (L1 — pgvector version guard). Remaining LOW items promoted to tech-debt register.

**Fixed in review:**
- **M1** — [backend/app/rag/seed.py:110](../../backend/app/rag/seed.py#L110): `'...'::vector` → `'...'::halfvec`. Re-seed end-to-end verified (276 rows, alembic round-trip downgrade → upgrade → seed).
- **M2** — [backend/tests/test_rag_retrieval.py](../../backend/tests/test_rag_retrieval.py): added `test_retriever_sql_casts_to_halfvec` invariant test. Default sweep now **873 passed, 23 deselected** (was 872; +1 new invariant test).
- **L1** — [backend/alembic/versions/e0f04e4194bc_migrate_document_embeddings_to_halfvec_.py:32-44](../../backend/alembic/versions/e0f04e4194bc_migrate_document_embeddings_to_halfvec_.py#L32-L44): added pgvector ≥ 0.7.0 pre-flight check in `upgrade()`. Fails with readable `RAISE EXCEPTION` instead of opaque type-not-found error on old pgvector installs.

**Gate re-verified post-fixes:**
- Ruff: all checks pass.
- Default sweep: 873 passed, 23 deselected.
- Alembic round-trip: `downgrade -1` → `upgrade head` → `python -m app.rag.seed` all green.

**Deferred to tech-debt:**
- [TD-089](../../docs/tech-debt.md#td-089) — No CI test for Alembic migration round-trip on `document_embeddings` [MEDIUM, waived — needs Postgres CI fixture].
- [TD-090](../../docs/tech-debt.md#td-090) — `seed.py` uses f-string SQL interpolation for embedding literal [LOW].

**Dropped on reflection:**
- L2 (mypy skip): AC-drafting carryover; already documented in Completion Notes and not worth a TD entry.
- L3 (regression-set size 31 vs 30): documented in Completion Notes; doc drift only, not a real bug.
- L5 (Alembic `DROP TABLE CASCADE` future-proofing): YAGNI until an FK to `document_embeddings.id` actually exists.

## Change Log

| Date       | Version | Change                                                                                                                                                                                                                             |
|------------|---------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| 2026-04-23 | 1.38.0  | Story 9.6: migrated `document_embeddings` from `vector(1536)` / `text-embedding-3-small` to `halfvec(3072)` / `text-embedding-3-large`. TD-079 resolved. AC #2 deterministic-retrieval gate passed at Story 9.3 spike baseline.     |
| 2026-04-23 | 1.38.0  | Version bumped from 1.37.0 to 1.38.0 per story completion (MINOR — RAG retrieval now on winner embedder).                                                                                                                           |
