# Story 9.5a: `llm.py` Provider-Routing Refactor (Anthropic + OpenAI only)

Status: done
Created: 2026-04-23
Epic: 9 — AI Infra Readiness (Bedrock Provider, RAG Eval Harness, Embedding Decision)

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **backend developer preparing `llm.py` for a future Bedrock path (Story 9.5b)**,
I want `backend/app/agents/llm.py` refactored into a small provider-routing factory that reads an `LLM_PROVIDER` env var and a role → per-provider model-ID map from `backend/app/agents/models.yaml` (currently Bedrock-only; this story adds the `anthropic:` + `openai:` columns alongside the existing `bedrock:` pins from Story 9.4),
so that Story 9.5b can wire `ChatBedrock` into the **same factory** by adding a third branch (no call-site churn, no schema churn), Story 9.5c's cross-provider regression matrix has a stable seam to parameterize on, and the Epic 3/8 agents that call `get_llm_client()` / `get_fallback_llm_client()` today keep producing the exact same Anthropic-Haiku + OpenAI-gpt-4o-mini behavior bit-for-bit once this story lands (no functional change in local or prod runtime — only the seams move).

## Acceptance Criteria

1. **Given** [backend/app/agents/llm.py](../../backend/app/agents/llm.py) currently hardcodes provider + model — `ChatAnthropic(model="claude-haiku-4-5-20251001")` at [llm.py:18](../../backend/app/agents/llm.py#L18) and `ChatOpenAI(model="gpt-4o-mini")` at [llm.py:33](../../backend/app/agents/llm.py#L33) — **When** this story completes **Then** `llm.py` resolves both model IDs by looking up a **logical role** (`agent_default` for the primary, `agent_cheap` / `chat_default` reserved for future roles) in `backend/app/agents/models.yaml`, splitting the value on the first `:` to separate provider-scheme (`anthropic` / `openai` / `bedrock`) from model-ID, and constructing the client for the scheme that matches `LLM_PROVIDER` (new env var — default `anthropic`). No model-ID string literal remains in `llm.py` after this refactor — every model ID flows out of `models.yaml`.

2. **Given** Story 9.4 committed `backend/app/agents/models.yaml` with three Bedrock entries only (schema comment: "logical role → provider-qualified model ID"; values prefixed with `bedrock:…`) **When** this story lands **Then** the schema is **extended from flat-string to per-role provider-map** to accommodate multi-provider routing, while preserving Story 9.4's pinned Bedrock values verbatim:
   ```yaml
   # Bedrock entries pinned by Story 9.4 on 2026-04-23 against region eu-central-1
   # (see docs/decisions/agentcore-bedrock-region-availability-2026-04.md).
   # Anthropic + OpenAI entries added by Story 9.5a — keep llm.py factory behavior
   # bit-for-bit equivalent to pre-refactor defaults (Haiku 4.5 + gpt-4o-mini).
   # Story 9.5b wires the bedrock: branch into the factory; this story does NOT.
   agent_default:
     anthropic: "claude-haiku-4-5-20251001"
     openai:    "gpt-4o-mini"
     bedrock:   "arn:aws:bedrock:eu-central-1:573562677570:inference-profile/eu.anthropic.claude-haiku-4-5-20251001-v1:0"
   agent_cheap:
     anthropic: "claude-haiku-4-5-20251001"
     openai:    "gpt-4o-mini"
     bedrock:   "arn:aws:bedrock:eu-central-1:573562677570:inference-profile/eu.anthropic.claude-haiku-4-5-20251001-v1:0"
   chat_default:
     anthropic: "claude-sonnet-4-6"
     openai:    "gpt-4o"
     bedrock:   "arn:aws:bedrock:eu-central-1:573562677570:inference-profile/eu.anthropic.claude-sonnet-4-6"
   ```
   Migration rule for the Bedrock values: the ARNs from Story 9.4's flat-string entries are copied verbatim into the `bedrock:` sub-key (**strip** the leading `bedrock:` scheme prefix when nesting — the key now carries the scheme, not the value). Anthropic entries match `llm.py:19` exactly. OpenAI `gpt-4o-mini` matches `llm.py:34` exactly. `chat_default.anthropic` / `chat_default.openai` are **reasonable best-guesses** (`claude-sonnet-4-6` per Story 9.4's sonnet-tier evidence; `gpt-4o` as the conventional OpenAI Sonnet-tier peer) and are marked as such in a one-line YAML comment `# chat_default anthropic/openai peers: unreferenced until Epic 10 — revise in Story 9.5b/10.4a if needed`. The file continues to parse via `yaml.safe_load` without errors.

3. **Given** the existing call sites do not want to know about providers, roles, or config plumbing **When** the refactor lands **Then** the existing public API of `llm.py` — **`get_llm_client()`** and **`get_fallback_llm_client()`** — is preserved with **identical signatures, identical circuit-breaker semantics, and identical return-type contracts** (both return a LangChain `BaseChatModel` subclass). The callsites in [backend/app/agents/categorization/node.py:24](../../backend/app/agents/categorization/node.py#L24), [backend/app/agents/education/node.py:13](../../backend/app/agents/education/node.py#L13), [backend/app/services/schema_detection.py:38](../../backend/app/services/schema_detection.py#L38), [backend/tests/eval/rag/candidates/runner.py:417](../../backend/tests/eval/rag/candidates/runner.py#L417), [backend/tests/eval/rag/judge.py:15](../../backend/tests/eval/rag/judge.py#L15) — **five files, seven call sites total** — are NOT edited by this story; their existing imports and invocations continue to compile + run unchanged. `get_llm_client()` internally resolves `role="agent_default"` against the active `LLM_PROVIDER`. `get_fallback_llm_client()` internally resolves the role `agent_default` against the **opposite** provider of the primary (`anthropic` primary → `openai` fallback, and vice versa) — this preserves the current runtime topology where Anthropic is primary and OpenAI is the circuit-breaker fallback. For the initial ship, `LLM_PROVIDER=bedrock` is a **valid config value but raises `NotImplementedError("Bedrock provider wiring lands in Story 9.5b")`** when either function is called under it; the enum value is accepted so Story 9.5b's diff is code-only (no config contract churn).

4. **Given** `LLM_PROVIDER` is a new env var introduced by this story **When** the refactor lands **Then** `backend/app/core/config.py` (Pydantic `Settings` class, currently carrying `ANTHROPIC_API_KEY` + `OPENAI_API_KEY` at [config.py:39-40](../../backend/app/core/config.py#L39-L40)) adds exactly one new field: `LLM_PROVIDER: Literal["anthropic", "openai", "bedrock"] = "anthropic"`. Default is `"anthropic"` so every existing deployment (local dev, Celery workers on ECS, test runs) keeps the pre-refactor behavior with **zero env-var changes required**. The `.env.example` (if present at repo root or `backend/`) gets a one-line entry: `LLM_PROVIDER=anthropic  # anthropic | openai | bedrock — bedrock wiring lands in Story 9.5b`. If `.env.example` is absent (verify; a `grep -l "ANTHROPIC_API_KEY" .env*` sweep at repo root will confirm), **do not create it** for this story — Story 9.7 owns the deploy-config surface.

5. **Given** the factory now reads a YAML file at import-time or first-call-time **When** `llm.py` is imported **Then** the YAML is loaded **once per process** via a cached loader (e.g., `functools.lru_cache(maxsize=1)` on a private `_load_models_config()` function) so production hot-paths (per-transaction categorization, per-card education) do not re-parse the YAML on every call. The cache is **invalidated-for-tests** via a public helper `reload_models_config_for_tests()` that clears the lru_cache — tests can call this after monkeypatching the YAML path, but production code must not. The YAML path defaults to `Path(__file__).parent / "models.yaml"` and is overridable via a `LLM_MODELS_CONFIG_PATH` env var (undocumented in `.env.example`; strictly for integration tests and Story 9.5c's matrix runner to inject a fixture file). If the YAML is missing at resolution time, the error is `FileNotFoundError` with the resolved path in the message — **not a silent empty-dict default** that would let a deployment ship with the wrong model pins.

6. **Given** the role-lookup must fail loud for typos + missing entries **When** `get_llm_client()` or `get_fallback_llm_client()` runs **Then** a missing role raises `KeyError("Role '<role>' not found in models.yaml (available: <sorted-role-list>)")` and a missing `<role>.<provider>` sub-key raises `KeyError("Role '<role>' has no '<provider>' entry in models.yaml (available: <sorted-provider-list>)")`. Neither path falls back to a hardcoded default — the whole point of this refactor is to eliminate hardcoded model IDs. The circuit-breaker checks (`check_circuit("anthropic")` / `check_circuit("openai")` per [llm.py:14](../../backend/app/agents/llm.py#L14) + [llm.py:29](../../backend/app/agents/llm.py#L29)) happen **after** config resolution but **before** client construction — same ordering as today; preserve the exact existing behavior so the existing circuit-breaker tests at [backend/tests/agents/test_circuit_breaker.py](../../backend/tests/agents/test_circuit_breaker.py) (if present — verify) stay green without edits. The circuit-breaker provider key is still `"anthropic"` / `"openai"` (matches [circuit_breaker.py:20-21](../../backend/app/agents/circuit_breaker.py#L20-L21) key format); **not** a role name and **not** the Bedrock key (Bedrock circuit-breaker wiring is 9.5b).

7. **Given** the refactor must be verifiable as behavior-preserving **When** the story ships **Then** a new test module `backend/tests/agents/test_llm_factory.py` is added covering:
   - **Default provider path**: `get_llm_client()` with no env var → returns a `ChatAnthropic` instance whose `.model` attribute (or equivalent LangChain-internal attribute — verify on the installed `langchain-anthropic` version) is `"claude-haiku-4-5-20251001"`. Asserts the model ID came from YAML, not a literal.
   - **Primary provider switch**: `monkeypatch.setenv("LLM_PROVIDER", "openai")` → `get_llm_client()` returns a `ChatOpenAI` with model `"gpt-4o-mini"`; `get_fallback_llm_client()` under the same env returns a `ChatAnthropic` with model `"claude-haiku-4-5-20251001"` (opposite-of-primary rule from AC #3).
   - **Bedrock is reserved but not wired**: `monkeypatch.setenv("LLM_PROVIDER", "bedrock")` → `get_llm_client()` raises `NotImplementedError` containing the substring `"Story 9.5b"`. `get_fallback_llm_client()` under `bedrock` also raises `NotImplementedError` (neither direction of fallback is defined for `bedrock` by this story).
   - **Missing API key still raises `ValueError`**: `monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", None)` → `get_llm_client()` raises the same `ValueError("ANTHROPIC_API_KEY not configured")` message as [llm.py:16](../../backend/app/agents/llm.py#L16) today (string-match the exact message — this is a contract preservation test).
   - **Missing role + missing provider sub-key** raise `KeyError` per AC #6 with the expected message shape (via a temp YAML fixture injected through `LLM_MODELS_CONFIG_PATH`; reload cache via `reload_models_config_for_tests()`).
   - **Circuit-breaker ordering**: when the Redis breaker is open (mock `check_circuit` to raise), the test confirms `CircuitBreakerOpenError` surfaces and **no** LangChain client was constructed (patch the provider constructor to fail the test if it was called after the breaker opened).
   The module uses `pytest` + `monkeypatch` only — no live network, no Redis, no actual `ChatAnthropic.invoke` call. Target: ≤ ~120 lines, ≤ 8 test functions.

8. **Given** the five existing callsites from AC #3 import `get_llm_client` / `get_fallback_llm_client` **When** the default sweep runs (`cd backend && uv run pytest tests/ -q`) **Then** it stays green: baseline from Story 9.4 close-out is **`861 passed, 11 deselected`** (confirmed at Story 9.4's Task 10.1). After 9.5a, the count becomes **`861 + N passed, 11 deselected`** where `N` is the count of test functions added in AC #7 (target ≤ 8). No existing test is deleted, skipped, or modified to make the suite green — if any test fails after the refactor, the refactor is wrong (the `langchain_anthropic.ChatAnthropic` / `langchain_openai.ChatOpenAI` call shapes are **unchanged**; the only observable change to existing code is that the model-ID string now comes from YAML via a helper, not a literal).

9. **Given** `ruff` is the project linter per [backend/pyproject.toml](../../backend/pyproject.toml) **When** the story ships **Then** `uv run ruff check backend/app/agents/llm.py backend/tests/agents/test_llm_factory.py` returns zero findings. (Repo-wide ruff drift from TD-068 is out of scope — only the files this story touches/adds must be clean.)

10. **Given** `docs/tech-debt.md` tracks deferred work with `TD-NNN` IDs (highest current = TD-081 per [docs/tech-debt.md:1247](../../docs/tech-debt.md#L1247)) **When** this refactor surfaces any deferred item (expected candidates: (a) logical roles beyond `agent_default` are defined in `models.yaml` but only `agent_default` is wired into `get_llm_client`/`get_fallback_llm_client` — the `agent_cheap` / `chat_default` roles are data-only until Story 10.4a consumes them; (b) `chat_default.anthropic` / `chat_default.openai` values are best-guesses that Story 9.5b or 10.4a may revise; (c) the opposite-of-primary fallback rule in AC #3 is hardcoded in Python rather than expressed in YAML — a more general `fallback_provider` field on each role would be cleaner but is out-of-scope for 9.5a's minimum-diff goal) **Then** each becomes a `TD-082+` entry pointing back to this story. If none are taken, add no entry.

11. **Given** sprint-status.yaml tracks story state **When** the story is ready for dev **Then** `_bmad-output/implementation-artifacts/sprint-status.yaml`'s `9-5a-llm-py-provider-routing-refactor:` key is flipped `backlog` → `ready-for-dev` by the create-story workflow (this file), and on story close-out the implementing dev flips it to `review` (code-review flips to `done` per the normal flow). A one-line pointer comment above `9-5b-add-bedrock-provider-path:` is updated to note that the factory seam for 9.5b is now landed (the existing "region/ARN" pointer comment from Story 9.4 stays; add a second line: `# Story 9.5a factory ready; 9.5b adds the bedrock: branch in llm.py`).

## Tasks / Subtasks

- [x] Task 1: Capture baseline + plan the diff (AC: #8, #9)
  - [x] 1.1 From `backend/` with the `backend/.venv` active (per memory `feedback_python_venv.md`), run `uv run pytest tests/ -q` and confirm the baseline **`861 passed, 11 deselected`** (Story 9.4 close-out). If the count has drifted on `main`, record the current count as this story's baseline and carry that forward into AC #8 — do not investigate drift (orthogonal to this refactor).
  - [x] 1.2 Read [backend/app/agents/llm.py](../../backend/app/agents/llm.py) completely — note circuit-breaker call ordering (line 14, 29), API-key validation ordering (line 15, 30), LangChain constructor shapes (line 17-21, 32-36). Every one of these is preserved bit-for-bit in the refactor; the only change is the source of the `model=...` string.
  - [x] 1.3 Read [backend/app/agents/models.yaml](../../backend/app/agents/models.yaml) completely — capture the exact three Bedrock ARN strings (verbatim-preserve rule per AC #2) into a scratch buffer so the YAML rewrite does not paraphrase them.

- [x] Task 2: Extend `models.yaml` schema (AC: #2)
  - [x] 2.1 Rewrite `backend/app/agents/models.yaml` from flat-string per-role to per-role provider-map per AC #2. Copy the Bedrock ARNs verbatim from Task 1.3 into the `bedrock:` sub-key of each role (strip the leading `bedrock:` scheme prefix — the key carries the scheme now). Add `anthropic:` + `openai:` entries per AC #2 (Haiku 4.5 + gpt-4o-mini for `agent_default` and `agent_cheap`; sonnet-4-6 + gpt-4o best-guess for `chat_default`).
  - [x] 2.2 Update the top-of-file comment block per AC #2 (preserve Story 9.4 provenance; append Story 9.5a provenance + the note that `chat_default` peers are unreferenced until Epic 10).
  - [x] 2.3 Validate the file parses: from repo root with backend venv active, `python -c "import yaml, pathlib; d = yaml.safe_load(pathlib.Path('backend/app/agents/models.yaml').read_text()); assert set(d) == {'agent_default', 'agent_cheap', 'chat_default'}; assert all('anthropic' in v and 'openai' in v and 'bedrock' in v for v in d.values()); print(d)"`. Output must match the AC #2 structure.

- [x] Task 3: Add `LLM_PROVIDER` to settings (AC: #4)
  - [x] 3.1 Edit [backend/app/core/config.py](../../backend/app/core/config.py) to add `LLM_PROVIDER: Literal["anthropic", "openai", "bedrock"] = "anthropic"` in the `Settings` class near the `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` fields (lines 39-40). Import `Literal` from `typing` if not already imported.
  - [x] 3.2 Search for `.env.example` at repo root and under `backend/` (`ls .env.example backend/.env.example 2>/dev/null` — or glob). If found, add one line per AC #4. If not found, do not create it.
  - [x] 3.3 From `backend/`, run `uv run python -c "from app.core.config import settings; print(settings.LLM_PROVIDER)"` to confirm the default resolves to `"anthropic"`.

- [x] Task 4: Refactor `llm.py` into a provider-routing factory (AC: #1, #3, #5, #6)
  - [x] 4.1 Add private helpers to `backend/app/agents/llm.py`:
    - `_load_models_config() -> dict[str, dict[str, str]]` — loads the YAML via `pathlib.Path(os.environ.get("LLM_MODELS_CONFIG_PATH", Path(__file__).parent / "models.yaml"))`; `@functools.lru_cache(maxsize=1)`; raises `FileNotFoundError` with resolved path on miss (AC #5).
    - `reload_models_config_for_tests() -> None` — `_load_models_config.cache_clear()` (public test hook per AC #5).
    - `_resolve_model_id(role: str, provider: str) -> str` — fetches from the loaded config; raises `KeyError` with the exact message shapes from AC #6.
    - `_build_client(provider: str, model_id: str)` — matches on provider: `"anthropic"` → `ChatAnthropic(model=model_id, api_key=settings.ANTHROPIC_API_KEY)`; `"openai"` → `ChatOpenAI(model=model_id, api_key=settings.OPENAI_API_KEY)`; `"bedrock"` → `raise NotImplementedError("Bedrock provider wiring lands in Story 9.5b")`. Langchain imports stay **lazy** (inside each branch, matching current code — preserves import-time cost profile).
  - [x] 4.2 Rewrite `get_llm_client()` to: resolve `primary = settings.LLM_PROVIDER`; call `check_circuit(primary)` (if primary is `"bedrock"`, the `NotImplementedError` from `_build_client` will fire before any circuit call — accept the slightly-out-of-order ordering for `bedrock` because 9.5b owns that path); validate the primary's API key per AC #7's ValueError-preservation requirement (keep the **exact** error message strings from [llm.py:16](../../backend/app/agents/llm.py#L16) + [llm.py:31](../../backend/app/agents/llm.py#L31) — `"ANTHROPIC_API_KEY not configured"` / `"OPENAI_API_KEY not configured"` — only raise the one matching the active primary); resolve model-id via `_resolve_model_id("agent_default", primary)`; build client via `_build_client(primary, model_id)`.
  - [x] 4.3 Rewrite `get_fallback_llm_client()` symmetrically: `fallback = {"anthropic": "openai", "openai": "anthropic", "bedrock": "bedrock"}[primary]`; same sequence as 4.2 but using the fallback provider. `bedrock → bedrock` fallback intentionally raises `NotImplementedError` (no defined fallback for a Bedrock-primary deployment in 9.5a — deferred to 9.5b).
  - [x] 4.4 Keep the `CircuitBreakerOpenError` re-export on line 4 of `llm.py` exactly as-is; it is consumed elsewhere and must not move.
  - [x] 4.5 `uv run ruff check backend/app/agents/llm.py` → zero findings.

- [x] Task 5: Add factory unit tests (AC: #7, #9)
  - [x] 5.1 Create `backend/tests/agents/test_llm_factory.py` covering the six scenarios enumerated in AC #7. Use `pytest`'s `monkeypatch` for env vars + settings attributes; use `tmp_path` + `LLM_MODELS_CONFIG_PATH` for the "missing role / missing provider sub-key" fixture injection; call `reload_models_config_for_tests()` after setting the env var so the lru_cache doesn't serve stale config.
  - [x] 5.2 For the "no LangChain construction when circuit is open" test: patch `app.agents.circuit_breaker.check_circuit` to raise `CircuitBreakerOpenError`, then assert no `ChatAnthropic.__init__` / `ChatOpenAI.__init__` was called (monkeypatch the constructor with a `pytest.fail`-on-call sentinel).
  - [x] 5.3 For the `.model` attribute assertion (AC #7 first scenario): before writing the assertion, quickly verify the live attribute name on the installed `langchain-anthropic` — `uv run python -c "from langchain_anthropic import ChatAnthropic; c = ChatAnthropic(model='claude-haiku-4-5-20251001', api_key='fake'); print([a for a in dir(c) if 'model' in a.lower()])"`. If the attribute is named differently in the pinned version (e.g. `.model_name`), use the actual name — do not hardcode an attribute the runtime does not expose.
  - [x] 5.4 Run `uv run pytest tests/agents/test_llm_factory.py -q -v` — all tests pass.

- [x] Task 6: Full regression + no-untouched-callsite verification (AC: #3, #8)
  - [x] 6.1 `git status` + `git diff --stat` — confirm the only non-test files modified are `backend/app/agents/llm.py`, `backend/app/agents/models.yaml`, `backend/app/core/config.py`, and (optionally) `.env.example` per Task 3.2. The five call-site files listed in AC #3 must be **unchanged** (`git diff --stat backend/app/agents/categorization/node.py backend/app/agents/education/node.py backend/app/services/schema_detection.py backend/tests/eval/rag/candidates/runner.py backend/tests/eval/rag/judge.py` → empty).
  - [x] 6.2 From `backend/`, run `uv run pytest tests/ -q`. Confirm count matches AC #8: `861 + N passed, 11 deselected` where `N` is the new test count from Task 5.1 (≤ 8).
  - [x] 6.3 Quick manual smoke: from `backend/` with real `ANTHROPIC_API_KEY` set, `uv run python -c "from app.agents.llm import get_llm_client; c = get_llm_client(); print(type(c).__name__, getattr(c, 'model', None) or getattr(c, 'model_name', None))"` → prints `ChatAnthropic` + `claude-haiku-4-5-20251001`. Repeat with `LLM_PROVIDER=openai` + `OPENAI_API_KEY` → prints `ChatOpenAI` + `gpt-4o-mini`. This is a human-loop sanity check, not a committed test.

- [x] Task 7: Update tracking + version (AC: #10, #11)
  - [x] 7.1 If any shortcut from AC #10's candidate list was taken (role-data-only without Python wiring, best-guess `chat_default` peers, hardcoded fallback topology), append `TD-082`+ entries to [docs/tech-debt.md](../../docs/tech-debt.md) — `LOW` severity unless the shortcut materially blocks Story 9.5b, in which case `MEDIUM`. Each entry ends with a pointer to this story file. If none taken, no TD entry.
  - [x] 7.2 Edit `_bmad-output/implementation-artifacts/sprint-status.yaml`:
    - Flip `9-5a-llm-py-provider-routing-refactor:` from `ready-for-dev` → `review` at story close.
    - Append a second pointer line above `9-5b-add-bedrock-provider-path:` per AC #11 (keep Story 9.4's existing region/ARN comment — this is additive, not a replacement): `# Story 9.5a factory ready; 9.5b adds the bedrock: branch in llm.py`.
  - [x] 7.3 Bump [VERSION](../../VERSION) from `1.34.0` → `1.35.0` (MINOR) per the project's "any story = MINOR" convention (matches Story 9.4's 1.33.0 → 1.34.0 bump).
  - [x] 7.4 Commit as a single PR titled `Story 9.5a: llm.py provider-routing refactor (Anthropic + OpenAI only)`. Expected diff surface: ~60 lines changed in `llm.py`, ~15 lines in `models.yaml`, 1 line in `config.py`, ~100 lines in `test_llm_factory.py`, 1 line in `VERSION`, 2 lines in `sprint-status.yaml`. Total ≤ ~180 lines.

## Dev Notes

### Scope discipline

This is a **pure refactor** with zero behavioral change under default config. OFF-LIMITS:

- Any edit to the five existing callsites listed in AC #3 — they consume the unchanged public API (`get_llm_client` / `get_fallback_llm_client`). Changing any of them invalidates AC #3 and reopens the regression surface this story is trying to *close*.
- Any `ChatBedrock` import or wiring — Story 9.5b owns that. This story accepts `LLM_PROVIDER=bedrock` as a valid enum value but deliberately raises `NotImplementedError` when it is active. That keeps the config contract stable for 9.5b's **code-only** diff.
- Any Terraform or IAM change — Story 9.7 owns the ECS task-role permissions for Bedrock.
- Any change to `backend/app/agents/circuit_breaker.py` — the provider keys (`"anthropic"`, `"openai"`) stay exactly as they are today. Bedrock will get its own provider key in Story 9.5b.
- Any change to the RAG eval harness scoring or baseline ([backend/tests/eval/rag/](../../backend/tests/eval/rag/)) — the harness imports `get_llm_client()` per AC #3's callsite list; it must continue to return the same Anthropic-Haiku client with no observable change. If the harness baseline numbers shift after this story, the refactor is wrong.

If a task tempts you to "clean up" the callsites ("while I'm here, let me replace `get_llm_client()` with `get_client("agent_default")`") — stop. That cleanup belongs to Story 9.5c's matrix work or a dedicated tech-debt story. The whole point of preserving the old API is to keep the PR diff **reviewable in one sitting** and to keep the regression surface **tiny**.

### Why this story is worth doing as a standalone unit

Splitting the original Story 9.5 into 9.5a/b/c (done in the 2026-04-19 sprint-planning pass per `sprint-status.yaml` line 182-183) is specifically to let this refactor land alone:

1. **Reviewer load is low** — the PR is a mechanical restructuring with ≤ ~180 lines diff. A senior reviewer can verify "no behavior change" by inspection in minutes.
2. **Bedrock wiring (9.5b) becomes a pure additive code diff** — a single case branch in `_build_client` plus unit tests. No schema changes, no callsite touches, no YAML rewrites. That is the smallest-possible Bedrock-adoption surface and exactly what auditors want to see.
3. **Cross-provider regression (9.5c) gets a stable seam** — `models.yaml` is now the single source of truth for per-role per-provider model IDs. 9.5c's matrix runner can loop `LLM_PROVIDER ∈ {anthropic, openai, bedrock}` without further refactoring.
4. **Production risk is minimized** — under default config (`LLM_PROVIDER=anthropic`), every callsite produces the same `ChatAnthropic(model="claude-haiku-4-5-20251001")` object as today. Nothing about request paths, retry logic, circuit breaker, or fallback topology moves.

### Why a YAML file, not a Python constant

The `models.yaml` schema originated in Story 9.4 specifically so that AWS-Bedrock churn (new model versions, inference-profile ARN changes) can land as **data edits reviewable by a security person who does not read Python**. Story 9.5a extends that rationale to Anthropic + OpenAI: a model-ID bump (e.g. Haiku 4.5 → 4.7 when Anthropic ships it) becomes a one-line YAML edit with no Python changes and no risk of regressions from misplaced refactors. The YAML also becomes the single knob Story 9.5c's matrix-runner twists to swap providers in CI.

### Opposite-of-primary fallback rule (AC #3)

The existing runtime behavior is: primary=Anthropic, fallback=OpenAI. The circuit breaker uses OpenAI when Anthropic's breaker is open. This story generalizes to: fallback is whichever of Anthropic/OpenAI is **not** the primary — so under `LLM_PROVIDER=openai`, the fallback becomes Anthropic. That symmetry is a reasonable default for local/dev contexts where ops may want to run against OpenAI primarily (e.g., when Anthropic rate-limits); production today runs `LLM_PROVIDER=anthropic` (the default) and nothing observable changes.

The rule is hardcoded in Python as a two-entry dict (`{"anthropic": "openai", "openai": "anthropic"}`) rather than an explicit `fallback:` field on each role in `models.yaml`. That is a deliberate minimum-viability choice per AC #10: a future story can hoist fallback topology into the YAML if Epic 10 needs per-role fallback policies. For 9.5a, the two-provider symmetric rule is sufficient.

### `chat_default` role is reserved, not wired

AC #2 adds a `chat_default` role to `models.yaml` with sonnet-tier IDs. **No code in this story reads `chat_default`** — `get_llm_client()` and `get_fallback_llm_client()` both resolve `agent_default`. `chat_default` is pre-populated so that Epic 10's Story 10.4a (chat session handler) can simply start calling `_resolve_model_id("chat_default", provider)` without a schema edit. The `chat_default.anthropic` / `chat_default.openai` values are best-guesses (`claude-sonnet-4-6` / `gpt-4o`) and the YAML comment flags them as revisable — the authoritative validation of these values happens in Story 9.5b (when Bedrock sonnet is invoke-tested per the live factory) or Story 10.4a (when the chat session handler actually calls them).

### Tests must be deterministic and offline

The new `test_llm_factory.py` must not:
- Call real Anthropic / OpenAI / Bedrock endpoints.
- Construct a real `ChatAnthropic.invoke(...)` request.
- Read real environment `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` values (use `monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "fake-key-for-tests")`).
- Depend on Redis (mock `check_circuit` directly).

This matches the pattern of existing `backend/tests/agents/test_circuit_breaker.py` (if present — verify in Task 5.1) and keeps the test module safe to run in parallel / CI without external dependencies. The one exception is AC #7's "Bedrock raises NotImplementedError" path — it does not attempt any SDK import because the `NotImplementedError` fires before the import would run.

### LangChain attribute quirks

The `.model` attribute on `ChatAnthropic` may be exposed as `model`, `model_name`, or both depending on the `langchain-anthropic` version pinned in [backend/pyproject.toml](../../backend/pyproject.toml). Task 5.3 explicitly verifies the attribute name on the installed version before writing the assertion — do not hardcode `c.model` if the runtime exposes only `c.model_name` (or vice versa). A defensive pattern: `actual = getattr(c, "model", None) or getattr(c, "model_name", None)` — that is good enough for a smoke test and survives LangChain's occasional rename churn.

### Integration points

- Current `llm.py`: [backend/app/agents/llm.py](../../backend/app/agents/llm.py) (37 lines total — entire file is being rewritten).
- Current `models.yaml` (Story 9.4 artifact): [backend/app/agents/models.yaml](../../backend/app/agents/models.yaml) (17 lines — schema being extended).
- Circuit breaker: [backend/app/agents/circuit_breaker.py](../../backend/app/agents/circuit_breaker.py) — untouched; this story preserves exact ordering and provider-key shape.
- Settings: [backend/app/core/config.py](../../backend/app/core/config.py) — one new field (`LLM_PROVIDER`).
- Consumers (NOT edited): [categorization/node.py](../../backend/app/agents/categorization/node.py), [education/node.py](../../backend/app/agents/education/node.py), [schema_detection.py](../../backend/app/services/schema_detection.py), [rag/candidates/runner.py](../../backend/tests/eval/rag/candidates/runner.py), [rag/judge.py](../../backend/tests/eval/rag/judge.py).
- Sibling story: [Story 9.4 spike](./9-4-agentcore-bedrock-region-availability-spike.md) (pins Bedrock IDs that this story folds into the per-role map).
- Downstream dependent: Story 9.5b (adds `ChatBedrock` branch), Story 9.5c (cross-provider matrix runner).

### Memory / policy references

- `project_bedrock_migration.md` — LLM Bedrock migration is deferred; this story does NOT flip runtime traffic to Bedrock. It only **builds the seam**. Runtime still ships `LLM_PROVIDER=anthropic` by default.
- `project_agentcore_decision.md` — Epic 3 batch agents do NOT use AgentCore; this refactor preserves their current Anthropic-direct + OpenAI-fallback topology byte-for-byte.
- `feedback_python_venv.md` — all Python commands from `backend/` with `backend/.venv` active.
- `reference_tech_debt.md` — TD-082+ for any shortcut taken. Highest existing TD is TD-081 per current register state.
- `project_observability_substrate.md` — no CloudWatch emission added by this refactor; LLM-provider selection is a local config read.

### Project Structure Notes

- Modified: `backend/app/agents/llm.py` (rewrite — 37 lines → ~80 lines, still a single module).
- Modified: `backend/app/agents/models.yaml` (schema extension — 17 lines → ~28 lines).
- Modified: `backend/app/core/config.py` (one new field).
- Optional modified: `.env.example` (only if present — do not create).
- New: `backend/tests/agents/test_llm_factory.py` (~100 lines).
- Modified: `_bmad-output/implementation-artifacts/sprint-status.yaml` (status flip + one pointer comment line).
- Modified: `VERSION` (`1.34.0` → `1.35.0`).
- Conditional modified: `docs/tech-debt.md` (only if a shortcut was taken per AC #10).

No Terraform, no CI workflow changes, no frontend changes, no Alembic migration, no Redis schema change, no new dependencies.

### Testing Standards

- New tests live under `backend/tests/agents/` alongside existing `test_categorization.py`, `test_education.py`, etc.
- Test naming: `test_llm_factory.py`. Function naming: `test_<scenario>_<expected_outcome>` (e.g., `test_default_provider_returns_anthropic_haiku`).
- Use `pytest.fixture` + `monkeypatch` for config/env manipulation; `tmp_path` for the fixture YAML injection path per AC #5's `LLM_MODELS_CONFIG_PATH`.
- `pytest.raises(...)` with `match="<regex>"` on the `ValueError` / `KeyError` / `NotImplementedError` message assertions — string-match the exact messages called out in AC #6 and AC #7.
- Default sweep target: `cd backend && uv run pytest tests/ -q` → `861 + N passed, 11 deselected` (Task 6.2).
- Ruff target: `uv run ruff check backend/app/agents/llm.py backend/tests/agents/test_llm_factory.py` → zero findings.

### References

- Epic 9 overview: [epics.md#Epic 9](../../_bmad-output/planning-artifacts/epics.md) lines 2021–2078
- Story 9.5a epic entry: [epics.md lines 2055–2056](../../_bmad-output/planning-artifacts/epics.md)
- Story 9.5b / 9.5c dependency statements: [epics.md lines 2058–2062](../../_bmad-output/planning-artifacts/epics.md)
- Story 9.4 (Bedrock pins source): [9-4-agentcore-bedrock-region-availability-spike.md](./9-4-agentcore-bedrock-region-availability-spike.md) + [docs/decisions/agentcore-bedrock-region-availability-2026-04.md](../../docs/decisions/agentcore-bedrock-region-availability-2026-04.md)
- Current `llm.py`: [backend/app/agents/llm.py](../../backend/app/agents/llm.py)
- Current `models.yaml`: [backend/app/agents/models.yaml](../../backend/app/agents/models.yaml)
- Circuit breaker: [backend/app/agents/circuit_breaker.py](../../backend/app/agents/circuit_breaker.py)
- Settings: [backend/app/core/config.py](../../backend/app/core/config.py)
- Callsite files (NOT to be modified):
  - [backend/app/agents/categorization/node.py:24](../../backend/app/agents/categorization/node.py#L24)
  - [backend/app/agents/education/node.py:13](../../backend/app/agents/education/node.py#L13)
  - [backend/app/services/schema_detection.py:38](../../backend/app/services/schema_detection.py#L38)
  - [backend/tests/eval/rag/candidates/runner.py:417](../../backend/tests/eval/rag/candidates/runner.py#L417)
  - [backend/tests/eval/rag/judge.py:15](../../backend/tests/eval/rag/judge.py#L15)
- Tech-debt register: [docs/tech-debt.md](../../docs/tech-debt.md)

## Dev Agent Record

### Agent Model Used

claude-opus-4-7[1m]

### Debug Log References

- Baseline (pre-refactor): `861 passed, 11 deselected` — matches Story 9.4 close-out.
- Post-refactor: `869 passed, 11 deselected` — +8 new tests from `test_llm_factory.py`. No regressions.
- Ruff on touched files: clean.

### Completion Notes List

- Refactored `backend/app/agents/llm.py` into a small provider-routing factory keyed off `settings.LLM_PROVIDER`. Public API (`get_llm_client` / `get_fallback_llm_client`) preserved bit-for-bit; callsites in `agents/categorization`, `agents/education`, `services/schema_detection`, `tests/eval/rag/candidates`, `tests/eval/rag/judge` are not modified (verified with `git diff --stat`).
- Extended `backend/app/agents/models.yaml` from flat-string per-role to per-role provider-map. Bedrock ARNs from Story 9.4 copied verbatim into `bedrock:` sub-keys; `anthropic:` + `openai:` columns added; `chat_default` peers are data-only and flagged in comments as revisable in Story 9.5b/10.4a.
- Added `LLM_PROVIDER: Literal["anthropic", "openai", "bedrock"] = "anthropic"` to `Settings`. Default preserves pre-refactor behavior for all existing deployments with zero env-var changes. `.env.example` gains one commented line.
- YAML loading is cached via `functools.lru_cache(maxsize=1)` on `_load_models_config`; `reload_models_config_for_tests()` exposes cache clearing for tests. YAML path is overridable via `LLM_MODELS_CONFIG_PATH` env var (undocumented; test-only).
- `LLM_PROVIDER=bedrock` is a valid enum value but `_build_client` raises `NotImplementedError("Bedrock provider wiring lands in Story 9.5b")`. Both `get_llm_client` and `get_fallback_llm_client` propagate this.
- New tests `backend/tests/agents/test_llm_factory.py`: 8 test functions covering default path, primary switch + opposite-of-primary fallback, Bedrock-reserved, missing API key ValueError preservation (Anthropic + OpenAI), missing role / missing provider sub-key KeyError shapes, and circuit-breaker-open blocks client construction (constructors monkeypatched to `pytest.fail`).
- LangChain attribute check (Task 5.3): on installed versions, `ChatAnthropic` exposes only `.model`; `ChatOpenAI` exposes both `.model` and `.model_name`. Assertions use the available attribute directly.
- Tech-debt register: added TD-082 (roles-data-only-until-10.4a) and TD-083 (hardcoded opposite-of-primary fallback topology) per AC #10. Both LOW severity, pointer back to this story.
- Sprint-status pointer comment for Story 9.5b was already present above `9-5b-add-bedrock-provider-path:` from the create-story step — no change needed beyond the status flip.
- VERSION bumped `1.34.0` → `1.35.0` per project's MINOR-per-story convention.

### File List

- Modified: `backend/app/agents/llm.py` — rewritten as provider-routing factory (`_load_models_config`, `reload_models_config_for_tests`, `_resolve_model_id`, `_build_client`, `_get_client_for`; public `get_llm_client` / `get_fallback_llm_client` preserved).
- Modified: `backend/app/agents/models.yaml` — schema extended from flat-string to per-role provider-map; Bedrock ARNs preserved verbatim; `anthropic:` + `openai:` columns added.
- Modified: `backend/app/core/config.py` — new `LLM_PROVIDER` Literal field + `Literal` import.
- Modified: `backend/.env.example` — one new line documenting `LLM_PROVIDER`.
- New: `backend/tests/agents/test_llm_factory.py` — 8 offline unit tests.
- Modified: `_bmad-output/implementation-artifacts/sprint-status.yaml` — `9-5a-llm-py-provider-routing-refactor: ready-for-dev` → `review`.
- Modified: `docs/tech-debt.md` — new TD-082 and TD-083 entries.
- Modified: `VERSION` — `1.34.0` → `1.35.0`.
- Modified: `_bmad-output/implementation-artifacts/9-5a-llm-py-provider-routing-refactor.md` — task checkboxes, Dev Agent Record, File List, Change Log, Status.

## Senior Developer Review (AI)

**Reviewed:** 2026-04-23 by adversarial code-review workflow.
**Outcome:** Approved with fixes applied. All 11 ACs implemented; all 7 tasks genuinely done; callsite files untouched (verified via `git diff --stat`); `869 passed, 11 deselected` matches AC #8 (861 baseline + 8 new); ruff clean on touched files.

### Fixes applied during review (MEDIUM)

- **M1 — Bedrock short-circuits before Redis.** [`llm.py`](../../backend/app/agents/llm.py) `_get_client_for` now raises `NotImplementedError("Bedrock provider wiring lands in Story 9.5b")` immediately when `provider == "bedrock"`, before `check_circuit(...)` and `_resolve_model_id(...)`. Prior implementation called `check_circuit("bedrock")` and resolved the ARN first, which (a) violated the Dev Notes intent that "Bedrock circuit-breaker wiring is 9.5b" and (b) would surface a Redis connection error instead of the advertised `NotImplementedError` if Redis were unreachable under `LLM_PROVIDER=bedrock`.
- **M2 — `models.yaml` non-dict parse is now a loud `ValueError`.** [`llm.py`](../../backend/app/agents/llm.py) `_load_models_config` validates that `yaml.safe_load(...)` returned a `dict` and raises `ValueError(f"models.yaml at {path} must be a mapping of role -> provider-map (got {type})")` otherwise. Prior code would let `None` (empty file) flow through and produce a `TypeError: argument of type 'NoneType' is not iterable` from `_resolve_model_id`.

### Deferred findings (LOW)

- **L1 (story-local):** `record_failure` / `record_success` imports in [`llm.py:14`](../../backend/app/agents/llm.py#L14) are silenced with `noqa: F401` but no code in `llm.py` uses them and no callsite imports them through this module. Dead re-exports. Kept for now; pick up opportunistically when touching this file next.
- **L2 (story-local):** `CircuitBreakerOpenError` is re-exported from [`llm.py:15`](../../backend/app/agents/llm.py#L15) via `app.agents.circuit_breaker`, while the new test imports it directly from [`app.core.exceptions`](../../backend/tests/agents/test_llm_factory.py#L13). Two valid sources, no bug — the re-export is load-bearing for existing callsites and not worth churning here.
- **L3 → dropped:** "Unreachable `ValueError` defensive branch in `_build_client`" withdrawn — it is a trivial defensive nit and does not rise to debt.
- **L4 → [TD-084](../../docs/tech-debt.md). `chat_default.bedrock` ARN missing `-v*:0` version suffix; untested until Story 9.5b wires `ChatBedrock`.**
- **L5 → dropped:** `.env.example` placement of `LLM_PROVIDER` at line 1 withdrawn — cosmetic and `.env.example` is reference-only.

## Change Log

- 2026-04-23 — Story 9.5a code review: fixed M1 (bedrock short-circuits before `check_circuit`) + M2 (non-dict YAML raises `ValueError` not `TypeError`). LOW findings L1/L2 kept story-local; L3/L5 dropped; L4 promoted to TD-084. Status `review` → `done`. Tests still `869 passed, 11 deselected`; ruff clean.
- 2026-04-23 — Story 9.5a implemented + moved to `review`. Refactor landed per AC: factory routes on `settings.LLM_PROVIDER`, YAML schema extended to per-role provider-map, public API preserved, 8 new offline tests (`861 → 869 passed, 11 deselected`), ruff clean on touched files, callsite files untouched. TD-082 + TD-083 added for deferred items (roles-data-only + hardcoded fallback topology). Version bumped `1.34.0 → 1.35.0`.
- 2026-04-23 — Story 9.5a drafted: refactor `backend/app/agents/llm.py` into a `LLM_PROVIDER`-routed factory reading per-role per-provider model IDs from `backend/app/agents/models.yaml`. Extends the Story 9.4 YAML schema from flat-string to nested provider-map (adds `anthropic:` + `openai:` columns alongside the existing `bedrock:` pins). Preserves the existing `get_llm_client()` / `get_fallback_llm_client()` public API bit-for-bit so no callsite in `agents/categorization`, `agents/education`, `services/schema_detection`, or `tests/eval/rag` needs to change. Accepts `LLM_PROVIDER=bedrock` as a valid config value but raises `NotImplementedError("Bedrock provider wiring lands in Story 9.5b")` — 9.5b's diff becomes a single new case branch in `_build_client`. No runtime behavior change under default config.
