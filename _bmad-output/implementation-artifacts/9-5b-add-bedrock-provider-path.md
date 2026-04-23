# Story 9.5b: Add Bedrock Provider Path + Smoke Test

Status: done
Created: 2026-04-23
Epic: 9 — AI Infra Readiness (Bedrock Provider, RAG Eval Harness, Embedding Decision)

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **backend developer completing the Bedrock seam that Story 9.5a left open**,
I want `backend/app/agents/llm.py`'s `_build_client(...)` Bedrock branch to actually construct a LangChain `ChatBedrockConverse` client (instead of raising `NotImplementedError("Bedrock provider wiring lands in Story 9.5b")` at [llm.py:67-68](../../backend/app/agents/llm.py#L67-L68) / [llm.py:80-83](../../backend/app/agents/llm.py#L80-L83)) — wired against the Bedrock ARNs already pinned by Story 9.4 in [backend/app/agents/models.yaml](../../backend/app/agents/models.yaml), plus a new `agent_fallback` role carrying a chosen **Bedrock-hosted** fallback model (because `gpt-4o-mini` from the current opposite-of-primary fallback rule is *not* invocable on Bedrock) — and the whole path verified with a one-off local smoke test against `haiku` + `sonnet` + the chosen fallback in `eu-central-1`,
so that Story 9.5c's cross-provider regression matrix can loop `LLM_PROVIDER ∈ {anthropic, openai, bedrock}` against the same `get_llm_client()` entry-point that Epic 3/8 agents already use, Story 10.4a's AgentCore session handler inherits a working Bedrock factory without re-implementing client construction, and a future operator switching `LLM_PROVIDER=bedrock` in a non-prod environment (prod flip still blocked on ADR-0003 + Story 9.7 — out of scope here) gets a real client and not a runtime `NotImplementedError`.

## Acceptance Criteria

1. **Given** [backend/app/agents/llm.py](../../backend/app/agents/llm.py) currently raises `NotImplementedError("Bedrock provider wiring lands in Story 9.5b")` in **two** places — at [llm.py:67-68](../../backend/app/agents/llm.py#L67-L68) inside `_build_client(...)` and at [llm.py:80-83](../../backend/app/agents/llm.py#L80-L83) inside `_get_client_for(...)` (the latter is the "short-circuit before Redis" safeguard added during the 9.5a review per M1 in that story's Senior Developer Review) — **When** this story completes **Then** both raises are replaced with real Bedrock wiring:
   - `_build_client("bedrock", model_id)` constructs a `langchain_aws.ChatBedrockConverse(model=model_id, region_name="eu-central-1", provider="anthropic")` and returns it. The import is **lazy** (inside the `if provider == "bedrock":` branch, matching the lazy-import pattern already used for `ChatAnthropic` / `ChatOpenAI` at [llm.py:61-66](../../backend/app/agents/llm.py#L61-L66)) so that `langchain-aws` import cost is not paid by test runs or processes that never touch Bedrock.
   - `_get_client_for("bedrock")` no longer short-circuits. Instead it follows the same sequence as the `anthropic` / `openai` branches: `check_circuit("bedrock")` → skip `_validate_api_key("bedrock")` (there is no API-key env var for Bedrock — credentials come from the boto3 default credentials chain: `AWS_PROFILE` / env vars / ECS task role) → `_resolve_model_id(role, "bedrock")` → `_build_client("bedrock", model_id)`. The `"bedrock"` circuit-breaker key joins `"anthropic"` and `"openai"` as a first-class provider key at the [circuit_breaker.py](../../backend/app/agents/circuit_breaker.py) layer (no code change required in `circuit_breaker.py` — its `_FAILURE_KEY` / `_OPEN_KEY` are already provider-parameterized).

2. **Given** Story 9.5a's `_FALLBACK_MAP` at [llm.py:19](../../backend/app/agents/llm.py#L19) currently sends `"bedrock" → "bedrock"` (which previously hit the `NotImplementedError` short-circuit) and the epic description of this story states explicitly *"Choose + document Bedrock-hosted fallback model (gpt-4o-mini is not on Bedrock)"* ([epics.md line 2059](../../_bmad-output/planning-artifacts/epics.md#L2059)) **When** this story lands **Then** the fallback topology is extended so that under `LLM_PROVIDER=bedrock`, `get_fallback_llm_client()` returns a **different** Bedrock model (not the same Haiku as primary — a useless same-ARN round-trip — and not an Anthropic-direct or OpenAI client, because the epic mandates a **Bedrock-hosted** fallback). Concretely:
   - A new top-level role **`agent_fallback`** is added to [backend/app/agents/models.yaml](../../backend/app/agents/models.yaml) with all three provider columns populated. The `bedrock:` entry is the fallback Bedrock model chosen during Task 3's smoke test; the `anthropic:` and `openai:` entries mirror `agent_default` verbatim (they are data-only for symmetry — the non-bedrock primary path still resolves `agent_default` under the existing opposite-of-primary rule and never consults `agent_fallback`). Exact candidate for `agent_fallback.bedrock`: **Amazon Nova Micro** (`arn:aws:bedrock:eu-central-1:573562677570:inference-profile/eu.amazon.nova-micro-v1:0`) **or** Amazon Nova Lite (`eu.amazon.nova-lite-v1:0`) — whichever Task 3's inventory confirms is available as an EU-scoped inference profile (no `global.*` routing, which would defeat the GDPR rationale behind ADR-0003's `eu.*` choice). If neither Nova profile is EU-scoped in `eu-central-1` at test time, fall back to `eu.anthropic.claude-haiku-3-5-20241022-v1:0` (older Haiku family — same Anthropic provider, cheaper tier than the Haiku 4.5 primary). The chosen ARN is recorded verbatim in `models.yaml` and in the decision doc from Task 6.
   - `get_fallback_llm_client()` is updated so that when `settings.LLM_PROVIDER == "bedrock"` it resolves role **`agent_fallback`** against provider `"bedrock"` (not `agent_default`). When `LLM_PROVIDER` is `anthropic` or `openai`, the existing opposite-of-primary rule (resolving `agent_default` against the opposite provider) is **preserved bit-for-bit** — no behavior change for current prod + local-dev deployments, which all run under the default `LLM_PROVIDER=anthropic`.
   - `_FALLBACK_MAP` is kept as a dict; the `"bedrock": "bedrock"` entry stays (the fallback *provider* is still bedrock; only the *role* differs). A small private helper — e.g. `_fallback_role_for(primary: str) -> str` returning `"agent_fallback"` if `primary == "bedrock"` else `"agent_default"` — captures the rule so the 8-test file in Story 9.5a (`test_llm_factory.py`) can assert on it without depending on construction side-effects.

3. **Given** the project's dependency manifest at [backend/pyproject.toml](../../backend/pyproject.toml) currently pins `boto3>=1.42.73`, `langchain-anthropic>=0.3.0`, `langchain-core>=0.3.0`, `langchain-openai>=0.3.0` — but **not** `langchain-aws` — **When** this story ships **Then** `langchain-aws>=0.2.0` (pick the latest-compatible pin at commit time; 0.2.x ships `ChatBedrockConverse`) is added to the `dependencies` array in [pyproject.toml](../../backend/pyproject.toml), `uv lock` is run to refresh [backend/uv.lock](../../backend/uv.lock), and `uv sync` resolves without conflict on a clean `backend/.venv`. No other dependency pin changes in this story (avoid drive-by version bumps — any `langchain-*` coupled upgrade belongs to a separate story). Verify the installed `ChatBedrockConverse` signature supports the three kwargs used in AC #1 (`model`, `region_name`, `provider`) before writing the assertion in the new tests from AC #7 — LangChain-AWS 0.2.x has been renaming `model` / `model_id` arguments between point releases.

4. **Given** the smoke-test deliverable (epic description: "Smoke-test against haiku + sonnet in `eu-central-1` (or fallback region per Story 9.4)") matches the pattern already established by Story 9.4's invoke-tests **When** this story completes **Then** a committed evidence capture lands at:
   - `docs/decisions/bedrock-provider-smoke-2026-04.md` — a short decision doc (≤ ~60 lines) with sections: **Context** (pointer to Story 9.4 + this story + ADR-0003), **Tested Inventory** (markdown table: tier | role | modelId / ARN | region | direct vs inference-profile | result | latency ms), **Fallback Model Decision** (which Bedrock-hosted model was chosen for `agent_fallback.bedrock` and why — address Nova Micro vs Nova Lite vs Haiku-3.5 trade-offs in 3–5 bullets), **Re-run instructions** (exact boto3 invocation used), **Status note** (one line stating production runtime flip to `LLM_PROVIDER=bedrock` is **still blocked** on ADR-0003 acceptance + Story 9.7 IAM).
   - `docs/decisions/bedrock-provider-smoke-2026-04/smoke-tests.json` — raw evidence JSON with three top-level keys: `haiku_invoke_test`, `sonnet_invoke_test`, `fallback_invoke_test`. Each carries `modelId`, `region`, `http_status`, `latency_ms`, `timestamp` (ISO-8601, UTC), `prompt`, `response_text_first_80_chars`, and a `meta` block with `timestamp_semantics: "invocation_start"` (copy the Story 9.4 convention).
   - The smoke test uses the **same local-dev AWS credential pattern** as Story 9.4 ([9-4-agentcore-bedrock-region-availability-spike.md AC #6](./9-4-agentcore-bedrock-region-availability-spike.md)) — no Terraform / IAM task-role changes (Story 9.7 owns those). The redacted `aws sts get-caller-identity` (account id only) goes into the decision doc's Re-run instructions, **not** the JSON capture.

5. **Given** ADR-0003 ([docs/adr/0003-cross-region-inference-data-residency.md](../../docs/adr/0003-cross-region-inference-data-residency.md)) is currently **`Status: Proposed`** and explicitly gates Bedrock cross-region inference for production ("Story 9.5b's cross-region inference path is **blocked** on this flipping to Accepted") **When** this story ships **Then** the production runtime default stays **`LLM_PROVIDER=anthropic`** — no edit to [backend/.env.example](../../backend/.env.example) or deployment config flips the default. The Bedrock path is **wired in code** and **exercised by tests + local smoke**, but any environment that sets `LLM_PROVIDER=bedrock` is implicitly opting in to a cross-region inference path that is not yet Legally approved. The decision doc from AC #4 must state this constraint in one bold sentence (e.g. *"This story ships the code path but does not flip any deployed environment — production activation remains blocked on ADR-0003 acceptance and Story 9.7 (ECS task-role IAM)."*). Similarly, the story does **not** edit any of the five call sites from Story 9.5a's AC #3 ([categorization/node.py](../../backend/app/agents/categorization/node.py), [education/node.py](../../backend/app/agents/education/node.py), [services/schema_detection.py](../../backend/app/services/schema_detection.py), [tests/eval/rag/candidates/runner.py](../../backend/tests/eval/rag/candidates/runner.py), [tests/eval/rag/judge.py](../../backend/tests/eval/rag/judge.py)) — they continue to consume the unchanged `get_llm_client()` / `get_fallback_llm_client()` public API.

6. **Given** Story 9.5a's factory preserves existing `ValueError` / `KeyError` contracts for missing API keys and missing roles/providers (AC #6 in that story) **When** the Bedrock path lands **Then** the error-handling contract extends cleanly:
   - `_validate_api_key("bedrock")` is a **no-op** (Bedrock uses the boto3 credentials chain, not a settings-field API key). Do not invent a `BEDROCK_API_KEY` field in [config.py](../../backend/app/core/config.py) — add no new settings field in this story.
   - A missing role under `"bedrock"` still raises the existing `KeyError("Role '<role>' not found in models.yaml ...")` from `_resolve_model_id` ([llm.py:47-50](../../backend/app/agents/llm.py#L47-L50)).
   - A missing `<role>.bedrock` sub-key raises the existing `KeyError("Role '<role>' has no 'bedrock' entry in models.yaml ...")` from `_resolve_model_id` ([llm.py:52-56](../../backend/app/agents/llm.py#L52-L56)).
   - If `ChatBedrockConverse` construction itself fails at call time (wrong ARN, bad region, boto3 can't resolve credentials), the exception is allowed to propagate — no try/except swallowing. The circuit-breaker's `record_failure("bedrock")` is called by the **caller** on downstream invoke failure, same as today's anthropic/openai paths (the factory only constructs; per-call failure accounting lives in callers).

7. **Given** Story 9.5a's test module at [backend/tests/agents/test_llm_factory.py](../../backend/tests/agents/test_llm_factory.py) currently contains an 8-function suite with the Bedrock branch covered only by the `test_bedrock_primary_raises_not_implemented` test at [test_llm_factory.py:46-51](../../backend/tests/agents/test_llm_factory.py#L46-L51) **When** this story lands **Then** that single negative test is replaced with **positive coverage** of the now-wired Bedrock path, plus 3 new tests covering the new fallback topology. Specifically:
   - **Replace** `test_bedrock_primary_raises_not_implemented` with `test_bedrock_primary_returns_chat_bedrock_client`: monkeypatches `langchain_aws.ChatBedrockConverse` to a sentinel class (so the test does not require real AWS credentials or network access), sets `monkeypatch.setenv("AWS_PROFILE", "test-fake")` for good measure, asserts `type(get_llm_client()).__name__ == "<sentinel>"` and that the sentinel was called with `model=<expected-haiku-arn>`, `region_name="eu-central-1"`, `provider="anthropic"`.
   - **Add** `test_bedrock_fallback_resolves_agent_fallback_role`: with `LLM_PROVIDER=bedrock` and the sentinel monkeypatch from the previous test, asserts that `get_fallback_llm_client()` is called with `model=<agent_fallback.bedrock ARN from models.yaml>` (not the `agent_default.bedrock` ARN). This locks the role-level distinction from AC #2.
   - **Add** `test_bedrock_circuit_open_blocks_construction`: analogous to the existing `test_circuit_breaker_open_blocks_client_construction` test at [test_llm_factory.py:94-113](../../backend/tests/agents/test_llm_factory.py#L94-L113), but with `LLM_PROVIDER=bedrock`. Patches `check_circuit` to raise `CircuitBreakerOpenError("bedrock")`; asserts the sentinel `ChatBedrockConverse` was **not** called and the exception surfaces. Locks AC #1's "check_circuit('bedrock') now actually runs before construction" behavior.
   - **Add** `test_non_bedrock_primary_fallback_topology_unchanged`: regression test — with `LLM_PROVIDER=anthropic`, assert `get_fallback_llm_client()` still returns `ChatOpenAI(model="gpt-4o-mini")` (existing behavior from [test_llm_factory.py:35-43](../../backend/tests/agents/test_llm_factory.py#L35-L43)); with `LLM_PROVIDER=openai`, still returns `ChatAnthropic(model="claude-haiku-4-5-20251001")`. This covers the "opposite-of-primary is still opposite-of-primary for non-bedrock primaries" part of AC #2 and prevents a careless refactor from regressing the 9.5a behavior.
   - New test count: **same 8 functions** (replace 1 + add 3 = net +3, but the existing `test_bedrock_primary_raises_not_implemented` merges into `test_bedrock_primary_returns_chat_bedrock_client` — so 8 → 11 functions net, delta +3). Target file length: ≤ ~200 lines.
   - All tests remain **offline**: no real boto3 `ChatBedrockConverse` construction, no real AWS API calls, no Redis. Monkeypatch `langchain_aws.ChatBedrockConverse` to the sentinel **at the import path `llm_module` sees** (i.e. `monkeypatch.setattr(llm_module, "langchain_aws"` is wrong because the import is lazy; instead `monkeypatch.setattr("langchain_aws.ChatBedrockConverse", SentinelClient)` which mutates the lazy-imported module at call time).

8. **Given** the default test sweep target from Story 9.5a close-out is **`869 passed, 11 deselected`** ([9-5a-llm-py-provider-routing-refactor.md](./9-5a-llm-py-provider-routing-refactor.md) Debug Log References) **When** this story ships **Then** after the test-module edits from AC #7 the sweep reads **`869 + Δ passed, 11 deselected`** where `Δ = +3` (8 → 11 test functions in `test_llm_factory.py`). No existing test is deleted, skipped, or modified except `test_bedrock_primary_raises_not_implemented` which is **replaced** (not extended) per AC #7. If any of the five non-edited call-site files from AC #5 shows a diff — `git diff --stat backend/app/agents/categorization/node.py backend/app/agents/education/node.py backend/app/services/schema_detection.py backend/tests/eval/rag/candidates/runner.py backend/tests/eval/rag/judge.py` → MUST be empty — the refactor has regressed the 9.5a public-API preservation guarantee and the PR is rejected.

9. **Given** `ruff` is the project linter ([backend/pyproject.toml](../../backend/pyproject.toml)) **When** the story ships **Then** `uv run ruff check backend/app/agents/llm.py backend/app/agents/models.yaml backend/tests/agents/test_llm_factory.py` returns zero findings. (`models.yaml` is not a Python file so `ruff` ignores it — but listing it is harmless; keep the command copy-pasteable.) Repo-wide ruff drift from TD-068 is out of scope.

10. **Given** `docs/tech-debt.md` tracks deferred work with `TD-NNN` IDs (highest current = **TD-084** per the existing register) **When** this refactor surfaces any deferred item **Then** each becomes a `TD-085+` entry. Expected candidates:
    - (a) `agent_fallback.bedrock` is a **best-guess** Bedrock-hosted fallback choice pending the first real circuit-breaker trip in a pre-prod environment — if it turns out to be under-tiered (Nova Micro outputs too short for Haiku-replacement calls) or over-tiered (Haiku 3.5 same cost as Haiku 4.5), the choice will need revision.
    - (b) The `_fallback_role_for(primary)` helper (AC #2) is a second hardcoded fallback-topology rule on top of the `_FALLBACK_MAP` dict already flagged as TD-083 — a YAML-level expression (`roles.<role>.fallback_role: <role>`) would unify them but is out-of-scope for 9.5b. If taken, this extends TD-083 rather than creating a new entry — **update** TD-083 in place with a note + pointer to this story.
    - (c) **TD-084** (missing `-v*:0` version suffix on `chat_default.bedrock` in `models.yaml`) was deferred by 9.5a because no Bedrock client was wired. **This story wires the Bedrock client** — if the smoke test from Task 3 reveals that `chat_default.bedrock`'s current ARN format does/does not accept the call, resolve TD-084 by updating the ARN verbatim in `models.yaml` and mark TD-084 `RESOLVED` in the register with the smoke-test date. If the smoke does not exercise `chat_default` (which is Epic 10's role, not wired into any Epic 3/8 agent) defer TD-084 further to Story 10.4a.
    - (d) Bedrock-direct prod runtime is **still blocked** on ADR-0003 acceptance + Story 9.7 IAM — this is a *process* debt, not a code debt, and does not deserve a TD entry unless one of the gates slips past a sprint boundary.
    - If none of (a)/(b) applies and TD-084 does not change state, add no TD entries.

11. **Given** sprint-status.yaml tracks story state **When** the story is ready for dev **Then** `_bmad-output/implementation-artifacts/sprint-status.yaml`'s `9-5b-add-bedrock-provider-path:` key is flipped `backlog` → `ready-for-dev` by the create-story workflow (this file), and on story close-out the implementing dev flips it to `review` (code-review flips to `done` per the normal flow). The existing two pointer comments above that line (from Story 9.4 — region/ARN pointer; from Story 9.5a — factory-ready pointer; the ADR-0003-block note) are **preserved verbatim**; one additional pointer line is appended above `9-5c-cross-provider-regression-suite:` reading `# Story 9.5b: Bedrock path wired; 9.5c can now loop LLM_PROVIDER ∈ {anthropic,openai,bedrock}.`

## Tasks / Subtasks

- [x] Task 1: Capture baseline + plan the diff (AC: #8, #9)
  - [x] 1.1 From `backend/` with the `backend/.venv` active (per memory `feedback_python_venv.md`), run `uv run pytest tests/ -q` and confirm the baseline **`869 passed, 11 deselected`** (Story 9.5a close-out). If drift is observed on `main`, record the current count as this story's baseline and carry it forward into AC #8 — do not investigate drift.
  - [x] 1.2 Re-read [backend/app/agents/llm.py](../../backend/app/agents/llm.py) and confirm the two `NotImplementedError("Bedrock provider wiring lands in Story 9.5b")` raises at [llm.py:67-68](../../backend/app/agents/llm.py#L67-L68) (inside `_build_client`) and [llm.py:80-83](../../backend/app/agents/llm.py#L80-L83) (inside `_get_client_for`, the 9.5a-review M1 short-circuit). Both are removed by this story; the comment block above the short-circuit at `llm.py:81-82` is also removed.
  - [x] 1.3 Read [backend/app/agents/models.yaml](../../backend/app/agents/models.yaml) verbatim. Capture the exact `eu.anthropic.claude-haiku-4-5-20251001-v1:0` and `eu.anthropic.claude-sonnet-4-6` ARNs into a scratch buffer so Task 3's smoke test uses byte-identical ARNs (no copy/paste drift).

- [x] Task 2: Add `langchain-aws` dependency (AC: #3)
  - [x] 2.1 Edit [backend/pyproject.toml](../../backend/pyproject.toml)'s `dependencies` array: add `"langchain-aws>=0.2.0"` alphabetically between `langchain-anthropic` and `langchain-core`. Do not bump any other pin.
  - [x] 2.2 From `backend/`, run `uv lock` (refresh lockfile) then `uv sync` (apply to `.venv`). Confirm both exit 0. Scan `uv sync`'s output for "Downloading" lines — confirm `langchain-aws` and its transitive deps (`boto3`, `botocore`, etc.) resolved without pin conflicts.
  - [x] 2.3 Verify `ChatBedrockConverse` import + signature: `uv run python -c "from langchain_aws import ChatBedrockConverse; import inspect; print(inspect.signature(ChatBedrockConverse.__init__))"`. Confirm `model`, `region_name`, `provider` are accepted keyword arguments in the installed version (LangChain-AWS 0.2.x has occasionally renamed `model` / `model_id` between point releases — if `model` is not accepted in the installed version, use whatever name IS accepted and note the discrepancy in the decision doc; hardcoding a mismatched kwarg breaks the runtime).

- [x] Task 3: Smoke-test Bedrock models + pick fallback model (AC: #2, #4)
  - [x] 3.1 With local AWS creds (same pattern as Story 9.4 AC #6: `AWS_PROFILE` or `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY`), invoke Haiku primary:
    ```
    aws bedrock-runtime invoke-model \
      --region eu-central-1 \
      --model-id "arn:aws:bedrock:eu-central-1:573562677570:inference-profile/eu.anthropic.claude-haiku-4-5-20251001-v1:0" \
      --body '{"anthropic_version":"bedrock-2023-05-31","max_tokens":16,"messages":[{"role":"user","content":"ping — reply with the word OK"}]}' \
      --cli-binary-format raw-in-base64-out \
      /tmp/sp95b-haiku.json
    ```
    Capture HTTP status, round-trip latency (via `time`), and first 80 chars of `content[0].text`. Record in `docs/decisions/bedrock-provider-smoke-2026-04/smoke-tests.json` under key `haiku_invoke_test`.
  - [x] 3.2 Repeat Task 3.1 for Sonnet primary — model-id `arn:aws:bedrock:eu-central-1:573562677570:inference-profile/eu.anthropic.claude-sonnet-4-6`. Capture under `sonnet_invoke_test`. If the current sonnet ARN format rejects the call with `ValidationException` about an invalid ARN shape (possible — TD-084 flagged this ARN as missing `-v*:0` version suffix), try `arn:aws:bedrock:eu-central-1:573562677570:inference-profile/eu.anthropic.claude-sonnet-4-6-v1:0` next. If the corrected form works, record the corrected ARN in `smoke-tests.json` and update [backend/app/agents/models.yaml](../../backend/app/agents/models.yaml)'s `chat_default.bedrock` verbatim; mark TD-084 `RESOLVED` per AC #10 candidate (c). If neither form works, capture the exact AWS error into `smoke-tests.json` and defer to Task 6's decision doc (do **not** silently commit a broken ARN).
  - [x] 3.3 Inventory Bedrock-hosted fallback candidates for `agent_fallback.bedrock`. Preferred: Amazon Nova Micro or Lite with an EU-scoped inference profile. Inventory them:
    ```
    aws bedrock list-inference-profiles --region eu-central-1 \
      --query 'inferenceProfileSummaries[?contains(inferenceProfileId,`nova`) || contains(inferenceProfileId,`claude-haiku-3`)].[inferenceProfileId,inferenceProfileArn]' \
      --output table
    ```
    If any row's `inferenceProfileId` starts with `eu.amazon.nova-micro-*` or `eu.amazon.nova-lite-*`, it's a valid EU-scoped candidate. If only `global.amazon.nova-*` profiles exist (route to `us-*`), those are **rejected** per AC #2 GDPR rationale — pick `eu.anthropic.claude-haiku-3-5-20241022-v1:0` (or whichever Haiku-3.5 EU profile exists) as the fallback instead.
  - [x] 3.4 Invoke the chosen fallback candidate with the same "ping" prompt (body shape may differ for Nova — Nova's body is `{"messages": [...], "inferenceConfig": {"maxTokens": 16}}` rather than Anthropic's bedrock envelope; consult the AWS Nova Converse docs at call time). Record latency + status + response first-80-chars under `fallback_invoke_test` in `smoke-tests.json`.
  - [x] 3.5 Edit [backend/app/agents/models.yaml](../../backend/app/agents/models.yaml): append a new role `agent_fallback:` block at the end of the file, with `anthropic:`, `openai:`, `bedrock:` sub-keys per AC #2. Copy the chosen fallback ARN verbatim into `agent_fallback.bedrock`. `anthropic: "claude-haiku-4-5-20251001"` and `openai: "gpt-4o-mini"` (mirror `agent_default`'s non-bedrock entries — they are schema completeness only; non-bedrock primaries do not consult `agent_fallback`).
  - [x] 3.6 Validate the file parses: from repo root with backend venv active, `python -c "import yaml, pathlib; d = yaml.safe_load(pathlib.Path('backend/app/agents/models.yaml').read_text()); assert set(d) == {'agent_default', 'agent_cheap', 'chat_default', 'agent_fallback'}; assert all({'anthropic', 'openai', 'bedrock'} <= set(v.keys()) for v in d.values()); print(d)"`. Output must show four roles with all three provider sub-keys.

- [x] Task 4: Wire the Bedrock branch into `llm.py` (AC: #1, #2, #6)
  - [x] 4.1 Edit [backend/app/agents/llm.py](../../backend/app/agents/llm.py): replace the Bedrock branch in `_build_client` ([llm.py:67-68](../../backend/app/agents/llm.py#L67-L68)) with:
    ```python
    if provider == "bedrock":
        from langchain_aws import ChatBedrockConverse
        return ChatBedrockConverse(
            model=model_id,
            region_name="eu-central-1",
            provider="anthropic",
        )
    ```
    The `provider="anthropic"` kwarg tells `ChatBedrockConverse` which request body schema to use — Anthropic-flavored (which matches the Haiku + Sonnet primary ARNs). If `agent_fallback.bedrock` ends up being an Amazon Nova ARN, `ChatBedrockConverse` auto-detects the body shape from the ARN prefix at invoke time — the `provider=` kwarg hints the primary path; Nova fallback works because LangChain-AWS uses the ARN provider-prefix (`eu.amazon.*`) as override. Confirm via the Task 2.3 signature inspection before committing the kwarg list.
  - [x] 4.2 Remove the `_get_client_for` short-circuit at [llm.py:80-83](../../backend/app/agents/llm.py#L80-L83) (the entire `if provider == "bedrock": raise NotImplementedError(...)` block including the two-line comment above it). After removal the function reads linearly: `check_circuit(provider) → _validate_api_key(provider) → _resolve_model_id(...) → _build_client(...)` — same sequence for all three providers.
  - [x] 4.3 Update `_validate_api_key` at [llm.py:72-76](../../backend/app/agents/llm.py#L72-L76): add an early `if provider == "bedrock": return None` (or equivalent) to document the intentional no-op — Bedrock credentials come from the boto3 chain, not a `*_API_KEY` setting. A bare `pass` inside an `elif provider == "bedrock":` branch is fine; the point is that the function signals "bedrock by design has no API key to validate" rather than implicitly falling through.
  - [x] 4.4 Implement the AC #2 fallback-role rule. Add a private helper just below `_FALLBACK_MAP`:
    ```python
    _FALLBACK_ROLE_MAP = {"anthropic": "agent_default", "openai": "agent_default", "bedrock": "agent_fallback"}

    def _fallback_role_for(primary: str) -> str:
        return _FALLBACK_ROLE_MAP[primary]
    ```
    Rewrite `get_fallback_llm_client` ([llm.py:100-106](../../backend/app/agents/llm.py#L100-L106)) to resolve the fallback provider via `_FALLBACK_MAP[primary]` **and** the fallback role via `_fallback_role_for(primary)`, then call a new `_get_client_for(provider, role)` that accepts the role as an optional second arg defaulting to `_PRIMARY_ROLE`. This keeps `get_llm_client()` calling `_get_client_for(settings.LLM_PROVIDER)` with the default role and `get_fallback_llm_client()` passing the explicit fallback role.
  - [x] 4.5 `uv run ruff check backend/app/agents/llm.py` → zero findings.

- [x] Task 5: Update unit tests (AC: #7, #8, #9)
  - [x] 5.1 Edit [backend/tests/agents/test_llm_factory.py](../../backend/tests/agents/test_llm_factory.py). Delete `test_bedrock_primary_raises_not_implemented` (lines [46-51](../../backend/tests/agents/test_llm_factory.py#L46-L51)). Add the four tests enumerated in AC #7.
  - [x] 5.2 For the `ChatBedrockConverse` sentinel pattern: define a local `_BedrockSentinel` class that captures constructor kwargs into instance attributes, then `monkeypatch.setattr("langchain_aws.ChatBedrockConverse", _BedrockSentinel)` inside each bedrock test. Because `_build_client` imports `ChatBedrockConverse` lazily via `from langchain_aws import ChatBedrockConverse`, the monkeypatch must target the module attribute **at `langchain_aws.ChatBedrockConverse`**, not the `llm_module` namespace — the import statement reads the attribute freshly on each call.
  - [x] 5.3 For `test_bedrock_fallback_resolves_agent_fallback_role`, assert on the `model` kwarg captured by `_BedrockSentinel` — it must equal the `agent_fallback.bedrock` value from `models.yaml`, NOT the `agent_default.bedrock` value. Use a `tmp_path` fixture + `LLM_MODELS_CONFIG_PATH` override to pin the expected ARN as a known fixture (avoids coupling the test to whatever `agent_fallback.bedrock` ends up being in the committed `models.yaml` — the fixture test should still pass even if the operational fallback ARN changes in a later TD-resolution).
  - [x] 5.4 For `test_bedrock_circuit_open_blocks_construction`: patch `check_circuit` to raise `CircuitBreakerOpenError("bedrock")` specifically when called with `"bedrock"`, and assert that `_BedrockSentinel` was **not** instantiated (use a `call_count` attribute on the sentinel; assert it stays at 0).
  - [x] 5.5 For `test_non_bedrock_primary_fallback_topology_unchanged`: simply re-parameterize the existing `test_primary_switch_to_openai` logic — this is a regression lock, it does not need novel assertions; the point is that CI notices if someone breaks the anthropic ↔ openai opposite-of-primary rule while editing `get_fallback_llm_client`.
  - [x] 5.6 Run `uv run pytest tests/agents/test_llm_factory.py -q -v` — all 11 tests pass.

- [x] Task 6: Write the smoke decision doc (AC: #4, #5)
  - [x] 6.1 Create `docs/decisions/bedrock-provider-smoke-2026-04/` directory if not already present. Create `docs/decisions/bedrock-provider-smoke-2026-04/smoke-tests.json` populated from Tasks 3.1, 3.2, 3.4 raw captures, with the `meta` block carrying `timestamp_semantics: "invocation_start"` (match Story 9.4 convention).
  - [x] 6.2 Create `docs/decisions/bedrock-provider-smoke-2026-04.md` with the section order from AC #4: Context → Tested Inventory → Fallback Model Decision → Re-run instructions → Status note. Keep it ≤ ~60 lines. In the Tested Inventory table, each row names a logical role (`agent_default`, `chat_default`, `agent_fallback`) so a future reader can trace it back to `models.yaml`.
  - [x] 6.3 In the **Status note** section, include the literal bolded sentence required by AC #5: *"This story ships the code path but does not flip any deployed environment — production activation remains blocked on ADR-0003 acceptance and Story 9.7 (ECS task-role IAM)."*
  - [x] 6.4 In the Fallback Model Decision section, address the Nova Micro / Nova Lite / Haiku-3.5 trade-off — latency, cost per 1M input tokens (use AWS published pricing pages at commit time), EU-region availability, and whether the chosen model carries over to Epic 10's chat use case. The writer is not locked into a specific choice — document the choice that Task 3.4's smoke-test actually validated.

- [x] Task 7: Full regression + no-untouched-callsite verification (AC: #5, #8)
  - [x] 7.1 `git status` + `git diff --stat` — confirm the only code files modified are `backend/app/agents/llm.py`, `backend/app/agents/models.yaml`, `backend/pyproject.toml`, `backend/uv.lock`, and `backend/tests/agents/test_llm_factory.py`. The five 9.5a-AC-#3 callsite files MUST be **unchanged**: `git diff --stat backend/app/agents/categorization/node.py backend/app/agents/education/node.py backend/app/services/schema_detection.py backend/tests/eval/rag/candidates/runner.py backend/tests/eval/rag/judge.py` → empty.
  - [x] 7.2 From `backend/`, run `uv run pytest tests/ -q`. Confirm count matches AC #8: **`872 passed, 11 deselected`** (869 from 9.5a close-out + 3 net-new test functions in `test_llm_factory.py`). If drift on main pushed the baseline elsewhere between story start and end, log the adjusted number in the Dev Agent Record.
  - [x] 7.3 Quick human-loop smoke: from `backend/` with real AWS creds + `LLM_PROVIDER=bedrock`, `uv run python -c "from app.agents.llm import get_llm_client; c = get_llm_client(); print(type(c).__name__, getattr(c, 'model', None) or getattr(c, 'model_id', None))"` → prints `ChatBedrockConverse` + the haiku ARN. Repeat for `get_fallback_llm_client()` → prints `ChatBedrockConverse` + the fallback ARN. Not a committed test; a 30-second sanity check.

- [x] Task 8: Update tracking + version (AC: #10, #11)
  - [x] 8.1 Apply AC #10 candidate handling:
    - **(a)** If the chosen fallback model is a known-gamble (e.g. Nova Micro's context window may be short for some Epic 3/8 prompts), add `TD-085` [LOW] with a one-line pointer back to this story file + the smoke decision doc.
    - **(b)** If the `_fallback_role_for` helper landed, **update** [TD-083](../../docs/tech-debt.md#TD-083) in place (do not create a duplicate entry) with: "Second hardcoded fallback-topology rule added in Story 9.5b via `_fallback_role_for`; unifying both rules into `models.yaml` remains deferred."
    - **(c)** If Task 3.2 resolved the missing `-v*:0` suffix on `chat_default.bedrock`, mark **[TD-084](../../docs/tech-debt.md#TD-084)** `RESOLVED` with the smoke-test date. If not exercised, leave TD-084 as-is.
    - **(d)** No TD entry for process gates (ADR-0003 + 9.7) — they are tracked in their own artifacts.
  - [x] 8.2 Edit `_bmad-output/implementation-artifacts/sprint-status.yaml`:
    - Flip `9-5b-add-bedrock-provider-path:` from `ready-for-dev` → `review` at story close (NOT in this create-story step — that's the implementing dev's close-out).
    - Preserve the existing comment block above `9-5b-add-bedrock-provider-path:` (the Story 9.4 region/ARN pointer + the 9.5a factory-ready pointer + the ADR-0003 block note) verbatim.
    - Append one new comment line **above `9-5c-cross-provider-regression-suite:`** reading: `# Story 9.5b: Bedrock path wired; 9.5c can now loop LLM_PROVIDER ∈ {anthropic,openai,bedrock}.`
  - [x] 8.3 Bump [VERSION](../../VERSION) from `1.35.0` → `1.36.0` (MINOR) per the project's "any story = MINOR" convention (matches the 9.5a 1.34.0 → 1.35.0 bump).
  - [x] 8.4 Commit as a single PR titled `Story 9.5b: Add Bedrock provider path + smoke test`. Expected diff surface: ~30 lines in `llm.py`, ~6 lines in `models.yaml`, 1 line in `pyproject.toml`, lockfile churn (auto), ~40 lines in `test_llm_factory.py`, new decision doc (~60 lines) + JSON evidence (~40 lines), 1 line in `VERSION`, 2 lines in `sprint-status.yaml`. Total ≤ ~200 lines excluding `uv.lock`.

## Dev Notes

### Scope discipline

This story **completes** the Bedrock factory seam opened by Story 9.5a. OFF-LIMITS:

- Any edit to the five 9.5a-AC-#3 callsite files ([categorization/node.py](../../backend/app/agents/categorization/node.py), [education/node.py](../../backend/app/agents/education/node.py), [services/schema_detection.py](../../backend/app/services/schema_detection.py), [tests/eval/rag/candidates/runner.py](../../backend/tests/eval/rag/candidates/runner.py), [tests/eval/rag/judge.py](../../backend/tests/eval/rag/judge.py)) — they consume the unchanged `get_llm_client` / `get_fallback_llm_client` public API, and Story 9.5a's regression surface depends on zero churn there.
- Any Terraform / IAM change — Story 9.7 owns ECS task-role permissions for `bedrock:InvokeModel` / `bedrock:ApplyGuardrail` / `bedrock-agentcore:*`. The smoke test here runs with local dev creds only, same as Story 9.4.
- Any edit to [.env.example](../../backend/.env.example) or deployment config that flips a production environment to `LLM_PROVIDER=bedrock` — AC #5 is explicit: production runtime stays `anthropic` until ADR-0003 flips and Story 9.7 ships.
- Any new settings field in [config.py](../../backend/app/core/config.py) — Bedrock has no `*_API_KEY` field; the boto3 credentials chain is the auth surface, and that is configured outside Python.
- Any change to [backend/app/agents/circuit_breaker.py](../../backend/app/agents/circuit_breaker.py) — its provider keys are already string-parameterized; adding `"bedrock"` as a first-class key is a caller-side change, not a circuit_breaker-side change.
- Any cross-region inference profile beyond the `eu.*` ARNs already pinned by 9.4 — `global.*` profiles route to `us-*` and are explicitly rejected per ADR-0003 rationale.

If a task tempts you to "productize" the smoke-test script as a committed pytest test that talks to real AWS — stop. That is Story 9.5c's matrix runner scope. The 9.5b smoke is a one-off invoke for the decision doc, not a CI-able artifact.

### Why `ChatBedrockConverse` and not `ChatBedrock`

LangChain-AWS ships two Bedrock chat classes: `ChatBedrock` (older, uses the deprecated `InvokeModel` endpoint and each provider's proprietary request body) and `ChatBedrockConverse` (newer, uses the unified Bedrock **Converse API** — a provider-agnostic `messages/content` envelope that is the documented-forward path per AWS docs). The Converse API is what AgentCore's session handler (Story 10.4a) will use, and it's the only Bedrock class with first-class tool-use + streaming support in LangChain 0.3.x. Pinning `ChatBedrockConverse` here avoids a migration in Story 10.4a. If the pinned LangChain-AWS version only exposes `ChatBedrock` (0.1.x), the story is blocked — call out the version gap and either bump langchain-aws or defer.

### Why `agent_fallback` is a separate role (not a per-role `fallback_model_id` field)

AC #2's new `agent_fallback` role is the minimum-viable schema shape that accommodates a Bedrock-hosted fallback without changing `models.yaml`'s existing `{role → {provider → model-id}}` structure. A richer design would hoist fallback topology into a per-role `fallback:` sub-field (e.g. `agent_default.bedrock_fallback: <arn>`) — but that duplicates the concept of a role and fights against the existing shape. Introducing `agent_fallback` as a peer role keeps the schema flat and makes it trivial for Epic 10 / Story 9.5c to reference: "the fallback to Bedrock's `agent_default` is Bedrock's `agent_fallback`; same dict lookup pattern, no special sub-field". TD-083 already tracks the larger "fallback topology should live in YAML, not Python" cleanup; this story merely extends that rule by one entry rather than re-architecting it.

### Boto3 credentials chain for local smoke + tests

The smoke test (Task 3) uses the developer's local AWS creds (`AWS_PROFILE` or `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY`). For the unit tests (Task 5), no credentials are needed because `ChatBedrockConverse` is monkeypatched to a sentinel — no real boto3 client is constructed. **Do not** `monkeypatch.setenv("AWS_ACCESS_KEY_ID", ...)` with real values in tests; do set it to a fake like `"test-fake"` if a particular version of `langchain-aws` requires the env var to exist at import time (unlikely — `ChatBedrockConverse`'s credential resolution is deferred to first invoke — but check the installed version's behavior during Task 2.3 signature inspection).

### Production runtime is NOT flipped

The overarching constraint of this story (AC #5): code lands, tests pass, smoke test validates, but **no deployed environment** — local dev, dev stack, staging, prod — has `LLM_PROVIDER=bedrock` after this story's PR merges. The flip is gated by:

1. **ADR-0003** — currently `Status: Proposed`. When DPO + Legal sign off C1/C2/C3, the ADR flips to `Accepted` and cross-region inference for Claude `eu.*` profiles is legally cleared.
2. **Story 9.7** — ECS task role needs `bedrock:InvokeModel`, `bedrock:ApplyGuardrail`, `bedrock-agentcore:*` scoped to the `eu.*` ARNs and `eu-central-1` region. Without this, a flipped `LLM_PROVIDER=bedrock` on a Celery worker raises `AccessDenied` at first invoke.

Both gates are **out of scope for 9.5b**. The decision doc's Status note (Task 6.3) records this explicitly so a future operator reading the decision doc does not assume Bedrock is live.

### Tests must be deterministic and offline (same rule as 9.5a)

The extended `test_llm_factory.py` must not:
- Call real Bedrock / Anthropic / OpenAI endpoints.
- Construct a real `ChatBedrockConverse.invoke(...)` request.
- Read real `AWS_*` env vars (monkeypatch to `"test-fake"` or unset).
- Depend on Redis (mock `check_circuit` directly).

This matches the rule established in [9-5a-llm-py-provider-routing-refactor.md](./9-5a-llm-py-provider-routing-refactor.md) Dev Notes. The smoke test (Task 3) is explicitly NOT in this test module — it's a one-off invocation whose evidence is committed as JSON under `docs/decisions/`, not as a pytest fixture.

### ARN version suffix caveat (TD-084 resolution path)

TD-084 [LOW] in [docs/tech-debt.md](../../docs/tech-debt.md) flagged that `chat_default.bedrock` in `models.yaml` is `arn:aws:bedrock:eu-central-1:573562677570:inference-profile/eu.anthropic.claude-sonnet-4-6` — no `-v*:0` suffix, unlike `agent_default.bedrock` which is `...eu.anthropic.claude-haiku-4-5-20251001-v1:0`. Story 9.5a deferred the fix because no Bedrock client was wired. Task 3.2 in THIS story is the first real chance to validate that ARN shape against the live Bedrock API. If the bare form (no `-v*:0`) invokes cleanly, TD-084 can be closed as "not a bug — both formats are accepted by Bedrock inference-profile invocation"; if the `-v*:0` form is required, fix the ARN in `models.yaml` verbatim and mark TD-084 `RESOLVED`. Either way, update the register per AC #10 candidate (c).

### Integration points

- `llm.py` seam opened by 9.5a: [backend/app/agents/llm.py:67-68](../../backend/app/agents/llm.py#L67-L68) and [llm.py:80-83](../../backend/app/agents/llm.py#L80-L83) — both `NotImplementedError` raises replaced.
- `models.yaml` consumed by the factory: [backend/app/agents/models.yaml](../../backend/app/agents/models.yaml) — extended with one new `agent_fallback:` role.
- Pyproject dependency manifest: [backend/pyproject.toml](../../backend/pyproject.toml) — one new dependency (`langchain-aws>=0.2.0`).
- Circuit breaker (not modified): [backend/app/agents/circuit_breaker.py](../../backend/app/agents/circuit_breaker.py) — `"bedrock"` is just another provider key to the existing string-parameterized interface.
- Test module extended: [backend/tests/agents/test_llm_factory.py](../../backend/tests/agents/test_llm_factory.py) — 8 → 11 functions.
- Consumers (NOT edited): [categorization/node.py](../../backend/app/agents/categorization/node.py), [education/node.py](../../backend/app/agents/education/node.py), [schema_detection.py](../../backend/app/services/schema_detection.py), [rag/candidates/runner.py](../../backend/tests/eval/rag/candidates/runner.py), [rag/judge.py](../../backend/tests/eval/rag/judge.py).
- Sibling predecessors: [Story 9.4](./9-4-agentcore-bedrock-region-availability-spike.md) (pinned the Bedrock ARNs in `models.yaml`), [Story 9.5a](./9-5a-llm-py-provider-routing-refactor.md) (built the factory seam).
- Downstream dependents: Story 9.5c (cross-provider regression matrix), Story 10.4a (AgentCore session handler).
- Gating artifacts (NOT flipped by this story): [docs/adr/0003-cross-region-inference-data-residency.md](../../docs/adr/0003-cross-region-inference-data-residency.md), Story 9.7 (backlog).

### Memory / policy references

- `project_bedrock_migration.md` — Bedrock LLM migration is deferred; this story wires the code path but does NOT flip runtime traffic to Bedrock. Production default stays `LLM_PROVIDER=anthropic`. The `llm.py` abstraction from 9.5a remains the safe swap surface.
- `project_agentcore_decision.md` — Epic 3 batch agents do NOT use AgentCore; this story preserves their Anthropic-direct + OpenAI-fallback topology byte-for-byte under the default provider setting.
- `feedback_python_venv.md` — all Python / uv commands run from `backend/` with `backend/.venv` active.
- `reference_tech_debt.md` — TD-085+ for any shortcut taken; TD-083 update + TD-084 resolution per AC #10. Highest existing TD is TD-084.
- `project_observability_substrate.md` — no CloudWatch emission added by this story; provider selection + smoke invocation are local config + one-off operator actions.

### Project Structure Notes

- Modified: `backend/app/agents/llm.py` (remove 2 raises, add ~8 lines wiring `ChatBedrockConverse` + `_fallback_role_for` helper).
- Modified: `backend/app/agents/models.yaml` (append new `agent_fallback:` role — ~5 lines).
- Modified: `backend/pyproject.toml` (1 line — new dependency).
- Modified: `backend/uv.lock` (auto-regenerated by `uv lock`).
- Modified: `backend/tests/agents/test_llm_factory.py` (delete 1 negative test, add 4 new tests — net ~+60 lines).
- New: `docs/decisions/bedrock-provider-smoke-2026-04.md` (short decision doc — ≤ 60 lines).
- New: `docs/decisions/bedrock-provider-smoke-2026-04/smoke-tests.json` (raw invoke-test evidence — ~40 lines).
- Modified: `_bmad-output/implementation-artifacts/sprint-status.yaml` (status flip + 1 new pointer comment above `9-5c-*`).
- Modified: `VERSION` (`1.35.0` → `1.36.0`).
- Conditional modified: `docs/tech-debt.md` (update TD-083 + TD-084 + possible TD-085 per AC #10).

No Terraform, no CI workflow changes, no frontend changes, no Alembic migration, no Redis schema change, no new settings fields.

### Testing Standards

- New tests live in the existing [backend/tests/agents/test_llm_factory.py](../../backend/tests/agents/test_llm_factory.py) — this story extends the 9.5a module rather than creating a new one, so that `grep get_llm_client tests/` stays a single-file hit.
- Test naming: continue the `test_<scenario>_<expected>` convention from 9.5a.
- Use `pytest.fixture` + `monkeypatch` for env + settings + `langchain_aws.ChatBedrockConverse` patching; `tmp_path` + `LLM_MODELS_CONFIG_PATH` for fixture YAML injection (AC #7 test 2).
- Default sweep target: `cd backend && uv run pytest tests/ -q` → `872 passed, 11 deselected` (Task 7.2).
- Ruff target: `uv run ruff check backend/app/agents/llm.py backend/tests/agents/test_llm_factory.py` → zero findings.

### References

- Epic 9 overview: [epics.md#Epic 9](../../_bmad-output/planning-artifacts/epics.md) lines 2021–2078
- Story 9.5b epic entry: [epics.md lines 2058–2059](../../_bmad-output/planning-artifacts/epics.md)
- Story 9.4 (Bedrock ARN pins source + smoke pattern): [9-4-agentcore-bedrock-region-availability-spike.md](./9-4-agentcore-bedrock-region-availability-spike.md)
- Story 9.5a (factory seam this story completes): [9-5a-llm-py-provider-routing-refactor.md](./9-5a-llm-py-provider-routing-refactor.md)
- ADR-0003 (blocks production runtime flip): [docs/adr/0003-cross-region-inference-data-residency.md](../../docs/adr/0003-cross-region-inference-data-residency.md)
- Current `llm.py`: [backend/app/agents/llm.py](../../backend/app/agents/llm.py)
- Current `models.yaml`: [backend/app/agents/models.yaml](../../backend/app/agents/models.yaml)
- Pyproject: [backend/pyproject.toml](../../backend/pyproject.toml)
- Existing factory tests: [backend/tests/agents/test_llm_factory.py](../../backend/tests/agents/test_llm_factory.py)
- Circuit breaker (unchanged): [backend/app/agents/circuit_breaker.py](../../backend/app/agents/circuit_breaker.py)
- Callsite files (NOT to be modified):
  - [backend/app/agents/categorization/node.py:24](../../backend/app/agents/categorization/node.py#L24)
  - [backend/app/agents/education/node.py:13](../../backend/app/agents/education/node.py#L13)
  - [backend/app/services/schema_detection.py:38](../../backend/app/services/schema_detection.py#L38)
  - [backend/tests/eval/rag/candidates/runner.py:417](../../backend/tests/eval/rag/candidates/runner.py#L417)
  - [backend/tests/eval/rag/judge.py:15](../../backend/tests/eval/rag/judge.py#L15)
- Tech-debt register: [docs/tech-debt.md](../../docs/tech-debt.md) — TD-083, TD-084 touched by AC #10.
- Sibling smoke pattern: [docs/decisions/agentcore-bedrock-region-availability-2026-04.md](../../docs/decisions/agentcore-bedrock-region-availability-2026-04.md) + [its invoke-tests.json](../../docs/decisions/agentcore-bedrock-region-availability-2026-04/invoke-tests.json)

## Dev Agent Record

### Agent Model Used

Claude Opus 4.7 (1M context) — `claude-opus-4-7[1m]`

### Debug Log References

- Baseline test sweep (pre-implementation): `869 passed, 11 deselected` — matches Story 9.5a close-out.
- Post-implementation test sweep: `872 passed, 11 deselected` — matches AC #8 target (Δ +3 in `test_llm_factory.py`).
- `uv lock` / `uv sync` side-effects: `langchain-core` resolved from `1.2.23 → 1.3.0` by the resolver when adding `langchain-aws>=0.2.0` (installed: `1.4.5`). No `langchain-*` pin changed in `pyproject.toml`; this is a lockfile-only drift driven by transitive-dep resolution. No test regressions surfaced.
- Installed `langchain-aws` (1.4.5) canonical field is `model_id`, but the constructor accepts `model=` as a pydantic alias (validated via `ChatBedrockConverse.model_fields['model_id'].alias == 'model'`). Code uses `model=` per story spec; captured instance attribute is `model_id`.
- Sonnet bare ARN (`eu.anthropic.claude-sonnet-4-6`, no `-v*:0` suffix) invoked successfully (HTTP 200) — resolved TD-084 as not-a-bug (moved to `## Resolved` in `docs/tech-debt.md`).
- Fallback inventory: both `eu.amazon.nova-micro-v1:0` and `eu.amazon.nova-lite-v1:0` returned by `aws bedrock list-inference-profiles --region eu-central-1`. Nova Micro chosen (cheapest tier, cross-family diversification, EU-scoped).
- Ruff: AC #9 command includes `models.yaml` — ruff 0.15.7 does attempt to parse it and emits syntax errors (story's "ruff ignores non-Python files" assumption is wrong). Running on the two Python files (`app/agents/llm.py`, `tests/agents/test_llm_factory.py`) returns `All checks passed!`, which is the actual AC intent. Noted as a minor story-spec inaccuracy (not a code issue).

### Completion Notes List

- `NotImplementedError` raises at `llm.py:67-68` and `llm.py:80-83` removed. `_build_client("bedrock", …)` now lazily imports `langchain_aws.ChatBedrockConverse` and constructs with `model=<arn>, region_name="eu-central-1", provider="anthropic"`.
- `_get_client_for` simplified to uniform sequence (`check_circuit → _validate_api_key → _resolve_model_id → _build_client`) across all three providers. `_validate_api_key("bedrock")` is a no-op (boto3 credentials chain).
- `_get_client_for` now accepts an optional `role` parameter (defaulting to `_PRIMARY_ROLE` = `"agent_default"`); `get_fallback_llm_client()` passes the resolved fallback role explicitly.
- New `_FALLBACK_ROLE_MAP` + `_fallback_role_for(primary)` helper encodes the bedrock → `agent_fallback` routing; anthropic/openai primaries still resolve `agent_default` for opposite-of-primary fallback (bit-for-bit preserved — locked by `test_non_bedrock_primary_fallback_topology_unchanged`).
- `models.yaml` appended with `agent_fallback:` role; `bedrock:` entry is `eu.amazon.nova-micro-v1:0` (chosen via smoke test); `anthropic:` / `openai:` sub-keys mirror `agent_default` for schema symmetry (non-bedrock primaries never consult this role).
- Test module: replaced `test_bedrock_primary_raises_not_implemented` with `test_bedrock_primary_returns_chat_bedrock_client`; added `test_bedrock_fallback_resolves_agent_fallback_role` (uses `tmp_path` fixture yaml to decouple from operational ARN), `test_bedrock_circuit_open_blocks_construction`, `test_non_bedrock_primary_fallback_topology_unchanged`. Sentinel `_BedrockSentinel` patched at `langchain_aws.ChatBedrockConverse` (not `llm_module`) to match the lazy-import pattern.
- Smoke evidence in `docs/decisions/bedrock-provider-smoke-2026-04.md` + `smoke-tests.json`. All three invocations returned HTTP 200 / `"OK"` response.
- TD-083 updated in place (second hardcoded rule noted). TD-084 moved to `## Resolved` (not-a-bug). TD-085 added (Nova Micro tier gamble).
- Five 9.5a-AC-#3 callsite files verified unchanged (`git diff --stat` empty).
- VERSION bumped `1.35.0 → 1.36.0` (MINOR — new user-facing capability: `LLM_PROVIDER=bedrock` now produces a real client).

### File List

- Modified: `backend/app/agents/llm.py`
- Modified: `backend/app/agents/models.yaml`
- Modified: `backend/pyproject.toml`
- Modified: `backend/uv.lock`
- Modified: `backend/tests/agents/test_llm_factory.py`
- New: `docs/decisions/bedrock-provider-smoke-2026-04.md`
- New: `docs/decisions/bedrock-provider-smoke-2026-04/smoke-tests.json`
- Modified: `docs/tech-debt.md` (TD-083 update + TD-085 new + TD-084 moved to Resolved)
- Modified: `_bmad-output/implementation-artifacts/sprint-status.yaml` (9-5b status flipped to `review`)
- Modified: `VERSION` (`1.35.0` → `1.36.0`)

### Change Log

- 2026-04-23: Story 9.5b implemented. Bedrock provider path wired via `langchain_aws.ChatBedrockConverse`; `agent_fallback` role added; smoke-tested Haiku 4.5, Sonnet 4.6, Nova Micro in `eu-central-1`; test suite 869 → 872 passed; TD-084 resolved; TD-085 added. Version bumped `1.35.0 → 1.36.0` per story completion.
- 2026-04-23: Code review (adversarial) — fixed M1 (`provider` kwarg now derived from ARN prefix via new `_parse_bedrock_arn` helper, so Nova fallback sends `provider="amazon"`, not the wrong `"anthropic"` hint), M2 (`region_name` parsed from ARN instead of hardcoded `"eu-central-1"`), L1 (`test_bedrock_circuit_open_blocks_construction` now raises only for `provider=="bedrock"` per AC #7 wording), L2 (added `provider` + `region_name` sentinel-kwarg assertions in `test_bedrock_fallback_resolves_agent_fallback_role`, which now uses realistic ARN-shape fixtures), L3 (dropped redundant `!=` assertion), L4 (scrubbed user alias from decision-doc re-run instructions). L5 (smoke-evidence envelope mismatch with LangChain code path) auto-resolved by M1's fix. Full sweep still `872 passed, 11 deselected`; ruff clean.

### Senior Developer Review (AI) — 2026-04-23

**Reviewer:** AI adversarial pass (Opus 4.7)
**Outcome:** Approved with fixes applied.

**Changes landed in this review pass:**

- [llm.py:65-81](../../backend/app/agents/llm.py#L65-L81) — added `_parse_bedrock_arn(model_id) -> (region, family)` helper; `_build_client("bedrock", …)` now calls `ChatBedrockConverse(model=model_id, region_name=<parsed-region>, provider=<parsed-family>)`. Nova Micro fallback now correctly sends `provider="amazon"` (was: wrong `"anthropic"` hint).
- [test_llm_factory.py:96-128](../../backend/tests/agents/test_llm_factory.py#L96-L128) — fallback test fixtures rewritten to realistic Bedrock ARNs; added `assert fallback.provider == "amazon"` + `assert fallback.region_name == "eu-central-1"`; circuit-breaker-open test narrowed to raise only for `provider=="bedrock"`; redundant `!=` assertion removed.
- [bedrock-provider-smoke-2026-04.md:31](../../docs/decisions/bedrock-provider-smoke-2026-04.md#L31) — removed personal AWS profile alias from re-run instructions.

**Deferred (explicitly not promoted to tech-debt):** none. All findings addressed.
