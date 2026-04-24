# Story 9.8: Pipeline Orchestration Evaluation (Optional, Time-Boxed Spike)

Status: ready-for-dev
Created: 2026-04-23
Epic: 9 — AI Infra Readiness (Bedrock Provider, RAG Eval Harness, Embedding Decision)

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **tech lead closing Epic 9 and deciding whether to carry the current Celery+Redis orchestration architecture forward into Epic 10+ unchanged**,
I want **a time-boxed (≤ 1 dev-day) evaluation spike that compares the current Celery + Redis broker + ElastiCache + ECS-Fargate-worker pipeline** (as it actually runs today: `FastAPI → apply_async() → Celery worker on ECS → LangGraph StateGraph with 4 nodes (categorization → pattern_detection → triage → education) from [backend/app/agents/pipeline.py](../../backend/app/agents/pipeline.py) with a PostgresSaver checkpointer from [backend/app/agents/checkpointer.py](../../backend/app/agents/checkpointer.py), published over SSE via Redis pub/sub) **against two AWS-native orchestrators — AWS Step Functions and AWS Batch** — scored on six criteria (fit-for-LangGraph, migration effort, steady-state cost, reliability/retry semantics, observability, operational complexity) that are pre-registered in this story so the evaluator cannot rationalise toward a preferred outcome, resulting in **a single committed decision doc at `docs/decisions/pipeline-orchestration-evaluation-2026-04.md`** whose final line is exactly one of three forms (stay / migrate-to-Step-Functions / migrate-to-Batch) with the default being **stay on Celery** — matching epic wording at [epics.md:2070-2071](../../_bmad-output/planning-artifacts/epics.md#L2070-L2071) (*"Output: recommendation doc only — actual migration requires separate approval. Default outcome: stay on Celery"*) and the architecture escape-hatch language at [architecture.md:1651-1653](../../_bmad-output/planning-artifacts/architecture.md#L1651-L1653),

so that **(1)** Epic 9 can close cleanly (9.8 is the last story; [sprint-status.yaml:209-210](../../_bmad-output/implementation-artifacts/sprint-status.yaml#L209-L210) gates `epic-9-retrospective: optional` on 9.8 landing) without leaving an unmeasured "maybe Step Functions?" footnote hanging over Epic 10's kick-off, **(2)** the next time someone on the team (or a future contractor) asks *"why didn't we use Step Functions for the pipeline — we're on AWS anyway"* the answer lives in `git log`, not in a lost Slack thread — same rationale the Story 9.3 and 9.4 decision docs established as Epic-9 convention, **(3)** if the spike *does* flip to "migrate to X", the doc produces a scoped, approved-or-not fork that the PM agent can turn into a dedicated epic (with its own scope-lock, its own stories, its own tfvars and its own dependency graph) rather than having this story silently metastasize into a rewrite of the ingestion pipeline, **(4)** the evaluation does NOT commit any backend, frontend, Terraform, `models.yaml`, `tech-debt.md` (beyond optional deferred-item entries per AC #8), or `sprint-status.yaml` change outside the explicit 9.8 status flip — this is a **pure research story**: the diff is one new markdown file plus the status line flip — and **(5)** the time-box is real and enforced at AC #1: the spike carries a hard cap at 1 dev-day (8 hours of focused work, measured wall-clock not counting context switches) — at the cap, the evaluator stops, writes up whatever criteria are complete, and marks uncompleted criteria as "Evidence: insufficient within time-box → defaults to Celery per AC #1 tiebreaker rule", preserving the `optional` framing from the epic title (*"Pipeline Orchestration Evaluation (Optional, Time-Boxed Spike)"*).

## Acceptance Criteria

1. **Given** the epic titles this story *"Pipeline Orchestration Evaluation (**Optional, Time-Boxed Spike**)"* ([epics.md:2070](../../_bmad-output/planning-artifacts/epics.md#L2070)) and the architecture says *"Default: stay on Celery"* ([architecture.md:1653](../../_bmad-output/planning-artifacts/architecture.md#L1653)), **When** this spike concludes, **Then** a decision doc lands at exactly **`docs/decisions/pipeline-orchestration-evaluation-2026-04.md`** (new file — co-located with the other 9.x decision docs `embedding-model-comparison-2026-04.md`, `agentcore-bedrock-region-availability-2026-04.md`, `bedrock-provider-smoke-2026-04.md`) whose **final line** is **exactly one of three forms** (no hedging, no fourth variant, no "inconclusive"):

   - `**Outcome: stay on Celery + Redis**` — the default; applies whenever the tie-breaker rule fires (see AC #4's scoring-table rule) OR whenever the evaluator's time-box is exhausted before a clear winner is established. This is also the epic-documented default.
   - `**Outcome: migrate to AWS Step Functions** (separate epic required)`
   - `**Outcome: migrate to AWS Batch** (separate epic required)`

   **Time-box enforcement:** the evaluator SHALL record a start-of-work timestamp in the doc's `## Methodology` section (format: `Spike started: YYYY-MM-DDTHH:MMZ; time-box: 8 working hours`) and stop work — closing the doc with `**Outcome: stay on Celery + Redis**` per the tie-breaker — the moment the cumulative wall-clock (excluding lunch, context switches to other tickets, unrelated Slack) reaches 8 hours. The doc's `## Time-Box Ledger` section (see AC #3's mandatory section list) records the actual hours spent per criterion; if a criterion is marked `Evidence: insufficient within time-box`, that is acceptable and preferred to half-baked evidence.

2. **Given** a fair comparison needs the same three orchestration alternatives described with the same shape, **When** the decision doc enumerates candidates, **Then** it uses exactly these three (no more, no less — adding a fourth expands the time-box; dropping one breaks the "two alternatives vs status quo" frame the epic requires):

   - **Candidate A (status quo): Celery 5.x + Redis (ElastiCache) broker, LangGraph StateGraph, PostgresSaver checkpointer, ECS Fargate workers.** Source of truth: [backend/app/tasks/celery_app.py](../../backend/app/tasks/celery_app.py) (broker config, `task_time_limit=120`, `task_soft_time_limit=90`), [backend/app/agents/pipeline.py](../../backend/app/agents/pipeline.py) (4-node graph), [backend/app/tasks/processing_tasks.py](../../backend/app/tasks/processing_tasks.py) (the `process_upload` Celery task — **note**: architecture.md says `pipeline_tasks.py` at [architecture.md:1339](../../_bmad-output/planning-artifacts/architecture.md#L1339) but actual filename is `processing_tasks.py`; see Dev Notes doc-drift entry), [infra/terraform/modules/ecs/main.tf](../../infra/terraform/modules/ecs/main.tf) (worker service), [infra/terraform/modules/elasticache/main.tf](../../infra/terraform/modules/elasticache/main.tf) (broker).
   - **Candidate B: AWS Step Functions Standard Workflow** orchestrating ECS `RunTask` (or Lambda) invocations, one state per LangGraph node. LangGraph's Python library still runs *inside* each task; Step Functions replaces Celery as the outer scheduler + checkpoint authority. Rationale for Standard over Express: pipeline execution can exceed 5 minutes (Express cap) and idempotency + at-least-once semantics matter more than per-transition cost; record the Standard-vs-Express choice explicitly.
   - **Candidate C: AWS Batch on Fargate** running the LangGraph pipeline as a single Batch job per upload. Batch handles queueing + retry + DLQ; no per-node state machine — the LangGraph in-process graph stays intact. Rationale for Fargate over EC2 compute environment: current workers are Fargate; EC2 introduces a new compute type with no existing Terraform module, violating the "minimum migration surface" principle the evaluation scores against.

   Explicitly **out of scope** (named so a future reviewer knows they were considered and rejected, not missed): AWS MWAA/Airflow (overweight for a 4-node DAG; operational cost outweighs benefit at current throughput), EventBridge Scheduler (not an orchestrator — solves cron, not DAGs; we already use it implicitly via Celery beat which Story 7.9 resolved), self-hosted Argo/Temporal (adds a Kubernetes or Temporal-cluster dependency this architecture explicitly avoids — see [architecture.md:527](../../_bmad-output/planning-artifacts/architecture.md#L527) *"Celery workers need persistent containers for long-running AI pipeline jobs. Fargate provides this without managing servers"*), SQS-only (a broker, not an orchestrator; conflating the two was the most common anti-pattern the evaluator should resist).

3. **Given** a decision doc must be actionable for any follow-up epic *and* must make the "stay on Celery" default defensible, **When** the doc is written, **Then** it contains — **in this order, with exactly these section headings** (matches the shape established by [docs/decisions/agentcore-bedrock-region-availability-2026-04.md](../../docs/decisions/agentcore-bedrock-region-availability-2026-04.md) and [docs/decisions/embedding-model-comparison-2026-04.md](../../docs/decisions/embedding-model-comparison-2026-04.md); reviewers should be able to navigate without re-learning the layout):

   - **Context** (≤ 12 lines): why this gate exists. Cite epic wording verbatim, link [architecture.md#Pipeline-Orchestration — Celery vs Step Functions](../../_bmad-output/planning-artifacts/architecture.md#L1651), note the "Default: stay on Celery" framing, and state that this is an **optional** story Epic 9 could have closed without (so flipping to `optional: done` without running the spike is also a valid close-out path — see AC #7's alternate path).
   - **Current Architecture — One-Paragraph Baseline**: a single paragraph (≤ 150 words) describing how an upload flows today: `POST /api/v1/uploads` → `uploads.py` creates `ProcessingJob` row → `processing_tasks.process_upload.apply_async(job_id)` (via Celery) → worker picks from Redis broker → builds LangGraph graph with checkpointer → runs 4 nodes sequentially → publishes progress to Redis pub/sub → `jobs.py` SSE endpoint relays to frontend. Cite the exact file paths (per AC #2 candidate-A bullet). This baseline is what Candidates B and C are compared against.
   - **Methodology**: one paragraph stating the spike is desk research + docs + cost calculator + pricing pages — **no proof-of-concept code is written**, **no Terraform module is drafted**, **no AWS resource is provisioned** (these would bust the time-box and this story does not own any infra migration work per AC #6). Record the start-of-work timestamp + time-box cap per AC #1.
   - **Evaluation Criteria (6-Criterion Scorecard)**: a table with the six criteria from AC #4 as rows and three columns (Celery / Step Functions / Batch). Each cell is scored `+`, `=`, or `−` (**+** = candidate is clearly better than Celery status-quo on this axis; **=** = indistinguishable within the evidence the time-box allows; **−** = clearly worse). Status-quo column's diagonal is `=` by construction. A one-sentence rationale below each column's per-criterion score cites the evidence (AWS pricing page, AWS docs link, LangGraph issue tracker, an internal metric, or "insufficient evidence within time-box → `=`"). **Scoring is ordinal, not numeric** — the tie-breaker rule is "if Step Functions or Batch does not post a net ≥ +2 across the six criteria relative to Celery (after subtracting `−` scores), the outcome is `stay on Celery`". The `+2 net` bar is high on purpose: this is a migration decision that the epic says should default to staying put, and the bar must be calibrated so that a "slight edge" does not trigger a multi-week migration.
   - **Criterion-by-Criterion Findings**: six H3 subsections, one per criterion (exactly the six listed in AC #4) — each ≤ 10 lines. This is where the scoring rationale lives; the scorecard table is a summary.
   - **Decision**: one line — `**Outcome: <one of the three AC #1 forms>**`.
   - **Rationale**: 3–7 bullets. If the outcome is `stay on Celery + Redis`, the rationale explicitly cites which criteria tipped the scale toward the default — *"migrate-to-X net score was +1 on 6 criteria; tie-breaker rule per AC #4 defaults to stay"* is an acceptable bullet.
   - **Impact on downstream work**: one bullet each for (a) Epic 9 retrospective (how this story's outcome feeds the retrospective), (b) Epic 10 (chat pipeline is AgentCore-native per [architecture.md:1614-1619](../../_bmad-output/planning-artifacts/architecture.md#L1614-L1619), so this decision does NOT affect Epic 10 regardless of outcome — call that out), (c) Epic 11 (ingestion + categorization hardening runs on the same Celery pipeline evaluated here; the outcome does affect 11.x ops plans).
   - **Time-Box Ledger**: a small table logging wall-clock hours per criterion (six rows + "Write-up"). The `Total` row must not exceed 8 hours; if it does, add a note explaining which criterion was under-evidenced and why the overflow was accepted (reviewable exception, not a silent drift).
   - **Re-run instructions**: a one-paragraph "if the underlying conditions change (e.g. throughput grows ≥ 10×, pipeline node count grows ≥ 2×, LangGraph adds a native Step Functions backend) the evaluator of a future re-run should repeat this exercise using the same six criteria and the same `+2 net` tie-breaker". Record the current throughput baseline observed from prod CloudWatch (one number, e.g. "≈ N uploads / day"; if no prod data exists because prod traffic is near zero, say that).

4. **Given** the scoring must be pre-registered so the evaluator cannot rationalise toward a preferred outcome, **When** the Evaluation Criteria section is written, **Then** it uses **exactly these six criteria** (same wording as the story — do not paraphrase during implementation; wording drift is the most common way pre-registered scoring decays into post-hoc rationalisation):

   1. **Fit-for-LangGraph.** Can the orchestrator host a `langgraph.graph.StateGraph` execution without losing the LangGraph checkpointer model (state reconstruction across retries) or forcing a rewrite of the 4-node graph into orchestrator-native state primitives? Evidence to look for: LangGraph's own docs for "backend" or "deployment" options; whether the in-process `graph.invoke(state, config)` pattern from [backend/app/agents/pipeline.py](../../backend/app/agents/pipeline.py) works unchanged when the orchestrator schedules a container that runs it end-to-end (Batch: yes trivially; Step Functions: yes if one state runs the whole graph, but then why use Step Functions). If the orchestrator forces splitting LangGraph's 4 nodes into Step Functions states, the PostgresSaver checkpointer becomes redundant / doubly-authoritative, which is a significant downside to score against.
   2. **Migration effort (dev-days).** How many dev-days (rough order-of-magnitude: 1–2 / 3–5 / 6–10 / > 10) to reach feature parity with today's Celery path including retries, SSE progress publication, DLQ semantics, tests, and Terraform modules? Anchor estimates in the existing Terraform footprint ([infra/terraform/modules/ecs/main.tf](../../infra/terraform/modules/ecs/main.tf), [modules/elasticache/main.tf](../../infra/terraform/modules/elasticache/main.tf)) and the existing test surface ([backend/tests/integration/test_observability_event_coverage.py](../../backend/tests/integration/test_observability_event_coverage.py), [backend/tests/test_processing_tasks.py](../../backend/tests/test_processing_tasks.py)). Score `+` for ≤ 2 days (clear win), `=` for 3–5 days (noise), `−` for > 5 days.
   3. **Steady-state cost (USD / month at current + 10× throughput).** Evidence from AWS pricing calculator: Celery on Fargate (2 × `desired_count` per [modules/ecs/main.tf](../../infra/terraform/modules/ecs/main.tf) — current `worker` + `beat`) vs Step Functions Standard (per-state-transition pricing — [per AWS pricing page](https://aws.amazon.com/step-functions/pricing/): $0.025 per 1k transitions) vs AWS Batch on Fargate (compute cost only; Batch itself is free). The "current throughput" number comes from prod CloudWatch; if insufficient data, use an assumed baseline and name it. The 10× projection guards against picking an orchestrator that looks cheap today but scales poorly. Include the ElastiCache Redis cost in the Celery column — dropping Redis is a possible saving if a candidate removes the broker entirely (Step Functions: yes; Batch: yes).
   4. **Reliability / retry / DLQ semantics.** How each orchestrator handles task retries, dead-letter routing, and partial-success resumption. Celery baseline: `max_retries=3` + exponential backoff per [architecture.md:879](../../_bmad-output/planning-artifacts/architecture.md#L879); LangGraph PostgresSaver checkpointer rehydrates state from the last successful node per [backend/app/agents/checkpointer.py](../../backend/app/agents/checkpointer.py). Step Functions: native retry + catch + ResultPath. Batch: native retry with `attempts`, SQS DLQ. Score cares about whether the candidate's retry model **replaces** the LangGraph checkpointer (double-authority = minus) or **complements** it (single-source = plus or equals).
   5. **Observability.** Existing Celery path publishes to CloudWatch Logs (from ECS tasks) + Redis pub/sub for SSE + `processing_jobs` table for status; Epic 11 Story 11.9 adds CloudWatch Insights metric filters (per auto-memory note *"Epic 11 observability substrate is CloudWatch Insights + Terraform metric filters, not Grafana"*). Step Functions has built-in execution history + CloudWatch integration. Batch has CloudWatch + EventBridge lifecycle events. Score considers whether the candidate adds useful visibility **beyond** what 11.9 already provides (low ceiling — 11.9 is designed specifically for this pipeline) or replaces an internal plumbing with a managed equivalent (neutral — no net win).
   6. **Operational complexity.** On-call runbook weight, Terraform module count, new IAM surface, failure modes a human operator has to learn. Celery baseline: the existing [docs/operator-runbook.md](../../docs/operator-runbook.md) plus the known beat/worker split (TD-026 resolved). Step Functions: new state-machine JSON, new IAM roles per state, new alarm surface. Batch: new compute environment, job queue, job definition, new IAM execution/job roles. Score cares about *absolute* new surface, not just per-candidate — migrating *anywhere* is more complex than staying, so Celery's score on this axis is `=` by construction (diagonal).

5. **Given** the spike produces a **recommendation**, not an implementation, **When** the decision doc reaches its `Decision` section, **Then** the doc explicitly names and rejects the "silent migration" path — a single boldface line in the Rationale section must read: *"This story's outcome is a recommendation. Any migration requires a new epic proposal vetted by the PM agent (correct-course workflow), a scope-lock, its own stories with AC-level acceptance, and a separate sprint-planning run — see the epic's explicit phrasing at [epics.md:2071](../../_bmad-output/planning-artifacts/epics.md#L2071)."* The intent is to close off the common failure mode where a spike quietly grows into a partial migration in a follow-up PR. This line is mandatory regardless of outcome (yes, even if the outcome is `stay on Celery`, because a future re-run of the spike might flip, and preserving the "new epic" guardrail for that future flip is the point).

6. **Given** this is a research-only spike, **When** the dev executes the work, **Then** the **only** file changes permitted in the implementing PR are:

   - **Added:** `docs/decisions/pipeline-orchestration-evaluation-2026-04.md` (this story's deliverable).
   - **Modified:** `_bmad-output/implementation-artifacts/9-8-pipeline-orchestration-evaluation-spike.md` (this file — Task checkboxes, Dev Agent Record sections, File List).
   - **Modified:** `_bmad-output/implementation-artifacts/sprint-status.yaml` (AC #7's status flip — one line).
   - **Optionally modified:** `docs/tech-debt.md` (new TD entry only if AC #8 fires).

   **Explicitly forbidden in this story's diff** (each of these would expand scope into a separate story's territory — and each has a specific reason it is forbidden here): no edits under `backend/` (migration prep is Epic 11's or a follow-up epic's concern, not this evaluation's), no edits under `infra/terraform/` (drafting a Step Functions / Batch Terraform module is a spike-by-itself, not a sub-task of the evaluation — and it would cause the kind of "silent migration" AC #5 explicitly forbids), no edits under `frontend/` (SSE contract is unchanged regardless of outcome), no edits to [backend/app/agents/models.yaml](../../backend/app/agents/models.yaml) or [architecture.md](../../_bmad-output/planning-artifacts/architecture.md) (architecture updates from a *decided and approved* migration happen in the follow-up epic; this story's outcome, if it flips, is a recommendation — architecture stays describing current reality until migration completes), no edits to [.github/workflows/](../../.github/workflows/) (no CI changes from a research doc). If the evaluator feels the urge to prototype, that urge is the signal to stop and write the doc: prototyping is post-approval work.

7. **Given** [_bmad-output/implementation-artifacts/sprint-status.yaml](../../_bmad-output/implementation-artifacts/sprint-status.yaml) tracks story state and Epic 9 close-out depends on this being the last Epic 9 story, **When** this story is ready for dev, **Then** line 209's `9-8-pipeline-orchestration-evaluation-spike:` key is flipped `backlog` → `ready-for-dev` by the create-story workflow (this file), and on close-out the implementing dev flips it `in-progress` → `review` (code-review flips to `done` per the normal flow). **Additional close-out actions when `done`:**

   - **Epic close-out:** once `9-8-*: done`, the implementing dev (or the reviewer at `done` time) flips `epic-9: in-progress` → `done` at [sprint-status.yaml:184](../../_bmad-output/implementation-artifacts/sprint-status.yaml#L184). This is the only remaining backlog story in Epic 9 per [sprint-status.yaml:184-210](../../_bmad-output/implementation-artifacts/sprint-status.yaml#L184-L210) so the epic close-out is unambiguous. The `epic-9-retrospective: optional` line at [sprint-status.yaml:210](../../_bmad-output/implementation-artifacts/sprint-status.yaml#L210) remains `optional` — retrospective execution is a separate decision.
   - **Alternate close-out path (skip-without-running):** because the epic explicitly marks this story *optional*, a valid alternate close-out is for the PM agent (or a team decision) to flip `9-8-*: backlog` directly to `skipped` (or `done` with a one-line close note *"Skipped — 9.8 is optional per epic; team accepted default of staying on Celery without running the spike"*) without creating the decision doc. If that path is chosen, the status flip happens without a PR — a commit message in `_bmad-output/` is sufficient. The story-author would then NOT create the decision doc. The AC #1 / AC #3 / AC #4 requirements do not fire in that path. The dev-story workflow should offer this path explicitly at start: *"Run the spike, or skip it as optional?"* — see Dev Notes for the recommended decision tree.
   - The 11-line comment block above `9-6-*` at [sprint-status.yaml:196-206](../../_bmad-output/implementation-artifacts/sprint-status.yaml#L196-L206) is **preserved verbatim** (it belongs to 9.6 + 9.3 decision narrative, not 9.8). The Epic-10 block at [sprint-status.yaml:212-](../../_bmad-output/implementation-artifacts/sprint-status.yaml#L212) is **not touched** (Epic 10 does not consume this decision regardless of outcome — chat is AgentCore-native per AC #3's Impact bullet).

8. **Given** [docs/tech-debt.md](../../docs/tech-debt.md) tracks deferred work with `TD-NNN` IDs and the highest existing entry is **TD-091** (per Story 9.7 code-review — *"Terraform state backend is dev-authoritative..."*), **When** this spike finishes, **Then**:

   - **If the outcome is `stay on Celery + Redis`:** no new TD entry is mandatory. The spike found no deferred work; the register is not padded. **Optional** TD entries if the evaluator surfaces a concrete follow-up worth tracking:
     - **TD-092 (conditional, LOW)** — *"Re-run Story 9.8 pipeline-orchestration evaluation when throughput grows ≥ 10× OR pipeline adds ≥ 2 new nodes OR LangGraph ships a native Step Functions backend."* Fix shape: re-open 9.8's methodology with updated evidence; use the same scorecard. Only add this if the evaluator judges the re-run trigger is non-obvious to a future reader.
   - **If the outcome is `migrate to Step Functions` or `migrate to Batch`:** no new TD entry either — a migration outcome triggers a **new epic proposal**, not a TD entry (TD entries are for small deferred items; a multi-week migration is epic-shaped). The decision doc's `Impact on downstream work` section names the new-epic requirement per AC #5.
   - **If the evaluator exceeded the time-box** (AC #1's 8-hour cap) and accepted the overflow: add a **TD-092 (MEDIUM)** — *"Story 9.8 pipeline-orchestration evaluation exceeded its 1-dev-day time-box by N hours; evaluate whether the scorecard methodology needs more criteria or whether the time-box was mis-calibrated."* Only if overflow actually happens.
   - **TD-091 is untouched.** Terraform state backend hygiene is a 9.7-follow-up concern orthogonal to orchestration choice. TD-086, TD-041, etc. are also untouched — this is a research story with no IAM / CI / payments touch.

9. **Given** [backend/AGENTS.md](../../backend/AGENTS.md) de-facto gates merges on `cd backend && uv run ruff check .` + pytest passing, **When** this story ships, **Then** the standard backend gates are **unchanged** (no new test failures, no new ruff findings — because no backend file is edited per AC #6). Similarly the infra gates are unchanged (no `.tf` edit per AC #6). The only gate specific to this story is:

   - **Markdown lint** (if the project runs `markdownlint` in CI — check [.github/workflows/](../../.github/workflows/) at implementation time; if not run in CI, the evaluator verifies the decision doc renders correctly on GitHub preview before marking the story `review`).
   - **Link-check**: every cross-reference in the decision doc (file paths, line numbers, AWS pricing URLs) resolves at commit time. Use `grep -n` or the IDE's link resolver; AWS pricing URLs are verified as HTTP-200 (not 404) once and the verification is noted in Debug Log References. Dead AWS pricing links are a common failure mode that degrades the doc's future utility.
   - **Baseline test sweep drift check**: run `cd backend && uv run pytest tests/ -q` once at the start of the story, record the baseline pass/deselect count in Debug Log References; at close-out the count must match (this is a drift check against `main`, not a positive test signal — no test was added or removed). Story 9.7's close landed `873 passed, 23 deselected` (per its Completion Notes). Confirm the current count at spike start and match it at spike end; if `main` has drifted between start and end, record the new baseline in the decision doc's `Re-run instructions` section.

10. **Given** this story is explicitly optional and time-boxed, **When** the dev-story workflow begins work on it, **Then** the implementing dev is expected to read this AC block **before** writing the doc and make an explicit up-front call between three paths — **the call itself is a deliverable** (one-sentence close-out note in the story's Completion Notes, regardless of path chosen):

   - **Path A — run the spike (produce the decision doc):** proceed through Tasks 1–5 below. Typical choice if the team has bandwidth and wants the decision on the record.
   - **Path B — skip as optional (no decision doc):** close the story per AC #7's alternate close-out. Typical choice if team bandwidth is tight and the default ("stay on Celery") is already the operating assumption. The Completion Notes line must read: *"Skipped — 9.8 is optional per epic wording. Team accepts default of staying on Celery without running the spike; a future re-run may revisit if throughput or pipeline shape changes materially (see AC #8's TD-092 trigger conditions)."*
   - **Path C — partial spike (evidence for ≤ 3 of the 6 criteria, time-box hit early):** produce a decision doc per AC #3 but mark the un-evidenced criteria `Evidence: insufficient within time-box → defaults to Celery per AC #4 tiebreaker`. This is an acceptable middle ground; the `+2 net` rule naturally pushes toward the default when evidence is sparse.

## Tasks / Subtasks

- [ ] Task 1: Up-front path decision + baseline capture (AC: #7, #9, #10)
  - [ ] 1.1 Read AC #10. Make the explicit A/B/C call. Record the call in a scratch note — it becomes the first line of Completion Notes at close-out.
  - [ ] 1.2 If Path A or C: record start-of-work timestamp `YYYY-MM-DDTHH:MMZ` — this becomes the `Spike started:` line in the decision doc's Methodology section per AC #1.
  - [ ] 1.3 Baseline test sweep: `cd backend && uv run pytest tests/ -q`; record `<N> passed, <M> deselected` in Debug Log References.
  - [ ] 1.4 Confirm `docs/decisions/` exists (it does — Story 9.3 and 9.4 created decision docs there). No `index.md` needed — the directory is self-describing.
  - [ ] 1.5 Confirm highest existing TD ID in [docs/tech-debt.md](../../docs/tech-debt.md) (expected: TD-091 per Story 9.7 close-out). The conditional TD-092 from AC #8 will use the next ID.
  - [ ] 1.6 If Path B: skip directly to Task 5 (close-out). AC #1 / AC #3 / AC #4 do not fire on Path B.

- [ ] Task 2: Candidate baseline — characterise the current Celery pipeline (AC: #2, #3)
  - [ ] 2.1 Read [backend/app/tasks/celery_app.py](../../backend/app/tasks/celery_app.py), [backend/app/tasks/processing_tasks.py](../../backend/app/tasks/processing_tasks.py), [backend/app/agents/pipeline.py](../../backend/app/agents/pipeline.py), [backend/app/agents/checkpointer.py](../../backend/app/agents/checkpointer.py). Extract: broker config, task time limits, retry policy, checkpointer backing, per-node execution model. These populate the `Current Architecture — One-Paragraph Baseline` section per AC #3.
  - [ ] 2.2 Note the doc-drift between [architecture.md:1339](../../_bmad-output/planning-artifacts/architecture.md#L1339) (`pipeline_tasks.py`) and actual filename `processing_tasks.py`. Call this out in the doc's Dev Notes; optional TD if it becomes a recurring confusion (likely not — one-line note is enough).
  - [ ] 2.3 Pull the current Terraform ECS + ElastiCache footprint for the Migration-effort criterion (AC #4, criterion 2). Surface the `desired_count` for `worker` + `beat` (per [modules/ecs/main.tf:89](../../infra/terraform/modules/ecs/main.tf#L89) / [L176](../../infra/terraform/modules/ecs/main.tf#L176)) — this is the "what would we be replacing" count.
  - [ ] 2.4 Capture a rough current-throughput number from prod CloudWatch if available (one number — e.g. "≈ 3 uploads / day in prod week of 2026-04-XX"); if prod traffic is near zero, say that explicitly. Goes into the Steady-state-cost criterion (AC #4, criterion 3) and the Re-run-instructions section (AC #3).

- [ ] Task 3: Candidate research — Step Functions + Batch (AC: #2, #4)
  - [ ] 3.1 **Step Functions**: read AWS docs on Standard vs Express Workflows (focus: at-least-once semantics, max duration, per-transition pricing at [https://aws.amazon.com/step-functions/pricing/](https://aws.amazon.com/step-functions/pricing/)). Determine whether to host each LangGraph node as a state (splits the graph; duplicates checkpointer authority) or run the whole graph inside a single ECS `RunTask` state (Step Functions becomes a fancy retry wrapper). Score criterion 1 (Fit-for-LangGraph) and criterion 2 (Migration effort).
  - [ ] 3.2 **AWS Batch on Fargate**: read AWS docs on Batch compute environments, job queues, job definitions. Confirm Batch on Fargate is ≥ 2023-GA (it is). Establish whether Batch replaces Celery end-to-end (yes — Batch takes over queueing + retry + DLQ + scheduling; LangGraph runs inside a job).
  - [ ] 3.3 For criterion 3 (Steady-state cost): use AWS pricing calculator or pricing-page calculations. Include ElastiCache Redis removal as a credit in Step Functions + Batch columns (if the broker goes away).
  - [ ] 3.4 For criterion 4 (Reliability): note which candidate's retry model **replaces** the LangGraph PostgresSaver checkpointer (creates a double-authority hazard — minus) vs **complements** it (candidate retries at orchestrator level, LangGraph retries at node level, disjoint domains — plus or equals).
  - [ ] 3.5 For criterion 5 (Observability): cross-reference the Epic 11 Story 11.9 observability plan in the epic — does the candidate add visibility beyond what 11.9 provides? Typically low ceiling.
  - [ ] 3.6 For criterion 6 (Operational complexity): count new Terraform resources each candidate would need (IAM roles, state-machine definitions, job queues, compute envs). The counting is the score — more resources → more `−`.
  - [ ] 3.7 Respect the time-box. If any criterion hits a dead end within 1 hour, mark `Evidence: insufficient within time-box → =` and move on. Do NOT prototype.

- [ ] Task 4: Write the decision doc (AC: #1, #3, #4, #5)
  - [ ] 4.1 Create [`docs/decisions/pipeline-orchestration-evaluation-2026-04.md`](../../docs/decisions/pipeline-orchestration-evaluation-2026-04.md) with the exact section headings from AC #3 in the stated order.
  - [ ] 4.2 Fill in the 6-criterion scorecard table — ordinal `+` / `=` / `−` per AC #4. Net-score the two migration columns; apply the `+2 net` tie-breaker rule.
  - [ ] 4.3 Write the six H3 Criterion-by-Criterion subsections — each ≤ 10 lines, each citing its evidence.
  - [ ] 4.4 Write the Decision line exactly as one of AC #1's three forms. The default is `**Outcome: stay on Celery + Redis**`.
  - [ ] 4.5 Add the mandatory AC #5 migration-guardrail line to the Rationale section verbatim (boldface, no paraphrase).
  - [ ] 4.6 Fill in the Time-Box Ledger. Total ≤ 8 hours; note any overflow per AC #8's TD-092 rule.
  - [ ] 4.7 Link-check every URL + file-path citation per AC #9. Fix any dead links.

- [ ] Task 5: Close-out (AC: #6, #7, #8, #9)
  - [ ] 5.1 Verify the PR diff matches AC #6's allowed-files list. If anything else changed, move it to a separate PR.
  - [ ] 5.2 `cd backend && uv run pytest tests/ -q` — confirm the count matches Task 1.3's baseline. Record in Completion Notes.
  - [ ] 5.3 Update [sprint-status.yaml:209](../../_bmad-output/implementation-artifacts/sprint-status.yaml#L209): `9-8-*: ready-for-dev` → `in-progress` → `review` per the normal flow. (The create-story workflow flips `backlog` → `ready-for-dev`; the implementing dev handles the rest.)
  - [ ] 5.4 If the outcome is `stay on Celery`: no epic-10 / epic-11 impact bullets need updates. If the outcome is a migrate variant: the decision doc's `Impact on downstream work` section names the new epic; do NOT create that epic here — that is a PM-agent correct-course action.
  - [ ] 5.5 Optional: add TD-092 per AC #8 if its trigger fires (time-box overflow OR the re-run-trigger note is non-obvious). Default: no TD entry.
  - [ ] 5.6 Populate File List (expected shape: 1 added + 2–3 modified per AC #6).
  - [ ] 5.7 At `done`-time, flip [sprint-status.yaml:184](../../_bmad-output/implementation-artifacts/sprint-status.yaml#L184) `epic-9: in-progress` → `done` (last Epic 9 story — see AC #7's epic-close-out bullet).

## Dev Notes

### Path A/B/C decision tree (read first)

Because 9.8 is explicitly optional, the first call the dev makes is whether to run it at all. The decision tree:

1. **Is the team actively considering moving off Celery in the next 90 days?** If yes → Path A (run the full spike — produce the decision doc). If no → Path B or C.
2. **Does the team want the "why we stayed on Celery" answer in git log for future hires / contractors?** If yes → Path A or C. If no → Path B (skip — record in Completion Notes that the epic default is accepted without a doc).
3. **Has someone already asked "why didn't we use Step Functions?" in the last 60 days?** If yes → Path A (the question will recur; put the answer on the record). If no → Path B is defensible.

The spike's *output* value is not the migration decision (the default is to stay) — it's the **cost of answering the "why didn't we?" question again and again over the product's lifetime**. If the team would have to litigate that question repeatedly, a 1-day spike pays for itself.

### Why this is a research story, not an implementation story

Epic 9 Story 9.8 reads (verbatim, [epics.md:2070-2071](../../_bmad-output/planning-artifacts/epics.md#L2070-L2071)):

> **9.8 — Pipeline Orchestration Evaluation (Optional, Time-Boxed Spike)**
> Compare current Celery+Redis architecture to AWS Step Functions / AWS Batch for Epic 3/8 pipeline. Output: recommendation doc only — actual migration requires separate approval. **Default outcome: stay on Celery.**

Every word matters:

- **Compare** — desk research, not proof-of-concept. Prototyping would bust the time-box and produce a biased "we already built half of it, might as well finish" outcome.
- **Recommendation doc only** — the deliverable is markdown, not code or infra. AC #6 enforces this.
- **Separate approval** — even a `migrate to X` outcome does NOT license this story's dev to start the migration. AC #5 enforces this.
- **Default outcome: stay on Celery** — the scoring bar (`+2 net` in AC #4) is calibrated to preserve the default unless a candidate clearly wins.

### Why `+2 net` and not `+1 net` or simple majority

A migration decision costs multi-week dev time, destabilises a working system, and creates a follow-up drag of incidental re-work (runbook updates, CI changes, new IAM). A candidate that ties or wins narrowly on 3–6 ordinal criteria is not strong evidence that migration pays off — ordinal scoring has ±1 noise per axis just from reviewer judgment. `+2 net` is one noise-increment above tie, which is the minimum signal strength a migration decision should require. This is conservative on purpose; the epic's *"Default: stay on Celery"* framing sets the conservatism policy.

If a future re-run wants to lower the bar (e.g. because the team has adopted AWS orchestrators for other services and the migration cost has dropped), the bar itself becomes the debate — which is healthier than the bar being implicit and re-negotiated per spike.

### LangGraph is the subtle constraint

The 4-node LangGraph pipeline at [backend/app/agents/pipeline.py](../../backend/app/agents/pipeline.py) is not a DAG that Step Functions can natively express — it's an in-process state machine with a checkpointer ([backend/app/agents/checkpointer.py](../../backend/app/agents/checkpointer.py)) that rehydrates from Postgres. Any orchestrator that "replaces" Celery has to decide:

- **Run the whole LangGraph inside one task/state.** Orchestrator becomes a retry wrapper; LangGraph internals are unchanged. This is trivially easy to evaluate but rarely worth the migration effort (why adopt Step Functions if you're just using it as a retry wrapper Celery already provides?).
- **Split the LangGraph's 4 nodes into orchestrator states.** Then the LangGraph checkpointer becomes redundant (orchestrator owns state) or doubly-authoritative (both own state — which wins on conflict?). This is a significant re-architecting and is what criterion 1 (Fit-for-LangGraph) scores harshly against.

LangGraph's own deployment docs — if they document a "native Step Functions backend" — would be the single biggest signal that re-evaluating is worth the time. As of 2026-04, LangGraph does not ship such a backend. This is the trigger condition for TD-092's "re-run when LangGraph ships native Step Functions backend" clause.

### Epic 10 is not in scope — chat is AgentCore-native

A common confusion: *"surely the chat pipeline would benefit from Step Functions?"* — no. Chat runs on AWS-managed AgentCore runtime per [architecture.md:1614-1619](../../_bmad-output/planning-artifacts/architecture.md#L1614-L1619), not on ECS Celery workers. The Chat Agent's scheduler *is* AgentCore; adding Step Functions on top would be a third layer. The scope of this evaluation is **batch agents only** (categorization, pattern detection, triage, education — the Epic 3/8 pipeline that actually runs on Celery today).

Call this out in the decision doc's `Impact on downstream work > Epic 10` bullet, because a reviewer who hasn't read the architecture section will assume otherwise.

### Doc-drift note (low stakes)

[architecture.md:1339](../../_bmad-output/planning-artifacts/architecture.md#L1339) refers to `tasks/pipeline_tasks.py`. The actual file is `backend/app/tasks/processing_tasks.py` (see [backend/app/tasks/](../../backend/app/tasks/)). This is the same genus of doc-drift that Story 9.7's AC #2 flagged (*"architecture.md says FastAPI ECS task role but current infra uses App Runner"*) — worth a one-line mention in the decision doc's Current-Architecture-Baseline section so a reviewer isn't led astray, but not worth a TD entry on its own. If it becomes a recurring confusion, escalate to a single "architecture.md doc-drift sweep" TD.

### Time-box discipline — the main failure mode

The most common way this kind of spike goes wrong is scope creep: the evaluator starts prototyping a Step Functions state machine "just to see", and 3 days later there's a half-built artifact that nobody approved, nobody owns, and nobody wants to throw away. AC #6's file-change allowlist is the hard guardrail; the evaluator's own discipline is the soft one.

The Time-Box Ledger section (AC #3) is the main accountability mechanism. If the ledger says `Fit-for-LangGraph: 4.5 hours`, a future reviewer can see exactly where the time went and whether the criterion was worth that much attention. If the ledger's `Total` overshoots 8 hours, the overshoot triggers TD-092's MEDIUM variant — which is a cheap accountability cost and a fair trade for allowing overflow when it's truly warranted.

### Previous story intelligence (9.7 → 9.8)

- Story 9.7 landed 2026-04-23 — pure Terraform, no backend/Python. Delivered: Celery ECS task role with `bedrock:InvokeModel` + `bedrock:ApplyGuardrail`, App Runner instance role with `bedrock-agentcore:*`, cost-allocation tags (`feature` / `epic` / `env`), GitHub OIDC CI role for the Bedrock matrix, tfsec clean. Close-out landed `873 passed, 23 deselected` per that story's Completion Notes.
- 9.7's code review surfaced **TD-091** (HIGH) — the Terraform state backend is dev-authoritative, so un-targeted prod applies would destroy Cognito + S3 uploads. That TD is unrelated to 9.8 (9.8 touches no Terraform per AC #6) but a reviewer seeing "Terraform" in the environment may conflate them. Confirm no `.tf` edit in 9.8's PR.
- The closest prior art for *this* story's shape is **Story 9.3 (Embedding Model Comparison Spike)** and **Story 9.4 (AgentCore + Bedrock Region Availability Spike)** — both research stories that produced committed decision docs under `docs/decisions/` with the same Context / Methodology / Results / Outcome / Rationale structure. AC #3 codifies that structure for 9.8 so reviewers don't have to re-learn the layout.
- 9.6 landed the halfvec embedding migration (Postgres-side only); no pipeline-orchestration impact. 9.5a/b/c landed the provider routing + Bedrock smoke + regression matrix; also no pipeline-orchestration impact — the multi-provider work operates *inside* each pipeline node (via `llm.py`), not at the orchestration layer.

### Git intelligence

Recent commits on `main` (at time of story creation, 2026-04-23):

```
5f4f567 Story 9.7: Bedrock IAM + Observability Plumbing
a4bd508 Story 9.6: Embedding Migration — text-embedding-3-large (3072-dim halfvec)
cccdeff Story 9.5c: Cross-Provider Regression Suite
6251282 Story 9.5b: Add Bedrock Provider Path + Smoke Test
7d99958 Story 9.5a: Provider-Routing Refactor (Anthropic + OpenAI only)
```

All Epic 9. Pattern: each story lands as a single squash-merge with a `Story N.M:` prefix. 9.8 should follow the same convention: squash-merge with commit title `Story 9.8: Pipeline Orchestration Evaluation Spike (decision doc)`.

### Latest technical context

- **AWS Step Functions pricing** (2026-04, from the public pricing page): Standard Workflows at $0.025 per 1,000 state transitions + duration. Express Workflows at $1.00 per million requests + duration-GB-second. For the current throughput (low 3-digits uploads/month at most in prod today), Standard pricing is negligible — cost is not the decisive axis. The decisive axis is LangGraph compatibility (criterion 1) and migration effort (criterion 2).
- **AWS Batch on Fargate** (2026-04): Batch service itself is free; pay only for Fargate compute. Retry semantics via `RetryStrategy.attempts` (1–10). DLQ via SQS integration. Batch on Fargate has been GA since 2020 and is production-hardened.
- **LangGraph** (2026-04, per the project's current `pyproject.toml` pin — verify at implementation time): LangGraph provides a PostgresSaver checkpointer (`langgraph-checkpoint-postgres`) that this pipeline already uses. It does NOT provide a native Step Functions or Batch backend as of 2026-04. This is a moving target — re-verify in the decision doc.
- **Celery 5.x** (current): stable, boring, understood. The cost of staying is known; the cost of leaving is the subject of the spike.

### Project Structure Notes

- Alignment with unified project structure: decision doc lands under `docs/decisions/` — matches [docs/decisions/](../../docs/decisions/) convention established by Stories 9.3 / 9.4 / 9.5b (embedding-model-comparison, agentcore-bedrock-region-availability, bedrock-provider-smoke). No new directory, no index.md required.
- Naming convention for decision docs: `<topic>-<YYYY-MM>.md`. This story's file: `pipeline-orchestration-evaluation-2026-04.md` — matches.
- No code changes → no alignment concerns with backend / frontend / infra project structures. AC #6's allowlist enforces this.

### Detected conflicts or variances

- **architecture.md:1339 vs actual filename:** references `tasks/pipeline_tasks.py`; actual file is `processing_tasks.py`. Captured in Dev Notes (doc-drift note above); no TD needed unless it recurs.
- **epics.md:2070-2071 vs architecture.md:1651-1653:** both phrase the same scope consistently (*"Output: recommendation doc only — actual migration requires separate approval. Default outcome: stay on Celery"*). No drift — good.
- **epic-9 status at [sprint-status.yaml:184](../../_bmad-output/implementation-artifacts/sprint-status.yaml#L184):** currently `in-progress`. Per AC #7's epic close-out bullet, this flips to `done` after 9.8 closes (the only remaining backlog story in Epic 9).

### References

- Epic narrative for 9.8: [_bmad-output/planning-artifacts/epics.md:2070-2071](../../_bmad-output/planning-artifacts/epics.md#L2070-L2071)
- Architecture orchestration section (matching epic wording): [_bmad-output/planning-artifacts/architecture.md:1651-1653](../../_bmad-output/planning-artifacts/architecture.md#L1651-L1653)
- Current Celery pipeline — code: [backend/app/tasks/celery_app.py](../../backend/app/tasks/celery_app.py), [backend/app/tasks/processing_tasks.py](../../backend/app/tasks/processing_tasks.py)
- Current LangGraph 4-node graph: [backend/app/agents/pipeline.py](../../backend/app/agents/pipeline.py)
- PostgresSaver checkpointer: [backend/app/agents/checkpointer.py](../../backend/app/agents/checkpointer.py)
- Current Celery ECS worker service: [infra/terraform/modules/ecs/main.tf:82-126](../../infra/terraform/modules/ecs/main.tf#L82-L126)
- Current ElastiCache Redis broker: [infra/terraform/modules/elasticache/main.tf](../../infra/terraform/modules/elasticache/main.tf)
- Chat is NOT on Celery (AgentCore-native): [_bmad-output/planning-artifacts/architecture.md:1614-1619](../../_bmad-output/planning-artifacts/architecture.md#L1614-L1619)
- Decision doc convention (Story 9.3 prior art): [docs/decisions/embedding-model-comparison-2026-04.md](../../docs/decisions/embedding-model-comparison-2026-04.md)
- Decision doc convention (Story 9.4 prior art): [docs/decisions/agentcore-bedrock-region-availability-2026-04.md](../../docs/decisions/agentcore-bedrock-region-availability-2026-04.md)
- AWS Step Functions pricing: `https://aws.amazon.com/step-functions/pricing/`
- AWS Batch on Fargate docs: `https://docs.aws.amazon.com/batch/latest/userguide/fargate.html`
- Sprint status entry: [_bmad-output/implementation-artifacts/sprint-status.yaml:209](../../_bmad-output/implementation-artifacts/sprint-status.yaml#L209)
- Tech-debt register (highest existing TD): [docs/tech-debt.md](../../docs/tech-debt.md) (TD-091 per Story 9.7)
- Auto-memory pointer — Epic 11 observability substrate: [/Users/ohumennyi/.claude/projects/-Users-ohumennyi-Personal-kopiika-ai/memory/project_observability_substrate.md](/Users/ohumennyi/.claude/projects/-Users-ohumennyi-Personal-kopiika-ai/memory/project_observability_substrate.md) (relevant to criterion 5 — observability ceiling is already set by 11.9's CloudWatch Insights plan)
- Auto-memory pointer — tech-debt conventions: [/Users/ohumennyi/.claude/projects/-Users-ohumennyi-Personal-kopiika-ai/memory/reference_tech_debt.md](/Users/ohumennyi/.claude/projects/-Users-ohumennyi-Personal-kopiika-ai/memory/reference_tech_debt.md) (TD-NNN ID pattern)

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List
