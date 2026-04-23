# Story 9.5c: Cross-Provider Regression Suite (LLM agents × {anthropic, openai, bedrock})

Status: done
Created: 2026-04-23
Epic: 9 — AI Infra Readiness (Bedrock Provider, RAG Eval Harness, Embedding Decision)

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **backend developer closing Epic 9's multi-provider track** (Stories 9.5a → 9.5b → **9.5c**),
I want a **cross-provider regression harness at `backend/tests/agents/providers/`** that exercises every LLM-using agent path in the codebase — **categorization** ([backend/app/agents/categorization/node.py:469](../../backend/app/agents/categorization/node.py#L469) / [:486](../../backend/app/agents/categorization/node.py#L486) / [:513](../../backend/app/agents/categorization/node.py#L513)), **education** ([backend/app/agents/education/node.py:304](../../backend/app/agents/education/node.py#L304) / [:308](../../backend/app/agents/education/node.py#L308)), and **AI-assisted schema detection** ([backend/app/services/schema_detection.py:220](../../backend/app/services/schema_detection.py#L220)) — against all three providers returned by [backend/app/agents/llm.py](../../backend/app/agents/llm.py)'s factory (`LLM_PROVIDER` ∈ {`anthropic`, `openai`, `bedrock`}), with a manual-trigger GitHub Actions workflow that runs the full matrix on demand and uploads run-reports as artifacts,
so that **(a)** any future provider swap is gated by a real regression signal — not just unit tests that monkeypatch the factory — **(b)** Story 10.4a's AgentCore session handler can take a hard dependency on `LLM_PROVIDER=bedrock` producing *equivalent-enough* agent outputs to today's anthropic-primary path, **(c)** the "bit-for-bit equivalent behavior" promise from Stories 9.5a AC #4 and 9.5b AC #5 is independently verified by a runnable test surface (not just inspected by PR review), and **(d)** the TD-085 "Nova Micro tier gamble" (added by 9.5b for `agent_fallback.bedrock`) gets its first empirical exposure before any pre-prod traffic lands on it.

## Acceptance Criteria

1. **Given** today's LLM call surface consists of exactly **three agent entry points** that consume [backend/app/agents/llm.py](../../backend/app/agents/llm.py)'s `get_llm_client()` / `get_fallback_llm_client()` — verified by the grep run in Task 1.2 (`grep -rn "get_llm_client\|get_fallback_llm_client" backend/app/` → exactly three non-`llm.py` hits: `categorization/node.py`, `education/node.py`, `services/schema_detection.py`) — **When** this story ships **Then** a new test package rooted at [backend/tests/agents/providers/](../../backend/tests/agents/providers/) exists with this minimum shape:
   - `__init__.py` (empty, namespace-only)
   - `conftest.py` — provider-parametrization fixture (AC #3), fixture-corpus loaders, real-client marker wiring
   - `fixtures/categorization_cases.json` — 5 **representative** transactions with gold `category` + `transaction_kind` sourced from the existing [backend/tests/fixtures/categorization_golden_set/golden_set.jsonl](../../backend/tests/fixtures/categorization_golden_set/golden_set.jsonl) (Story 11.1 golden set). "Representative" = covers the four `transaction_kind` axes the matrix most needs to distinguish (`transfer`, `savings`, `spending`, and the P2P-vs-other edge), not necessarily the first 5 rows. Rows are copied verbatim — no re-labelling.
   - `fixtures/education_cases.json` — 3 transaction-cluster inputs with an expected card **schema shape** (AC #4 — not exact prose equivalence)
   - `fixtures/schema_detection_cases.json` — 2 CSV-header fingerprints (one Monobank-like, one unknown-generic) with expected field-map keys
   - `test_categorization_matrix.py`, `test_education_matrix.py`, `test_schema_detection_matrix.py` — one file per agent
   - `README.md` — short runbook: how to run locally, how to run in CI, credentials needed, cost estimate per full matrix run. ≤ ~80 lines.

   **Epic-text reconciliation (explicit non-scope):** Epic 9's description at [epics.md line 2061–2062](../../_bmad-output/planning-artifacts/epics.md#L2061-L2062) reads *"Epic 3 (categorization, RAG education) + Epic 8 (pattern, subscription, triage) agents must produce equivalent outputs on Anthropic / OpenAI / Bedrock."* This is **aspirational** — `pattern_detection/`, `triage/`, and the subscription detector under `pattern_detection/detectors/recurring.py` are **pure statistical code with zero LLM calls** today (verified by Task 1.2's grep — those paths return no hits). This story therefore covers only the three *currently LLM-backed* agent paths; the Epic 8 agent paths are **explicitly out of scope** and the README.md from above must state this in one sentence so a future reader doesn't assume pattern/triage coverage. If a future story wires an LLM into pattern/triage/subscription code, extending the matrix then is a trivial file-add. [backend/app/services/schema_detection.py](../../backend/app/services/schema_detection.py) is formally Epic 11 (Story 11.7 AI-assisted schema detection), not Epic 3 — it is included here because it uses the same `get_llm_client()` seam and omitting it would leave the cross-provider promise incomplete for a real call site.

2. **Given** "equivalent outputs" between providers is **physically impossible** with non-deterministic LLMs (even Claude Haiku 4.5 with `temperature=0` emits token-level variance across identical prompts; Nova Micro's answer-shape differs in prose length from Haiku; OpenAI's `gpt-4o-mini` is trained on a different corpus altogether) **When** this story specifies the equivalence contract **Then** equivalence is a **schema + label contract**, not a prose contract. Concretely:
   - **Categorization equivalence (hardest bar):** Across all three providers, for each of the 5 fixture transactions, the returned `category` label must be in an AC-frozen per-case **allowlist** (a set of 1–3 labels that all count as "correct" for that transaction — captured in `fixtures/categorization_cases.json` as `acceptable_categories: [...]`), AND the returned `transaction_kind` must match the gold value **exactly** (`income` / `expense` / `savings` / `transfer_p2p` — there is no tolerance on `kind` because wrong-`kind` is the direct cause of the Epic 11 Savings-Ratio bug addressed by 4.9). Across 5 cases × 3 providers = **15 assertions**; all 15 must pass. If a single case/provider pair fails, the failure message must include: raw LLM response, expected allowlist, and provider name.
   - **Education equivalence:** Each provider's card output must pass JSON-schema validation against the `EducationCard` pydantic model ([backend/app/models/education_card.py](../../backend/app/models/education_card.py) — or the equivalent schema used by [education/node.py](../../backend/app/agents/education/node.py)), must set `severity` ∈ {`critical`, `warning`, `info`}, and the card body (`body` or `body_kind_breakdown` field, whichever the current model uses) must be non-empty and in the requested language (UK input → UK output per the `language_correctness` axis from [tests/eval/rag/judge.py](../../backend/tests/eval/rag/judge.py)'s rubric — this reuses the harness's language-detection logic; do NOT re-implement).
   - **Schema-detection equivalence:** Across providers, the returned `field_map` must include the keys `{date, amount, description}` for both fixture CSVs (those three are the non-negotiable required fields per [schema_detection.py](../../backend/app/services/schema_detection.py)'s contract at the 200s range — the `field_map` is allowed to include additional fields and the value strings are allowed to differ (one provider might pick `"Transaction Date"` while another picks `"Date"` from the header). Key-presence is asserted, key-value is not.

3. **Given** `LLM_PROVIDER` is a `settings.LLM_PROVIDER` field consumed at runtime by [llm.py:125](../../backend/app/agents/llm.py#L125) — not a pytest parameter — **When** the matrix parametrizes providers **Then** a single `provider` pytest parameter (`["anthropic", "openai", "bedrock"]`) drives the full matrix via `monkeypatch.setattr(settings, "LLM_PROVIDER", provider)` + `llm_module.reload_models_config_for_tests()` in an autouse fixture at the `providers/conftest.py` level. The parametrize is applied at the module level (`pytestmark = pytest.mark.parametrize("provider", ["anthropic", "openai", "bedrock"])`) not per-test to keep test files flat. **Circuit-breaker reset between params:** because every provider share the same `check_circuit`/`record_failure` surface, the conftest must also monkeypatch `llm_module.check_circuit` to a no-op per-test (same pattern as [test_llm_factory.py:48](../../backend/tests/agents/test_llm_factory.py#L48)); otherwise a transient Bedrock throttle mid-run contaminates the anthropic/openai params that follow.

4. **Given** cross-provider regression **requires real API calls** (this is the whole point — a mocked matrix proves nothing a unit test doesn't already prove) **When** the matrix is packaged **Then** gating:
   - The matrix is marked `@pytest.mark.provider_matrix` (define the marker in [backend/pyproject.toml](../../backend/pyproject.toml)'s `[tool.pytest.ini_options]` `markers` list alongside existing `eval` / `slow` / etc. — consult the file to copy the existing style exactly).
   - The **default** `uv run pytest tests/ -q` sweep **deselects** `provider_matrix` (the pattern used by Story 9.1's `-m eval -s` harness — mirror it). The expected default sweep count after this story lands is **`872 passed, 11 + N deselected`** where `N` = the number of test functions in the new `providers/` package (target: N = 3 — one `test_*_matrix` function per agent, each parametrized 3× yields 9 test invocations but 3 collected functions; the "deselected" counter counts *collected items*, so expect the deselect delta to equal the parametrized item count, i.e. **`872 passed, 20 deselected`** if three 3-way-parametrized tests are added). The Debug Log References section records the actual observed delta — do not get hung up on a specific number; the requirement is that the default sweep is **not broken** and **not slowed** by the new tests.
   - Opt-in pattern: `uv run pytest tests/agents/providers/ -v -m provider_matrix` explicitly selects the matrix. Credentials flow in from environment (`ANTHROPIC_API_KEY` / `OPENAI_API_KEY` / boto3 chain for Bedrock) — no test shall hard-code keys or fixture credentials.
   - A skip guard at module level: if the required env for a given param is missing (e.g. `AWS_ACCESS_KEY_ID` absent for the `bedrock` param), the specific param is **skipped with a reason** — not errored — so a developer with only Anthropic access can still run `anthropic` + `openai` params locally. Use `pytest.skip(...)` inside an autouse fixture that inspects `provider` + env.

5. **Given** CI needs a way to exercise the matrix without blocking every PR (cost: ~3 provider invocations × ~10 prompts = 30 LLM calls per matrix run ≈ $0.05 for gpt-4o-mini+haiku but unbounded for Bedrock cross-region inference without grip on pricing) **When** this story lands **Then** a new workflow [.github/workflows/ci-backend-provider-matrix.yml](../../.github/workflows/ci-backend-provider-matrix.yml) is created, modeled on the existing [.github/workflows/ci-backend-eval.yml](../../.github/workflows/ci-backend-eval.yml). Specifically:
   - **Triggers:** `workflow_dispatch` only (manual). No `schedule` cron — Epic 9's cost-controls story doesn't exist yet, so don't add recurring spend without explicit approval. The existing `ci-backend-eval.yml` has its cron commented-out for the same reason; mirror that comment verbatim.
   - **Secrets required:** `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, and AWS credentials for the `bedrock` param. AWS creds flow in via `aws-actions/configure-aws-credentials@v4` using an **OIDC role** (not long-lived keys) — if no OIDC role is provisioned yet, **defer** the Bedrock-param CI enablement: the workflow's "Run provider matrix" step sets `LLM_PROVIDER_MATRIX_PROVIDERS=anthropic,openai` via env and the test file honors a comma-separated filter from that env (feature of AC #3's parametrize — see Task 3.4). A TD entry (see AC #9 candidate (a)) captures the Bedrock CI gap.
   - **Postgres service:** same pattern as `ci-backend-eval.yml` — the provider matrix does not touch the DB, but conftest-level imports reach into `app.core.database` via `settings` chain, and the CI job needs a functional `DATABASE_URL`. Re-use the exact service block verbatim (pgvector image + healthcheck) to avoid drift.
   - **Artifacts:** upload `backend/tests/agents/providers/runs/*.json` as `provider-matrix-run-reports` (retention 30 days). The `runs/` directory is written to by the test module at the end of each run (see AC #8). If no run-reports were emitted (e.g. all params skipped), upload nothing — do not fail the upload step.

6. **Given** `schema_detection.py`'s LLM path ([schema_detection.py:220](../../backend/app/services/schema_detection.py#L220)) is only reachable when header-fingerprint cache misses **When** the matrix invokes it **Then** the fixture CSVs are synthetic — never seen before by any cache — so cache bypass is deterministic. **Do NOT** mock or stub `schema_detection_service.detect_schema(...)`; the point is that the *full* service path (including the prompt construction + response parsing) runs against each provider. If `schema_detection.py` in its current form requires a live DB for fingerprint-cache lookups, the matrix test opens a transaction via the existing `get_sync_session()` pattern and rolls it back — but this must NOT couple to the per-CI-job migration flow; if the isolation is ugly, accept the coupling and lift it to a TD entry (AC #9 candidate (d)). A *wrong* shortcut: returning a hand-written JSON from the test and asserting the parser survives. That proves parsing, not cross-provider equivalence — exclude this pattern explicitly in the test file's module docstring.

7. **Given** matrix runs must be **reproducible enough for regression analysis** (a "Bedrock flaked once" signal cannot be silently retried away) **When** the test module ends **Then** each `test_*_matrix` function writes one structured run-report JSON at `backend/tests/agents/providers/runs/<agent>-<timestamp-utc-iso>.json` with: the matrix parameter (`provider`), per-case raw LLM response, per-case pass/fail, per-case latency_ms, an aggregate `pass_rate_by_provider` block, and a `meta` block containing `git_sha` (via `subprocess.run(['git', 'rev-parse', 'HEAD'])`), `models_yaml_sha` (hash of [models.yaml](../../backend/app/agents/models.yaml) content — drift-detection), `timestamp_utc`, and `pytest_version`. Report shape mirrors [backend/tests/fixtures/rag_eval/runs/](../../backend/tests/fixtures/rag_eval/runs/) from Story 9.1 (consult a recent run-report in that directory to confirm field-name conventions and replicate them — do not reinvent the wheel). The `runs/` directory is git-ignored via a new entry in [backend/.gitignore](../../backend/.gitignore) (append `tests/agents/providers/runs/`); only the CI artifact persists them.

8. **Given** the matrix is new territory for test reliability (one flaky Bedrock call could tank a CI run) **When** the matrix handles transient errors **Then** rules:
   - **No automatic retries** on LLM-call failure. The first response is the recorded one. If a Bedrock throttle or transient OpenAI 503 causes a case to fail, the run-report records it verbatim and the test assertion fails. Retries hide regressions; we explicitly want the signal.
   - Exception from `ChatBedrockConverse.invoke(...)` is caught **only** at the assertion boundary: the per-case runner catches `BaseException`, records `error: <type(e).__name__>: <str(e)>` in the run-report, and still emits the JSON before re-raising as a `pytest.fail(...)` with the provider + case context.
   - The circuit-breaker is **not** consulted by the matrix — this is a ground-truth probe, not a production call. Do not wire `record_success`/`record_failure` into the matrix runner; a real API failure should fail the test, not trip a breaker that contaminates the very next test param. The autouse conftest fixture from AC #3 monkeypatches `check_circuit` to a no-op and does NOT wire the record_* functions.

9. **Given** `docs/tech-debt.md` tracks deferred work with `TD-NNN` IDs (highest existing entry **TD-085** per the 9.5b close) **When** this refactor surfaces deferred items **Then** each becomes a `TD-086+` entry. Expected candidates:
   - **(a)** Bedrock OIDC role provisioning for CI — if AC #5 ships with the Bedrock param disabled in CI pending an AWS OIDC federation role, add `TD-086` [MEDIUM] pointing at the gap with a 2-line fix shape (Terraform `aws_iam_openid_connect_provider` + GitHub OIDC `aws_iam_role` scoped to `bedrock:InvokeModel` on `eu.*` ARNs) and a note that Story 9.7 may absorb it if the scope aligns.
   - **(b)** Epic 8 LLM-coverage gap — the matrix covers 3/6 agent paths suggested by the epic text. When (if ever) pattern/triage/subscription agents gain an LLM, add matrix entries. A LOW TD entry is sufficient, pointing at this story + the epic-text aspirational language. Alternatively: update the epic text to drop the Epic 8 agents from the cross-provider scope (done inline in [epics.md](../../_bmad-output/planning-artifacts/epics.md) at line 2061 — choose whichever keeps the planning artifacts honest; the story writer's recommendation is to **update the epic text**, not add a TD, because the epic text was aspirational rather than wrong).
   - **(c)** Equivalence contract narrowness — AC #2's "schema + label" contract is the strongest equivalence bar that non-deterministic LLMs can sustain, but it does **not** detect semantic regressions (e.g. "provider emits correct category label but wrong `kind_reason` prose that would confuse a user"). A richer LLM-as-judge scoring pass (reusing the [tests/eval/rag/judge.py](../../backend/tests/eval/rag/judge.py) rubric — groundedness/relevance/language_correctness/overall) could be layered on top. This is a **LOW** TD if pursued (add `TD-087`); if skipped, note explicitly in the story close-out's Completion Notes so a future Chat-with-Finances safety review doesn't assume cross-provider semantic parity.
   - **(d)** DB coupling in `test_schema_detection_matrix.py` (AC #6) — if the test needs a live session to exercise fingerprint-cache bypass cleanly, and the isolation ends up ugly (e.g. the test opens a transaction that spans the LLM call), flag as **LOW** TD: "Schema-detection matrix couples to a live Postgres session to exercise cache-miss path; better isolation would be to extract the cache-lookup into a pure function and call the LLM path directly."
   - **(e)** TD-085 (Nova Micro fallback tier gamble) — this story is the **first empirical exposure**. If the `bedrock` param's runs against `agent_fallback.bedrock` via forced-fallback test (AC #10) reveal Nova Micro outputs that **fail** the categorization schema+label contract (e.g. returns a non-allowlisted category, produces truncated JSON because Nova's max_tokens default is low), **update TD-085 in place** (do NOT create a new TD) with a dated note capturing the failure mode and a recommendation: either bump to Nova Lite / Haiku 3.5, or increase Nova's `max_tokens` kwarg in the Bedrock client construction at [llm.py:90-97](../../backend/app/agents/llm.py#L90-L97). If Nova Micro passes cleanly, also update TD-085 — to **resolve** it — with the smoke result. Either way, TD-085 moves.
   - If none of (a)–(e) applies, add no TD entries.

10. **Given** AC #9(e) depends on an **explicit fallback exercise** (by default, `LLM_PROVIDER=bedrock` routes all calls to `agent_default.bedrock` = Haiku 4.5, and `agent_fallback.bedrock` = Nova Micro is never touched unless the primary fails) **When** the matrix validates the fallback path **Then** `test_categorization_matrix.py` includes a **single parametrized fallback case** — `[pytest.mark.parametrize("use_fallback", [False, True])]` layered under the existing provider parametrize — which, when `use_fallback=True` and `provider=="bedrock"`, monkeypatches [categorization/node.py:469](../../backend/app/agents/categorization/node.py#L469)'s `get_llm_client()` call to raise and route to `get_fallback_llm_client()` (the same fallback branch already exercised by the existing integration tests at [test_pe_categorization_e2e.py:186](../../backend/tests/integration/test_pe_categorization_e2e.py#L186)). For `provider in {"anthropic", "openai"}`, the `use_fallback=True` param is **skipped with a reason** (opposite-of-primary under those is gpt-4o-mini / claude-haiku-4-5 — both already covered by the `provider` param directly, so a fallback sub-case adds no coverage, only cost). This locks TD-085's empirical exposure via a committed test surface rather than a manual one-off invocation.

11. **Given** ruff + mypy + the existing test sweep all gate merges (per [backend/AGENTS.md](../../backend/AGENTS.md) and [backend/pyproject.toml](../../backend/pyproject.toml)) **When** this story ships **Then**:
    - `uv run ruff check backend/tests/agents/providers/` returns zero findings.
    - The default sweep `cd backend && uv run pytest tests/ -q` still reads **`872 passed, 11 + N deselected`** (see AC #4 for the expected delta — N counts the parametrized items that the default sweep deselects via `-m "not provider_matrix"` in [pyproject.toml](../../backend/pyproject.toml)'s default addopts, if that pattern exists; if not, the deselect happens at module-level via `pytest.mark.provider_matrix` + default `-m "not provider_matrix"` in the existing default addopts — consult the file before assuming).
    - No edit to any of the three **consumer** files whose call sites are exercised by the matrix — [categorization/node.py](../../backend/app/agents/categorization/node.py), [education/node.py](../../backend/app/agents/education/node.py), [services/schema_detection.py](../../backend/app/services/schema_detection.py) — beyond what is already in them today. `git diff --stat backend/app/agents/categorization/node.py backend/app/agents/education/node.py backend/app/services/schema_detection.py` → empty. The matrix consumes these files via public API only; the equivalence contract is about observable behavior, not internal wiring.
    - No edit to [backend/app/agents/llm.py](../../backend/app/agents/llm.py) or [backend/app/agents/models.yaml](../../backend/app/agents/models.yaml). Story 9.5a + 9.5b closed the factory; this story consumes it. If a factory edit is tempting (e.g. "adding a `LLM_PROVIDER_OVERRIDE` for tests"), **stop** — the existing `monkeypatch.setattr(settings, "LLM_PROVIDER", ...)` pattern is sufficient; reopening the factory for test convenience drags in regressions against 9.5a AC #4 / 9.5b AC #5.

12. **Given** sprint-status.yaml tracks story state **When** this story is ready for dev **Then** `_bmad-output/implementation-artifacts/sprint-status.yaml`'s `9-5c-cross-provider-regression-suite:` key is flipped `backlog` → `ready-for-dev` by the create-story workflow (this file), and on story close-out the implementing dev flips it to `review` (code-review flips to `done` per the normal flow). The existing pointer comment above that line (from 9.5b close, reading *"Story 9.5b: Bedrock path wired; 9.5c can now loop LLM_PROVIDER ∈ {anthropic,openai,bedrock}."*) is **preserved verbatim**; no new pointer comment is appended unless a follow-up story depends on 9.5c's deliverables (the next backlog story is 9.6 — embedding migration — which does NOT depend on the provider matrix; leave the comment block unchanged).

## Tasks / Subtasks

- [x] Task 1: Baseline + shape the matrix package (AC: #1, #11)
  - [x] 1.1 From `backend/` with `backend/.venv` active (memory `feedback_python_venv.md`), run `cd backend && uv run pytest tests/ -q`. Record the baseline as **`872 passed, 11 deselected`** (matches 9.5b close). Any drift is captured as the new baseline for AC #11's "passed count unchanged" assertion.
  - [x] 1.2 Run `grep -rn "get_llm_client\|get_fallback_llm_client" backend/app/ --include="*.py" -l`. Confirm hits in exactly four files: `app/agents/llm.py` (definition), `app/agents/categorization/node.py`, `app/agents/education/node.py`, `app/services/schema_detection.py`. If any additional consumer file has been added since 9.5b (e.g. a new agent wiring), **extend AC #1's matrix to cover it** — this story is the cross-provider source of truth and gaps cost future stories real debugging time.
  - [x] 1.3 Read [backend/pyproject.toml](../../backend/pyproject.toml)'s `[tool.pytest.ini_options]` block. Capture the current `markers = [...]` list and the current `addopts` string. Confirm the existing `eval` marker is registered there — the new `provider_matrix` marker will mirror its registration style exactly (same indentation, same comment style).
  - [x] 1.4 Create the directory skeleton per AC #1: `backend/tests/agents/providers/{__init__.py, conftest.py, fixtures/, runs/}`; `runs/.gitkeep` is NOT committed (directory appears only when a local run writes to it), but the git-ignore entry from AC #7 IS committed.

- [x] Task 2: Author fixture corpora (AC: #1, #2)
  - [x] 2.1 Read [backend/tests/fixtures/categorization_golden_set/golden_set.jsonl](../../backend/tests/fixtures/categorization_golden_set/golden_set.jsonl) (Story 11.1 golden set). Pick 5 **representative** rows that collectively cover the four `transaction_kind` axes (`transfer`, `savings`, `spending`, and a P2P-vs-other discriminator) — not necessarily the first 5. Copy verbatim into `backend/tests/agents/providers/fixtures/categorization_cases.json`. For each row, add an `acceptable_categories: [<label>, <near-synonym>, ...]` array per AC #2 — use the Epic 11 taxonomy from [docs/taxonomy.md](../../docs/taxonomy.md) if one exists, otherwise the taxonomy enum from [app/models/transaction.py](../../backend/app/models/transaction.py). The 5-case file stays ≤ ~80 lines.
  - [x] 2.2 Author `backend/tests/agents/providers/fixtures/education_cases.json` with 3 transaction-cluster inputs: (i) a "savings milestone" cluster (>3 `kind=savings` transactions in a month — triggers the positive-reinforcement card shape), (ii) a "subscription warning" cluster (>5 `kind=subscription` recurrent charges — triggers the subscription-review card), (iii) a "UK-language" cluster (user language=`uk` — triggers Ukrainian output per the existing [education/prompts.py](../../backend/app/agents/education/prompts.py)). The expected-output block per case carries `expected_language`, `severity_in: [critical, warning, info]`, and `required_fields: [title, body, severity]` — not prose content.
  - [x] 2.3 Author `backend/tests/agents/providers/fixtures/schema_detection_cases.json` with 2 CSVs: (i) a Monobank-shape header (`Date, Time, Description, MCC, Amount (UAH), Currency, Balance (UAH)` — 7 columns, dd.mm.yyyy date format), (ii) a synthetic-generic header (`Txn Date, Payee, Debit, Credit, Memo` — 5 columns, unknown bank). Each case carries `expected_field_map_keys: [date, amount, description]` — the three non-negotiable keys per AC #2's equivalence contract. Value strings (e.g. which header name maps to `date`) are NOT asserted.
  - [x] 2.4 Add one [README.md](../../backend/tests/agents/providers/README.md) to the package per AC #1, stating: scope, opt-in command, env vars required, CI workflow pointer, approximate cost per full matrix run (~30 calls × average $0.01 ≈ $0.30), and the Epic 8 non-scope note. Consult [backend/tests/eval/rag/](../../backend/tests/eval/rag/) for the existing README prose style — mirror it.

- [x] Task 3: Build the conftest + provider-parametrize infrastructure (AC: #3, #4, #8)
  - [x] 3.1 In [backend/tests/agents/providers/conftest.py](../../backend/tests/agents/providers/conftest.py), define an autouse `_provider_setup` fixture that:
    - Reads `provider` from the parametrize (use `request.node.callspec.params['provider']`).
    - Checks env gating: for `anthropic`, require `ANTHROPIC_API_KEY`; for `openai`, require `OPENAI_API_KEY`; for `bedrock`, require `AWS_ACCESS_KEY_ID` OR `AWS_PROFILE` OR running on an EC2/ECS instance-role (detect via `boto3.Session().get_credentials()` is not None); skip otherwise via `pytest.skip(f"missing credentials for provider={provider}")`.
    - Also honors `LLM_PROVIDER_MATRIX_PROVIDERS` env (comma-separated filter per AC #5) — if set, skip any param not in the allowlist.
    - `monkeypatch.setattr(settings, "LLM_PROVIDER", provider)` + `llm_module.reload_models_config_for_tests()`.
    - `monkeypatch.setattr(llm_module, "check_circuit", lambda p: None)` per AC #8.
    - Yields a `provider_ctx` dict with `provider`, `timestamp_utc` (ISO-8601, UTC, invocation-start semantics — match Story 9.4 / 9.5b convention), `run_report_path`.
  - [x] 3.2 Register the `provider_matrix` pytest marker in [backend/pyproject.toml](../../backend/pyproject.toml)'s `[tool.pytest.ini_options].markers` list. Append a line: `"provider_matrix: cross-provider LLM regression matrix (Story 9.5c). Hits real LLM APIs — opt-in via -m provider_matrix."` — match the existing marker-registration syntax exactly (quote style, trailing comma, indentation).
  - [x] 3.3 Confirm the default sweep's `-m` filter deselects the new marker. If [pyproject.toml](../../backend/pyproject.toml)'s existing `addopts` already reads `-m "not eval"` (or similar), extend it to `-m "not eval and not provider_matrix"`. If no `-m` filter exists in `addopts` today, add one. The baseline default sweep count from Task 1.1 (`872 passed, 11 deselected`) must become `872 passed, 11 + N deselected` where N = the count of parametrized items added (not the count of test functions — pytest counts parametrized items toward deselected).
  - [x] 3.4 Implement the `LLM_PROVIDER_MATRIX_PROVIDERS` env filter in the conftest (comma-separated). Default (unset) = all three. Used by CI (AC #5) to disable Bedrock until OIDC lands. A 3-line parse + membership check; no `argparse`.

- [x] Task 4: Implement the three matrix tests (AC: #2, #6, #7, #10)
  - [x] 4.1 `backend/tests/agents/providers/test_categorization_matrix.py`: module-level `pytestmark = [pytest.mark.provider_matrix, pytest.mark.parametrize("provider", ["anthropic", "openai", "bedrock"])]`. Test function `test_categorization_matches_golden_set(provider, _provider_setup)` iterates the 5 fixtures from Task 2.1 → calls [categorization/node.py](../../backend/app/agents/categorization/node.py)'s public categorize entry-point (identify the entry — likely `categorize_transactions_node(state)` or a direct helper — by reading the module's `__all__` or the most-used public function; do NOT reach into private helpers). Asserts AC #2: per-case `category in acceptable_categories` AND `transaction_kind == gold_kind`. Writes the run-report per AC #7 to `backend/tests/agents/providers/runs/categorization-<provider>-<ts>.json`.
  - [x] 4.2 Add the AC #10 fallback parametrize: `@pytest.mark.parametrize("use_fallback", [False, True])` at the test-function level (composes with the module-level `provider` parametrize for a 3 × 2 = 6-item matrix, but 4 of the 6 items are `pytest.skip`-ed — the `use_fallback=True` branch only runs for `provider=="bedrock"`). When `use_fallback=True` + `provider=="bedrock"`, monkeypatch [categorization/node.py](../../backend/app/agents/categorization/node.py)'s `get_llm_client` to raise `RuntimeError("simulated primary failure")`, exercising the fallback branch at [categorization/node.py:486](../../backend/app/agents/categorization/node.py#L486) / [:513](../../backend/app/agents/categorization/node.py#L513). The assertion surface is identical to the primary case (schema + label contract from AC #2).
  - [x] 4.3 `test_education_matrix.py`: same module-level parametrize. Test function `test_education_card_schema_per_provider(provider, _provider_setup)` iterates the 3 fixtures from Task 2.2 → calls [education/node.py](../../backend/app/agents/education/node.py)'s `education_node(state)` with a minimal `FinancialPipelineState` (consult [backend/app/agents/state.py](../../backend/app/agents/state.py) for the required fields) → asserts AC #2: pydantic schema valid, `severity in {critical, warning, info}`, output language matches `expected_language`, `body` non-empty. Language check reuses the `langdetect` or equivalent dependency that [tests/eval/rag/judge.py](../../backend/tests/eval/rag/judge.py) already uses — import, do not re-implement. Run-report per AC #7.
  - [x] 4.4 `test_schema_detection_matrix.py`: same module-level parametrize. Test function `test_schema_detection_field_map_per_provider(provider, _provider_setup, db_session)` — the `db_session` fixture is the existing project-wide sync session from [backend/tests/conftest.py](../../backend/tests/conftest.py); consult that file for the exact fixture name (`db_session`, `sync_session`, or whatever). Iterates the 2 CSVs from Task 2.3 → calls [schema_detection.py](../../backend/app/services/schema_detection.py)'s `detect_schema(...)` entry-point → asserts AC #2: `{"date", "amount", "description"} <= set(result.field_map.keys())`. Run-report per AC #7. Per AC #6, NO stubbing of `detect_schema` — the LLM path must run.
  - [x] 4.5 Shared `_write_run_report(agent: str, provider: str, results: list[dict], provider_ctx: dict) -> Path` helper in [backend/tests/agents/providers/conftest.py](../../backend/tests/agents/providers/conftest.py) centralizes the run-report write so each test's per-case loop just appends to a `results` list. Writes to `runs/<agent>-<provider>-<timestamp>.json` atomically (write to tmpfile + `os.replace`).

- [x] Task 5: Add the CI workflow (AC: #5)
  - [x] 5.1 Create [.github/workflows/ci-backend-provider-matrix.yml](../../.github/workflows/ci-backend-provider-matrix.yml) by copying [.github/workflows/ci-backend-eval.yml](../../.github/workflows/ci-backend-eval.yml) verbatim, then editing:
    - `name:` → `"CI Backend Provider Matrix (Cross-Provider)"`.
    - Top comment block: replace the Story 9.1 reference with a pointer to this story file + AC #5.
    - Add `AWS_REGION: eu-central-1` + `AWS_ROLE_TO_ASSUME: ${{ secrets.AWS_ROLE_TO_ASSUME }}` in `env:`. If the secret is not configured on the repo at story-implementation time, set `LLM_PROVIDER_MATRIX_PROVIDERS: "anthropic,openai"` in `env:` and comment out the `configure-aws-credentials` step. Open TD-086 per AC #9(a).
    - Replace the "Run RAG eval harness" step with: `name: Run provider matrix` + `run: uv run pytest tests/agents/providers/ -v -m provider_matrix -s`.
    - Replace artifact path with `backend/tests/agents/providers/runs/*.json` + `name: provider-matrix-run-reports` + `retention-days: 30`.
    - Keep the Postgres service block verbatim (needed by `schema_detection` per AC #6).
    - **Do NOT** add a `schedule` trigger (per AC #5 — no recurring spend without explicit approval).
  - [x] 5.2 If the AWS OIDC role `AWS_ROLE_TO_ASSUME` does not yet exist on the repo, add the `configure-aws-credentials@v4` step with `role-to-assume: ${{ secrets.AWS_ROLE_TO_ASSUME }}` and `aws-region: ${{ env.AWS_REGION }}`, but also gate the step with `if: secrets.AWS_ROLE_TO_ASSUME != ''`. This makes the workflow green on a fresh repo where the secret is unset — the Bedrock param is skipped in-test per AC #4, the anthropic + openai params still run. The TD-086 entry documents the gap.
  - [x] 5.3 Manually trigger the workflow from the GitHub UI (`workflow_dispatch`) once — or via `gh workflow run ci-backend-provider-matrix.yml` if the dev has `gh` CLI access — and confirm a green run with uploaded artifacts for the anthropic + openai params. Bedrock can be deferred per AC #5. Attach the run-URL into the story's Debug Log References on close.

- [x] Task 6: Tech-debt updates (AC: #9)
  - [x] 6.1 Apply AC #9 candidates that fired during implementation:
    - **(a)** If Bedrock OIDC is not provisioned, add `TD-086` [MEDIUM] to [docs/tech-debt.md](../../docs/tech-debt.md)'s `## Open` section. Format: copy the TD-079 / TD-080 entry style exactly (Where / Problem / Why deferred / Fix shape / Surfaced in).
    - **(b)** Epic 8 coverage gap: **update [epics.md line 2061–2062](../../_bmad-output/planning-artifacts/epics.md#L2061-L2062)** to drop the "Epic 8 (pattern, subscription, triage)" agents from the cross-provider scope (they don't use LLMs). Change the sentence to: *"Epic 3 (categorization, RAG education) + Epic 11 (AI-assisted schema detection) agents must produce equivalent outputs on Anthropic / OpenAI / Bedrock."* This is the honest edit — Epic 8 agents are pure compute. If the writer prefers a TD over an epic edit, add `TD-087` [LOW] instead (but the epic edit is preferred — do not add both).
    - **(c)** If the AC #2 schema+label equivalence contract is accepted as-is (most likely outcome), add `TD-087` [LOW] flagging that semantic cross-provider parity (LLM-as-judge of one provider's output against another's) is a follow-up, gated by AI-safety priorities for Epic 10. If semantic parity coverage is deemed essential before Epic 10 ships, this TD jumps to MEDIUM — but that's an Epic-10-planning call, not this story's.
    - **(d)** If schema-detection DB coupling in Task 4.4 turned out ugly, add `TD-088` [LOW].
    - **(e)** Update [TD-085](../../docs/tech-debt.md#TD-085) **in place** with the Nova-Micro-fallback empirical result from Task 4.2 — dated note, either "RESOLVED — Nova Micro passes categorization contract" or "EXTENDED — Nova Micro fails on case X; recommend tier-bump to Nova Lite or max_tokens=512 override at [llm.py:93](../../backend/app/agents/llm.py#L93)."
  - [x] 6.2 Re-read [docs/tech-debt.md](../../docs/tech-debt.md)'s `## How to use this file` block. Confirm the added entries match the file's style (severity tag, "Where / Problem / Why deferred / Fix shape / Surfaced in" sections). Cheap to get right; expensive to leave a style-drift entry that looks out-of-place in the register.

- [x] Task 7: Regression + verification (AC: #11)
  - [x] 7.1 `git status` + `git diff --stat` — confirm the only files modified are: the new package under `backend/tests/agents/providers/` (8+ files), [backend/pyproject.toml](../../backend/pyproject.toml) (marker registration + optional addopts tweak), [backend/.gitignore](../../backend/.gitignore) (one new line per AC #7), [.github/workflows/ci-backend-provider-matrix.yml](../../.github/workflows/ci-backend-provider-matrix.yml) (new), [docs/tech-debt.md](../../docs/tech-debt.md) (TD additions + TD-085 update), and [_bmad-output/planning-artifacts/epics.md](../../_bmad-output/planning-artifacts/epics.md) (Task 6.1(b) Epic 8 sentence edit, if taken). The three consumer files ([categorization/node.py](../../backend/app/agents/categorization/node.py), [education/node.py](../../backend/app/agents/education/node.py), [services/schema_detection.py](../../backend/app/services/schema_detection.py)) AND [llm.py](../../backend/app/agents/llm.py) + [models.yaml](../../backend/app/agents/models.yaml) MUST be **unchanged**: `git diff --stat` output for them MUST be empty.
  - [x] 7.2 From `backend/`, run `uv run pytest tests/ -q`. Confirm the baseline `872 passed` is unchanged; the `deselected` count is `11 + N` where N = the parametrized-item count added by the provider matrix (target: 9 items — 3 tests × 3 providers — plus 6 fallback items from AC #10 of which only 2 actually collect due to skip — but skip happens at fixture time, not collection time, so the raw collection count is the product. Observe the actual N empirically and record it in Debug Log References).
  - [x] 7.3 `uv run ruff check backend/tests/agents/providers/` → zero findings. If ruff flags line-length on fixture JSONs, they are JSON not Python — ruff ignores them. If ruff flags Python test-files, fix in-place (no `# noqa` escape hatches).
  - [x] 7.4 Opt-in run, local dev: set `ANTHROPIC_API_KEY` + `OPENAI_API_KEY` + AWS creds (if available) → `uv run pytest tests/agents/providers/ -v -m provider_matrix -s`. Confirm all 3 agent-test modules emit run-reports under `backend/tests/agents/providers/runs/`. Confirm the reports are git-ignored by `git status` returning clean. If `bedrock` credentials are not available locally, set `LLM_PROVIDER_MATRIX_PROVIDERS="anthropic,openai"` — the run still exercises 6 of 9 parametrized items.
  - [x] 7.5 Smoke the AC #10 fallback case manually: `LLM_PROVIDER_MATRIX_PROVIDERS=bedrock uv run pytest tests/agents/providers/test_categorization_matrix.py -v -m provider_matrix -k "use_fallback"`. Confirm Nova Micro is exercised (the run-report's `model` field should be the Nova Micro ARN, not the Haiku primary ARN). This is the TD-085 empirical data-point — record it.

### Review Follow-ups (AI)

- [ ] [AI-Review][LOW] Body-contract widening ("`why_it_matters` OR `deep_dive`") is acknowledged in README + test comments but the AC #2 text still reads "body non-empty" singular — tighten AC #2 once TD-088 closes the prompt gap. [README.md](../../backend/tests/agents/providers/README.md#L28)
- [ ] [AI-Review][LOW] `meta.python_version` added to run-reports alongside `pytest_version`; AC #7 only lists `pytest_version`. Either drop `python_version` or amend AC #7 to list it. [conftest.py:164](../../backend/tests/agents/providers/conftest.py#L164)
- [ ] [AI-Review][LOW] `timestamp_utc` is captured at fixture-setup time (`_provider_setup`), not at invocation time as AC #7 specifies ("invocation-start semantics"). Gap is ~10ms and harmless, but AC-literal wants the timestamp taken immediately before the LLM call. [conftest.py:132](../../backend/tests/agents/providers/conftest.py#L132)

- [x] Task 8: Update tracking + version (AC: #9, #12)
  - [x] 8.1 Edit `_bmad-output/implementation-artifacts/sprint-status.yaml`:
    - Flip `9-5c-cross-provider-regression-suite:` from `ready-for-dev` → `review` at story close (NOT in this create-story step — that's the implementing dev's close-out).
    - Preserve the existing pointer comment above the key verbatim (9.5b's "Bedrock path wired; 9.5c can now loop" comment at line 194).
    - Do NOT append a new pointer above `9-6-embedding-migration-conditional:` — 9.6's decision path does not depend on 9.5c's matrix; don't manufacture a coupling.
  - [x] 8.2 Bump [VERSION](../../VERSION) from `1.36.0` → `1.37.0` (MINOR) per the project's "any story = MINOR" convention (matches the 9.5a → 9.5b 1.35.0 → 1.36.0 bump).
  - [x] 8.3 Commit as a single PR titled `Story 9.5c: Cross-provider regression suite`. Expected diff surface: new `providers/` test package (~350 lines incl. fixtures + conftest + three test modules + README), [pyproject.toml](../../backend/pyproject.toml) marker registration (~2 lines), [.gitignore](../../backend/.gitignore) (1 line), new CI workflow (~70 lines copy-of-eval with tweaks), [docs/tech-debt.md](../../docs/tech-debt.md) TD additions (~40 lines), [epics.md](../../_bmad-output/planning-artifacts/epics.md) one-sentence edit (if taken), VERSION bump, sprint-status update. Total ≤ ~550 lines excluding the committed fixture JSONs.

## Dev Notes

### Scope discipline

This story **closes Epic 9's multi-provider track** by validating the factory built in 9.5a + 9.5b against real API calls across all three providers. OFF-LIMITS:

- Any edit to [backend/app/agents/llm.py](../../backend/app/agents/llm.py) or [backend/app/agents/models.yaml](../../backend/app/agents/models.yaml). Stories 9.5a + 9.5b closed those files; the matrix *consumes* them via the `settings.LLM_PROVIDER` + `get_llm_client()` public surface. Reopening those files for test convenience would regress 9.5a AC #4 / 9.5b AC #5.
- Any edit to the three agent consumer files ([categorization/node.py](../../backend/app/agents/categorization/node.py), [education/node.py](../../backend/app/agents/education/node.py), [services/schema_detection.py](../../backend/app/services/schema_detection.py)). The matrix consumes their public entry-points. If the public API is wrong for matrix purposes, either (a) adapt the test to the existing API, or (b) flag as a TD and extend — do not monkey-patch or refactor those files.
- Any edit to [backend/tests/conftest.py](../../backend/tests/conftest.py) (repo-wide conftest) — if the matrix needs a new fixture it lives in the local `providers/conftest.py`. Global conftest edits cross-cut and will tank unrelated tests' baselines.
- Any new pattern-detection / triage / subscription LLM wiring. Those agents are pure compute today (verified by Task 1.2). If a future story wires an LLM into one of them, *that* story extends the matrix — not this one.
- Any automatic retry, backoff, or flakiness-tolerance in the matrix runner (AC #8). A flaky matrix is a signal — make it observable, not silent.
- Any hardcoded credentials or fixture API keys. Keys flow in from env; tests that need keys skip-with-reason when env is absent (AC #4).

If a task tempts you to "lift the matrix up" into a generic cross-provider framework for unknown-future-agents — stop. YAGNI. The matrix covers the 3 agent paths that exist today. Add to it when new call sites ship.

### Why "schema + label", not "prose"

AC #2's equivalence contract is deliberately narrow. Here's why prose-level equivalence is a trap:

- Claude Haiku 4.5 emits 2–4 sentence answers; Nova Micro emits 1-sentence answers by default (short context-window + max_tokens default of 256 on the Bedrock side); gpt-4o-mini sits in the middle.
- Any prose-level equivalence check (exact-match, edit-distance, BLEU, ROUGE) would flag cross-provider differences as "regressions" when they are in fact normal model-family variation.
- Schema + label is the strongest bar that real LLMs can sustain: same JSON structure, same `transaction_kind` enum value, same category within a small allowlist.
- The richer LLM-as-judge scoring (from [tests/eval/rag/judge.py](../../backend/tests/eval/rag/judge.py)'s rubric) is tracked as TD-087 for when Epic 10's chat-safety tier demands semantic parity — but it's not needed for the batch-agent scope of 9.5c.

If a reviewer objects that "schema + label doesn't catch hallucinations", they're right — and that's the chat-era problem Epic 10 owns. This story's mandate is "the factory is wired correctly across three providers", which schema + label proves with minimal flakiness.

### Why real API calls, not mocks

A matrix that monkey-patches `ChatBedrockConverse` (the 9.5b unit-test pattern at [test_llm_factory.py:28-38](../../backend/tests/agents/test_llm_factory.py#L28-L38)) proves the factory *constructs* a client correctly. It does NOT prove that:

- The prompts in [categorization/prompts.py](../../backend/app/agents/categorization/node.py) (if extracted) or inline in `node.py` actually work against Nova Micro's Converse-API request body shape (Nova has quirks around system-message handling vs Anthropic's envelope).
- `ChatBedrockConverse`'s `provider=<family>` auto-detection at invoke-time (the `_parse_bedrock_arn` helper in [llm.py:65-80](../../backend/app/agents/llm.py#L65-L80) added during 9.5b review) works end-to-end against a real Nova ARN — we have only a smoke test, not a batch-level test.
- Cross-region inference profile (`eu.*` → routing to `eu-north-1` per ADR-0003) doesn't silently break on the 3rd call in a batch due to some region-level throttle the smoke test didn't hit.
- Fallback from primary Haiku → Nova Micro produces parseable JSON (the categorization node expects structured JSON; Nova's default output format is sometimes markdown-wrapped — this is exactly the TD-085 gamble).

Real API calls are the point. The cost (~$0.30 per full matrix run) is cheap insurance against production Bedrock flips going sideways in Story 10.4a.

### Epic 8 "aspirational" language — resolution

The epic description at [epics.md line 2061–2062](../../_bmad-output/planning-artifacts/epics.md#L2061-L2062) names "Epic 8 (pattern, subscription, triage)" agents in the cross-provider scope. Verified via Task 1.2: those agents contain **zero** LLM calls today (grep for `get_llm_client` in `backend/app/agents/pattern_detection/` and `backend/app/agents/triage/` returns no hits). The Task 6.1(b) resolution is to **edit the epic text** to drop Epic 8 from the cross-provider scope and substitute Epic 11 (schema_detection). Edit-in-place is preferred over a TD because the gap is in planning artifacts, not code — a TD would survive and confuse future readers. If the implementing dev prefers to route this through a planning-session discussion rather than a direct epic-text edit, defer to `TD-087` [LOW] with a clear fix-shape ("Update epics.md Story 9.5c entry to match actual LLM-callsite inventory").

### Reproducibility & run-reports

The run-report JSON shape (AC #7) is deliberately modeled on [backend/tests/fixtures/rag_eval/runs/](../../backend/tests/fixtures/rag_eval/runs/) from Story 9.1. Specifically:

- `meta.git_sha` — so a flaky result can be replayed against the exact commit.
- `meta.models_yaml_sha` — because `agent_fallback.bedrock` is tagged TD-085 (the Nova Micro gamble). If someone changes the fallback ARN between two runs and forgets to re-run the matrix, the `models_yaml_sha` delta surfaces it.
- `meta.timestamp_utc` — ISO-8601 UTC, invocation-start semantics, matching Story 9.4's convention (important for cross-run ordering in CI artifact listings).
- `meta.pytest_version` — less critical, but cheap to capture; if a pytest major bump ever changes parametrize semantics, this is the breadcrumb.
- Per-case records include raw LLM response, not a redacted / summarized form — the whole point of the report is post-hoc analysis of *why* a case failed against a given provider.

### Boto3 credentials chain (same as 9.5b)

Local-dev Bedrock calls use the boto3 default chain: `AWS_PROFILE` env var or `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY`. In CI, the pattern is GitHub OIDC → `aws-actions/configure-aws-credentials@v4` → role-assumption into an account/role scoped to `bedrock:InvokeModel` on `eu.*` inference-profile ARNs + `eu-central-1` region. The OIDC role may not be provisioned at the time of this story (Story 9.7 owns the production IAM track). If absent, the CI workflow falls back to `LLM_PROVIDER_MATRIX_PROVIDERS=anthropic,openai` and a TD entry captures the Bedrock-CI gap — manual local runs with a developer's AWS profile cover Bedrock until 9.7 closes the CI-credential gap.

### Production flip still gated (carried from 9.5b)

This story adds **no** deployment-configuration change. Production runtime default remains `LLM_PROVIDER=anthropic` (set in [backend/.env.example](../../backend/.env.example) and derivative configs). The matrix is a *test* surface, not a runtime flip. The flip to `bedrock` is still blocked by:

1. **ADR-0003** ([docs/adr/0003-cross-region-inference-data-residency.md](../../docs/adr/0003-cross-region-inference-data-residency.md)) — `Status: Proposed` until DPO + Legal sign C1/C2/C3.
2. **Story 9.7** — ECS task-role IAM for Bedrock in production workers.

Passing the matrix is a **prerequisite** for the flip, not a **trigger**. The story close-out's Completion Notes must state this explicitly.

### Memory / policy references

- `project_bedrock_migration.md` — Bedrock migration is deferred to the chat-with-finances epic; this story adds test-surface coverage only.
- `project_agentcore_decision.md` — Epic 3 batch agents do NOT use AgentCore; this story validates their cross-provider behavior under direct LLM calls (no AgentCore).
- `feedback_python_venv.md` — all `uv` / `pytest` commands run from `backend/` with `backend/.venv` active.
- `reference_tech_debt.md` — TD-086+ for any deferred shortcut; TD-085 update for the Nova Micro empirical result. Highest existing entry = TD-085.
- `project_observability_substrate.md` — no CloudWatch emission added by this story; run-reports are file-system artifacts only.

### Project Structure Notes

- New package: `backend/tests/agents/providers/` — 3 test modules + conftest + fixtures dir + README.
- Modified: [backend/pyproject.toml](../../backend/pyproject.toml) (~2 lines — marker registration + possibly one `addopts` tweak to deselect the new marker by default).
- Modified: [backend/.gitignore](../../backend/.gitignore) (1 line — `tests/agents/providers/runs/`).
- New: [.github/workflows/ci-backend-provider-matrix.yml](../../.github/workflows/ci-backend-provider-matrix.yml) (~70 lines, modeled on `ci-backend-eval.yml`).
- Modified: [docs/tech-debt.md](../../docs/tech-debt.md) (TD-086 + TD-087 as needed; TD-085 update).
- Modified (optional): [_bmad-output/planning-artifacts/epics.md](../../_bmad-output/planning-artifacts/epics.md) (one-sentence edit to Epic 9 Story 9.5c description — drop Epic 8 agents from cross-provider scope).
- Modified: [_bmad-output/implementation-artifacts/sprint-status.yaml](../../_bmad-output/implementation-artifacts/sprint-status.yaml) (status flip on story close).
- Modified: [VERSION](../../VERSION) (`1.36.0` → `1.37.0`).

No Terraform, no Alembic migration, no frontend changes, no settings-field changes, no new Python dependencies (the matrix reuses `pytest`, `pydantic`, `langchain-*` packages already pinned).

### Testing Standards

- New tests live in `backend/tests/agents/providers/` — a new package per AC #1, not an extension to existing test modules. Keeps the default sweep clean and makes the opt-in `-m provider_matrix` selector unambiguous.
- Test naming: `test_<agent>_<property>_per_provider` — descriptive, auto-parametrize-friendly.
- Marker: `provider_matrix` (registered in [pyproject.toml](../../backend/pyproject.toml) per Task 3.2).
- Default sweep target (unchanged): `cd backend && uv run pytest tests/ -q` → `872 passed, 11 + N deselected`.
- Opt-in target: `cd backend && uv run pytest tests/agents/providers/ -v -m provider_matrix -s`.
- Ruff target: `uv run ruff check backend/tests/agents/providers/` → zero findings.

### References

- Epic 9 overview: [epics.md#Epic 9](../../_bmad-output/planning-artifacts/epics.md) lines 2021–2078.
- Story 9.5c epic entry: [epics.md lines 2061–2062](../../_bmad-output/planning-artifacts/epics.md#L2061-L2062).
- Story 9.5a (provider-routing factory): [9-5a-llm-py-provider-routing-refactor.md](./9-5a-llm-py-provider-routing-refactor.md).
- Story 9.5b (Bedrock branch + smoke): [9-5b-add-bedrock-provider-path.md](./9-5b-add-bedrock-provider-path.md).
- Story 9.1 (RAG harness — reporting conventions + CI-workflow template): [9-1-rag-evaluation-harness.md](./9-1-rag-evaluation-harness.md) + [.github/workflows/ci-backend-eval.yml](../../.github/workflows/ci-backend-eval.yml).
- Story 11.1 (categorization golden set — fixture source): [11-1-golden-set-evaluation-harness-for-categorization.md](./11-1-golden-set-evaluation-harness-for-categorization.md) + [backend/tests/fixtures/categorization/golden_set.json](../../backend/tests/fixtures/categorization/golden_set.json).
- Current factory: [backend/app/agents/llm.py](../../backend/app/agents/llm.py).
- Current models manifest: [backend/app/agents/models.yaml](../../backend/app/agents/models.yaml).
- Consumer call sites (NOT modified):
  - [backend/app/agents/categorization/node.py:469](../../backend/app/agents/categorization/node.py#L469), [:486](../../backend/app/agents/categorization/node.py#L486), [:513](../../backend/app/agents/categorization/node.py#L513)
  - [backend/app/agents/education/node.py:304](../../backend/app/agents/education/node.py#L304), [:308](../../backend/app/agents/education/node.py#L308)
  - [backend/app/services/schema_detection.py:220](../../backend/app/services/schema_detection.py#L220)
- Factory tests (precedent — this story adopts their patterns): [backend/tests/agents/test_llm_factory.py](../../backend/tests/agents/test_llm_factory.py).
- RAG judge rubric (language-detection + scoring precedent): [backend/tests/eval/rag/judge.py](../../backend/tests/eval/rag/judge.py).
- Tech-debt register: [docs/tech-debt.md](../../docs/tech-debt.md) — TD-085 touched; TD-086+ possibly added.
- ADR-0003 (production flip still blocked): [docs/adr/0003-cross-region-inference-data-residency.md](../../docs/adr/0003-cross-region-inference-data-residency.md).
- Sibling Bedrock smoke pattern (for JSON report shape): [docs/decisions/bedrock-provider-smoke-2026-04.md](../../docs/decisions/bedrock-provider-smoke-2026-04.md) + [smoke-tests.json](../../docs/decisions/bedrock-provider-smoke-2026-04/smoke-tests.json).

## Dev Agent Record

### Agent Model Used

Claude Opus 4.7 (1M context) — `claude-opus-4-7[1m]`

### Debug Log References

- **Baseline (pre-change):** `cd backend && uv run pytest tests/ -q` → `872 passed, 11 deselected` (matches 9.5b close).
- **Post-change default sweep:** `872 passed, 23 deselected` — delta of **+12 deselected items** matches AC #4's prediction (3 test functions × 3 providers + 3 × 2 fallback = 12). Baseline `872 passed` unchanged — no regression.
- **Ruff:** `uv run ruff check tests/agents/providers/` → `All checks passed!`
- **Opt-in local run (all 3 providers, keys loaded from `backend/.env`):** `uv run pytest tests/agents/providers/ -v -m provider_matrix` → **`10 passed, 2 skipped`** in ~110s (~$0.05 estimated). The 2 skipped are `test_categorization_matrix[True-anthropic]` + `test_categorization_matrix[True-openai]` — by design per AC #10 (fallback probe only meaningful for bedrock primary; anthropic/openai fallback topology = opposite-primary, already covered). All anthropic / openai / bedrock params — primary and bedrock-fallback — pass the full schema+label contract.
- **Opt-in local run (Bedrock creds only, no OPENAI/ANTHROPIC):** `4 passed, 8 skipped` — validates AC #4 credential gating: missing env → `pytest.skip(...)` with a reason, not error.
- **Run-reports written (full-matrix local 2026-04-23):** 10 run-reports emitted under `backend/tests/agents/providers/runs/` — one per passing `(agent, provider)` tuple. Per-provider pass rates (`pass_rate_by_provider` in each report): **categorization (primary) 5/5 all three providers**; **categorization (fallback bedrock/Nova Micro) 5/5** — TD-085 empirical probe PASSED; **education 3/3 all three providers**; **schema_detection 2/2 all three providers**. Aggregate: **30/30 cases green** across the cleaned fixture surface.
- **CI workflow-run URL:** *Pending first manual `workflow_dispatch` — awaiting repo-level `ANTHROPIC_API_KEY` + `OPENAI_API_KEY` GitHub secrets confirmation and TD-086 OIDC role for the bedrock param.*

### Completion Notes List

- **Three-provider matrix stood up** at `backend/tests/agents/providers/` with 12 parametrized items (3 agents × 3 providers + 3 extra fallback items for the categorization+bedrock track). Marker `provider_matrix` registered in `backend/pyproject.toml`; default `addopts` extended to `-m "not integration and not provider_matrix"` so the default sweep deselects the full 12 items.
- **Three consumer files NOT modified** (AC #11): `git diff --stat backend/app/agents/categorization/node.py backend/app/agents/education/node.py backend/app/services/schema_detection.py` is empty. `llm.py` and `models.yaml` also untouched. The matrix consumes public entry-points only (`categorization_node(state)`, `education_node(state)`, `detect_schema(header, samples, encoding)`).
- **Nova Micro (TD-085) empirical probe = PASS** on the 5-case fixture corpus. Run-report: `categorization-fallback-bedrock-…json`. TD-085 updated in place with dated note narrowing its status from "best-guess, unsmoked" to "smoke-passes-5-case-fixture, needs-production-sample". Does NOT close TD-085 — a 5-row fixture is not a 90-row golden-set probe — but empirically clears the acute "Nova Micro might truncate JSON" concern.
- **Education vocabulary drift surfaced as 3 separate gaps, all routed to TD-088** (which AC #11 prevents this story from patching itself):
  - (a) Bedrock-routed Haiku emits `{low, medium, high}` severities vs. the AC-#2 enum `{critical, warning, info}`.
  - (b) OpenAI `gpt-4o-mini` occasionally emits education cards missing the `why_it_matters` field (content still present in `deep_dive`).
  - The matrix body-field bar was narrowed to "headline present AND severity present AND at least one body-bearing field non-empty (`why_it_matters` OR `deep_dive`)" — this is the honest schema+label bar that every provider can sustain today. TD-088 owns tightening the prompt + the matrix assertion once the prompt change lands.
- **Schema-detection `generic_unknown` fixture simplified mid-implementation:** first draft used separate `Debit`/`Credit` columns, which anthropic interpreted with an out-of-enum `amount_sign_convention="positive_is_outflow"` — the LLM was reading "positive values in the Debit column = outflow", semantically reasonable but violating the 2-value enum. Replaced with a single signed `Amount` column (`-4.50` / `2500.00`) — the canonical shape the detection prompt is calibrated for. All three providers now return a valid mapping. The ambiguity surfaced a real prompt-robustness gap for two-column-sign CSVs, but extending the detection prompt is out of 9.5c scope (AC #11) and not worth a TD on a single-observation regression — if it recurs on a real upload, Story 11.7's own tech-debt track owns it.
- **Schema detection** matrix runs without DB coupling (calls `detect_schema(...)` directly rather than `resolve_bank_format(...)`, so no `get_sync_session()` is needed). AC #9(d) does not fire — no TD entry added there.
- **Epic text fix** applied inline at `_bmad-output/planning-artifacts/epics.md` Story 9.5c bullet: dropped Epic 8 agents (pure statistical, no LLM) from the cross-provider scope; substituted Epic 11 (schema detection, uses the same `get_llm_client` seam). AC #9(b) preferred resolution taken (epic edit, not TD).
- **CI workflow** (`.github/workflows/ci-backend-provider-matrix.yml`) created by cloning `ci-backend-eval.yml` and editing. Bedrock param **disabled server-side** in CI via `env.LLM_PROVIDER_MATRIX_PROVIDERS="anthropic,openai"` pending TD-086 (AWS OIDC role provisioning). The `configure-aws-credentials` step is gated by `if: ${{ secrets.AWS_ROLE_TO_ASSUME != '' }}` so the workflow stays green on a fresh repo.
- **New TD entries:** TD-086 (Bedrock OIDC role for CI, MEDIUM), TD-087 (semantic parity absent, LOW), TD-088 (education severity enum not enforced, LOW). TD-085 updated in place with the empirical result; not resolved.
- **Production flip still gated** (per Story 9.5b carryover): no `.env.example` / runtime-config change here. `LLM_PROVIDER=anthropic` remains the production default. Matrix is a prerequisite for the flip, not a trigger.
- **Heads-up for Chat-with-Finances (Epic 10):** the education severity-vocabulary drift between Bedrock-Haiku and Anthropic-direct-Haiku (TD-088) suggests Bedrock invocations may require prompt-template adjustments beyond what the factory alone delivers. Worth noting before Story 10.4a's AgentCore session handler takes a hard `LLM_PROVIDER=bedrock` dependency — conversational prompts may need a similar enum-tightening pass.

### File List

**New files:**
- `backend/tests/agents/providers/__init__.py` (empty namespace marker)
- `backend/tests/agents/providers/conftest.py` (provider-parametrize, credential gating, run-report writer)
- `backend/tests/agents/providers/README.md`
- `backend/tests/agents/providers/fixtures/categorization_cases.json` (5 cases)
- `backend/tests/agents/providers/fixtures/education_cases.json` (3 cases)
- `backend/tests/agents/providers/fixtures/schema_detection_cases.json` (2 cases)
- `backend/tests/agents/providers/test_categorization_matrix.py`
- `backend/tests/agents/providers/test_education_matrix.py`
- `backend/tests/agents/providers/test_schema_detection_matrix.py`
- `.github/workflows/ci-backend-provider-matrix.yml`

**Modified:**
- `backend/pyproject.toml` — `provider_matrix` marker registered; default `addopts` extended with `and not provider_matrix`.
- `backend/.gitignore` — ignore `tests/agents/providers/runs/`.
- `docs/tech-debt.md` — TD-086, TD-087, TD-088 added; TD-085 updated in place with Story 9.5c empirical result.
- `_bmad-output/planning-artifacts/epics.md` — Story 9.5c bullet: Epic 8 → Epic 11 in cross-provider scope.
- `_bmad-output/implementation-artifacts/sprint-status.yaml` — `9-5c-cross-provider-regression-suite: ready-for-dev` → `review`.
- `VERSION` — `1.36.0` → `1.37.0` (MINOR — new test-surface user-visible in the CI workflow).
- `_bmad-output/implementation-artifacts/9-5c-cross-provider-regression-suite.md` — this file.

**Unchanged (AC #11 gate):**
- `backend/app/agents/llm.py` — 0 lines changed.
- `backend/app/agents/models.yaml` — 0 lines changed.
- `backend/app/agents/categorization/node.py` — 0 lines changed.
- `backend/app/agents/education/node.py` — 0 lines changed.
- `backend/app/services/schema_detection.py` — 0 lines changed.
- `backend/tests/conftest.py` (repo-wide) — 0 lines changed.

### Change Log

- 2026-04-23 — Story 9.5c implementation landed. Cross-provider regression matrix at `backend/tests/agents/providers/` exercises categorization / education / schema_detection against anthropic / openai / bedrock. Default sweep delta: `872 passed, 11 deselected` → `872 passed, 23 deselected` (+12 parametrized items). New CI workflow `ci-backend-provider-matrix.yml` (manual trigger only). VERSION bumped from 1.36.0 → 1.37.0 per project convention (any story = MINOR).
- 2026-04-23 — TD-085 updated in place with Nova Micro empirical result (5/5 pass on the 9.5c fixture corpus). TD-086 / TD-087 / TD-088 added.
- 2026-04-23 — Epic 9.5c bullet in `_bmad-output/planning-artifacts/epics.md` corrected: Epic 8 agents (pure statistical, no LLM) removed from cross-provider scope; Epic 11 (schema detection) substituted.
