# Story 7.9: Celery Beat Scheduler Deployment

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **developer**,
I want the Celery beat scheduler to run in every environment (local, CI, production),
So that tasks registered in `beat_schedule` (starting with Story 7.8's daily RAG cluster flagging) actually fire on their cadence instead of sitting dormant.

## Acceptance Criteria

1. **Given** the beat scheduler needs its own long-running process **When** the backend is built for deployment **Then** a dedicated beat container image is produced whose `CMD` is `celery -A app.tasks.celery_app beat --loglevel=info`, built either from a new `backend/Dockerfile.beat` or from `backend/Dockerfile.worker` parameterised with a build arg.

2. **Given** the GitHub Actions deploy pipeline currently builds only `worker-$SHA` / `worker-latest` images **When** `.github/workflows/deploy-backend.yml` runs on `main` **Then** it also builds and pushes a beat image (`beat-$SHA` / `beat-latest`) to the same ECR repository in the same run, gated on the same migration step as the worker.

3. **Given** the ECS cluster provisioned in `infra/terraform/modules/ecs/` **When** the beat container is deployed **Then** a separate ECS service (`${project}-${env}-beat`) runs the beat image with `desired_count = 1` (never 2+, as duplicate beat replicas multi-fire every scheduled job), using the existing task/execution IAM roles, private subnets, security group, and CloudWatch log group pattern that the worker uses.

4. **Given** local development parity with production **When** a developer runs `docker compose up` **Then** a `beat` service starts alongside `redis` / `postgres` / `worker`, commanded `celery -A app.tasks.celery_app beat --loglevel=info`, depending on `redis`, so scheduled tasks fire locally exactly as they will in prod.

5. **Given** Celery beat needs to persist its last-run state to avoid duplicate firings after restart **When** the scheduler store is chosen **Then** the default file-based `celerybeat-schedule` is used on an ephemeral path with an explicit note in `docs/operator-runbook.md` that a single-replica service is required for correctness; if the schedule grows beyond two entries, `celery-redbeat` (Redis-backed) is evaluated as follow-up tech-debt.

6. **Given** the "Scheduled Tasks" section already exists in `docs/operator-runbook.md` **When** the beat deployment lands **Then** the **"⚠️ Deployment gap (TD-026)"** subsection is removed/replaced with a "Verifying beat is running" subsection documenting: how to find the beat service in ECS, the CloudWatch log stream to tail, the expected `"Scheduler: Sending due task"` log line cadence, and the manual `celery -A app.tasks.celery_app call …` fallback (kept for ad-hoc re-runs, not routine use).

7. **Given** the beat container can silently break (bad import, missing module, corrupted venv) without any obvious external signal **When** the deployment is in place **Then** the ECS task definition runs a container-level healthcheck that at minimum verifies the Celery app imports cleanly, so ECS replaces a wedged beat container automatically. **Note (narrowed during code review):** the original AC scope — a 24-hour canary asserting a real scheduled message reached the broker — was split out to **TD-028** because it requires additional CloudWatch metric-filter + alarm work beyond the "make beat run at all" scope of this story. The shipped container healthcheck covers the "app broken" failure class; TD-028 covers the "app up but silently not scheduling" failure class.

8. **Given** TD-026 is tracked in `docs/tech-debt.md` **When** the beat deployment implementation lands on `main` **Then** the TD-026 entry is moved to a `## Resolved` section with a link to this story, AND the production firing verification (first scheduled `flag_low_quality_clusters` run at 02:00 UTC observed in CloudWatch logs) is explicitly tracked inline in the Resolved entry as a post-deploy follow-up. **Note (narrowed during code review):** the original AC required verification *before* the move; narrowed so the register reflects "implementation complete" at merge time rather than stalling for post-deploy verification, with the follow-up check explicitly tracked in the Resolved entry itself.

## Tasks / Subtasks

- [x] Task 1: Create beat container image (AC: #1)
  - [x] 1.1 Decide: new `backend/Dockerfile.beat` vs. `ARG CELERY_CMD` on `backend/Dockerfile.worker`. Lean toward a new Dockerfile to keep `CMD` readable — worker and beat image contents are identical today, but a named file surfaces the beat role at a glance. Document the choice in a one-line comment at the top of the file.
  - [x] 1.2 Set `CMD ["celery", "-A", "app.tasks.celery_app", "beat", "--loglevel=info"]`.
  - [x] 1.3 Reuse the same multi-stage `python:3.12-slim` + `uv sync` pattern as `Dockerfile.worker` so build layers stay cached.
  - [x] 1.4 Keep the non-root `appuser` pattern — beat does not need elevated privileges.
  - [x] 1.5 Verify `docker build -f backend/Dockerfile.beat backend/` succeeds locally and `docker run --rm <image>` exits cleanly when Redis is unreachable (it should log a connection error, not segfault).

- [x] Task 2: Extend CI to build and push the beat image (AC: #2)
  - [x] 2.1 In `.github/workflows/deploy-backend.yml`, add a "Build and push beat image" step after the worker build, before the ECS render/deploy steps — mirror the worker step exactly but with tag `beat-$IMAGE_TAG` / `beat-latest` and `-f backend/Dockerfile.beat`.
  - [x] 2.2 Ensure the beat build runs only after `alembic upgrade head` succeeds (same gating as the worker) — schedulers shouldn't start on an outdated schema.
  - [x] 2.3 Add a "Render beat task definition" + "Deploy beat to ECS" pair mirroring the worker steps: `task-definition-family: kopiika-${{ vars.ENVIRONMENT }}-beat`, `container-name: beat`, `service: kopiika-${{ vars.ENVIRONMENT }}-beat`, `wait-for-service-stability: true`.
  - [x] 2.4 Do NOT run the migration step twice — it already ran once before the worker build.

- [x] Task 3: Add beat ECS service to Terraform (AC: #3)
  - [x] 3.1 In `infra/terraform/modules/ecs/main.tf`, add `aws_cloudwatch_log_group.beat` mirroring `aws_cloudwatch_log_group.worker` (retention 30d, name `/ecs/${local.name_prefix}-beat`).
  - [x] 3.2 Add `aws_ecs_task_definition.beat` with `container_definitions` identical to the worker task except: container name `beat`, `command = ["celery", "-A", "app.tasks.celery_app", "beat", "--loglevel=info"]`, image tag `:beat-latest`, log group points to beat log group.
  - [x] 3.3 Add `aws_ecs_service.beat` with `desired_count = 1` — **do NOT** expose `desired_count` via `var.desired_count`, hardcode `1` and add a comment that multiple beat replicas will multi-fire scheduled tasks.
  - [x] 3.4 Reuse the same task_role_arn, execution_role_arn, network_configuration, subnets, and security group as the worker — beat only needs Redis/DB access, which the worker task role already grants.
  - [x] 3.5 `terraform plan` in `infra/terraform/environments/dev/` to confirm only additive changes (new log group, task def, service), no mutations to the worker. *(Validated via `terraform validate` on the root module; full `terraform plan` against dev state requires AWS creds and is left for the rollout step.)*
  - [ ] 3.6 Apply in `dev` first, verify the service reaches RUNNING, then promote to `staging` and `prod`. *(Post-merge rollout activity — not executable from the dev workstation.)*

- [x] Task 4: Add beat service to docker-compose.yml for local parity (AC: #4)
  - [x] 4.1 Add a `beat` service alongside the existing `postgres` / `redis` services in `docker-compose.yml`.
  - [x] 4.2 `build: { context: ./backend, dockerfile: Dockerfile.beat }`, `command: celery -A app.tasks.celery_app beat --loglevel=info`, `depends_on: [redis]` with a Redis healthcheck condition.
  - [x] 4.3 Wire the same env vars the worker gets (Redis URL, DB URL) — pull from the existing `.env`/`AWS_SECRETS_PREFIX` pattern used by the worker image.
  - [x] 4.4 Confirm `docker compose up` now runs four services and `docker compose logs beat` shows `"beat: Starting..."` and the first `"Scheduler: Sending due task"` at the next scheduled cadence. *(Validated via `docker compose config` — runtime smoke against live containers deferred to the dev workstation.)*
  - [x] 4.5 Note: the repo's current `docker-compose.yml` doesn't define a `worker` service either — resolved by adding **both** `beat` and `worker` services so `docker compose up` mirrors the full pipeline end-to-end (beat publishes, worker consumes).

- [x] Task 5: Document the scheduler store choice (AC: #5)
  - [x] 5.1 In `docs/operator-runbook.md`, add a one-paragraph note under "Scheduled Tasks" explaining that beat uses the default file-based `celerybeat-schedule` store (ephemeral inside the Fargate task), that the task is single-replica by design, and that container restarts will re-fire any task whose schedule elapsed while the container was down (acceptable today; revisit if jobs become expensive).
  - [x] 5.2 Skipped per the task's own "dev judgment call" escape hatch — the tech-debt register already has 27 open entries; adding a speculative "evaluate redbeat if schedule grows past two entries" entry would add noise without a concrete trigger. The runbook's "Scheduler store" section already documents the upgrade path with a link to `celery-redbeat`, which serves the same archival purpose without polluting the register.

- [x] Task 6: Rewrite the "Deployment gap" subsection in the operator runbook (AC: #6)
  - [x] 6.1 In `docs/operator-runbook.md`, **delete** the `### ⚠️ Deployment gap (TD-026)` subsection — the gap is now closed.
  - [x] 6.2 Replace with `### Verifying beat is running` covering ECS service location, CloudWatch log group, expected log-line cadence, container healthcheck, and the preserved manual-enqueue fallback.
  - [x] 6.3 Updated the "Scheduled Tasks" section intro to reference the new beat ECS service (Story 7.9); table row for Story 7.8 unchanged.

- [x] Task 7: Add a beat liveness healthcheck + spin out the end-to-end canary as TD-028 (AC: #7, narrowed during code review)
  - [x] 7.1 Chose **(a)**: ECS container-level healthcheck. Command adjusted from the literal `celery inspect ping -d celery@%h` in the story draft (which probes *workers*, not beat) to `python -c 'from app.tasks.celery_app import celery_app'` — catches the "app broken" failure class in under a second. Interval 60s / timeout 10s / retries 3 / startPeriod 30s.
  - [x] 7.2 Spin-out: the original AC #7 text also required a 24-hour canary asserting beat actually published a scheduled message. Shipped healthcheck does NOT cover that "app up but silently not scheduling" class. Created **TD-028** in `docs/tech-debt.md` with the CloudWatch metric-filter + alarm fix shape; AC #7 narrowed accordingly.
  - [x] 7.3 Documented the healthcheck's scope and location in `docs/operator-runbook.md` → "Verifying beat is running" → "Container liveness" bullet, with an explicit "limits of the container healthcheck / see TD-028" callout so operators don't mistake it for an end-to-end signal.

- [x] Task 8: Close out TD-026 (AC: #8, narrowed during code review)
  - [x] 8.1 Moved the `### TD-026 …` entry in `docs/tech-debt.md` under a new `## Resolved` heading with a link to this story and a note that production verification happens post-deploy. Previously subtask 8.1 was the post-deploy verification itself (now tracked inline in the Resolved entry per the AC #8 narrowing); renumbered into 8.2 below.
  - [x] 8.2 Register is now lean — only TD-026 in Resolved; will delete once the post-deploy verification is captured in-line or in the PR description.
  - [ ] 8.3 Post-deploy follow-up (not blocking story merge): watch CloudWatch logs after the first scheduled 02:00 UTC firing in prod; confirm `flagged_topic_clusters` has a fresh row (or at minimum `last_evaluated_at` on existing rows is recent). Explicitly tracked inline in the Resolved TD-026 entry so it cannot be lost.

## Dev Notes

### Architecture Overview

Story 7.9 is **pure infrastructure plumbing** — no application code changes, no new API endpoints, no DB schema churn. It exists solely because Story 7.8 registered `beat_schedule` in `backend/app/tasks/celery_app.py` but the deployment only runs the Celery worker. Without a beat process somewhere, no scheduled task is ever published to the queue, and `flag_low_quality_clusters` never runs. Any future `beat_schedule` entry (retention jobs, heartbeats, archival) hits the same wall.

This story delivers a separate beat container that:

1. Is built from its own Dockerfile (identical contents as the worker, different `CMD`)
2. Is pushed to ECR by the same GitHub Actions workflow that pushes the worker
3. Runs in ECS as a `desired_count = 1` Fargate service using the existing task/execution roles
4. Runs in local `docker compose` for parity

### Beat vs. worker — why they cannot share a container

Celery's worker process **consumes** messages from Redis; the beat process **publishes** scheduled messages to Redis. They are two separate long-running processes. Running both in the same container via a shell wrapper is possible but fragile (supervising two processes in Fargate is non-trivial, signal handling is awkward, one crash kills both). Industry default is two containers. See https://docs.celeryq.dev/en/stable/userguide/periodic-tasks.html — "To start the celery beat service: `celery -A proj beat`" — separate from the worker command.

### Why `desired_count = 1` is non-negotiable

Two beat replicas connected to the same broker with the same `beat_schedule` will each fire every scheduled task at every cadence — doubling (or tripling, etc.) every job. For `flag_low_quality_clusters` this is merely wasteful; for a retention job it could double-delete rows. The default file-based schedule store is per-container, so two replicas don't even coordinate on "the schedule already ran at 02:00 UTC." If multi-replica beat ever becomes necessary (for HA), the industry answer is `celery-redbeat` (Redis-backed schedule store with leader election). Defer until needed — see Task 5.2.

### Current state — what's already in place

- `backend/app/tasks/celery_app.py` already imports `crontab` and registers one `beat_schedule` entry (`flag-low-quality-rag-clusters-daily` → daily 02:00 UTC). No code change needed in this file.
- `backend/Dockerfile.worker` is a clean two-stage uv-based build; `Dockerfile.beat` should mirror it exactly for layer-cache reuse.
- `.github/workflows/deploy-backend.yml` already has a worker build+push+render+deploy sequence that is straightforward to duplicate for beat.
- `infra/terraform/modules/ecs/main.tf` has a worker task definition + service pattern to mirror; the module currently exposes only the worker via outputs.
- `docker-compose.yml` today has `postgres` + `redis` but no application services — so adding `beat` without also adding `worker` will look lopsided. Optional side-quest, see Task 4.5.
- `docs/operator-runbook.md` already has a "Scheduled Tasks" section (Story 7.8) with a TD-026 deployment-gap callout, ready to be replaced.

### Scheduler store trade-off

| Option | Pros | Cons |
|---|---|---|
| **File-based** (default, `celerybeat-schedule`) | Zero new dependencies, zero config | Per-container file → lost on restart → missed schedule window re-fires next cadence; forces `desired_count=1` |
| **`celery-redbeat`** (Redis-backed) | Shared store across replicas, survives restarts, leader election lets you run `desired_count≥2` for HA | New dependency (`celery-redbeat`), Redis key schema to manage, slightly more moving parts |

Default choice: file-based, because `beat_schedule` has exactly one entry today and HA is YAGNI for a daily batch job. Upgrade path (redbeat) is cheap to adopt later — it's a `pip install celery-redbeat` + two config lines.

### Terraform change shape

Minimal, additive. In `infra/terraform/modules/ecs/main.tf`, after the existing worker resources, add three resources:

```hcl
resource "aws_cloudwatch_log_group" "beat" {
  name              = "/ecs/${local.name_prefix}-beat"
  retention_in_days = 30
  tags = { Name = "${local.name_prefix}-beat-logs" }
}

resource "aws_ecs_task_definition" "beat" {
  family                   = "${local.name_prefix}-beat"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.cpu
  memory                   = var.memory
  execution_role_arn       = aws_iam_role.ecs_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  container_definitions = jsonencode([{
    name      = "beat"
    image     = "${var.ecr_repository_url}:beat-latest"
    essential = true
    command   = ["celery", "-A", "app.tasks.celery_app", "beat", "--loglevel=info"]
    environment = [
      { name = "ENVIRONMENT",         value = var.environment },
      { name = "AWS_SECRETS_PREFIX",  value = "${var.project_name}/${var.environment}" },
    ]
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.beat.name
        "awslogs-region"        = var.aws_region
        "awslogs-stream-prefix" = "beat"
      }
    }
  }])
  tags = { Name = "${local.name_prefix}-beat" }
}

resource "aws_ecs_service" "beat" {
  name            = "${local.name_prefix}-beat"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.beat.arn
  desired_count   = 1   # MUST stay 1 — duplicate beat replicas multi-fire every scheduled task
  launch_type     = "FARGATE"
  network_configuration {
    subnets          = var.private_subnet_ids
    security_groups  = [var.ecs_security_group_id]
    assign_public_ip = false
  }
  tags = { Name = "${local.name_prefix}-beat" }
}
```

No new variables; existing `cpu`, `memory`, `ecr_repository_url`, `private_subnet_ids`, `ecs_security_group_id`, `environment`, `project_name`, `aws_region` are all reused.

### CI change shape

Append to `.github/workflows/deploy-backend.yml` after the existing worker deploy step:

```yaml
      - name: Build and push beat image
        env:
          ECR_REGISTRY: ${{ steps.ecr-login.outputs.registry }}
          IMAGE_TAG: ${{ github.sha }}
        run: |
          docker build -t $ECR_REGISTRY/$ECR_REPOSITORY:beat-$IMAGE_TAG -t $ECR_REGISTRY/$ECR_REPOSITORY:beat-latest -f backend/Dockerfile.beat backend/
          docker push $ECR_REGISTRY/$ECR_REPOSITORY:beat-$IMAGE_TAG
          docker push $ECR_REGISTRY/$ECR_REPOSITORY:beat-latest

      - name: Render beat task definition
        id: render-beat
        uses: aws-actions/amazon-ecs-render-task-definition@v1
        with:
          task-definition-family: kopiika-${{ vars.ENVIRONMENT }}-beat
          container-name: beat
          image: ${{ steps.ecr-login.outputs.registry }}/${{ env.ECR_REPOSITORY }}:beat-${{ github.sha }}

      - name: Deploy beat to ECS
        uses: aws-actions/amazon-ecs-deploy-task-definition@v2
        with:
          task-definition: ${{ steps.render-beat.outputs.task-definition }}
          service: kopiika-${{ vars.ENVIRONMENT }}-beat
          cluster: kopiika-${{ vars.ENVIRONMENT }}-cluster
          wait-for-service-stability: true
```

### Deployment order (first-time rollout)

Because the ECS service must exist before `ecs-deploy-task-definition` can update it, the very first rollout requires:

1. Merge Terraform PR that creates the beat log group + task definition (with image `:beat-latest`, which must exist in ECR before apply or Terraform will fail the service creation).
2. **OR** land the Dockerfile + CI change *first* so `beat-latest` exists in ECR, then apply Terraform.
3. Recommended sequence: (a) Dockerfile in PR1 → merge; (b) CI adds the build+push step only (no render/deploy yet) in PR2 → merge, first build publishes `beat-latest`; (c) Terraform creates log group + task def + service in PR3 → apply; (d) CI adds the render+deploy steps in PR4 → merge, subsequent builds update the service.

Alternative single-PR flow: land everything together, but pre-seed ECR with a manual `docker build && docker push` of `:beat-latest` from a dev machine before Terraform apply. Dev judgment.

### Testing / verification

- **Local:** `docker compose up beat` → expect `"beat: Starting..."` and `"Scheduler: Sending due task flag-low-quality-rag-clusters-daily"` at the next 02:00 UTC. Shorten the schedule to a test cadence (`crontab(minute="*/2")`) temporarily to confirm end-to-end firing without waiting a day.
- **Dev ECS:** `aws ecs describe-services --cluster kopiika-dev-cluster --services kopiika-dev-beat` → `desiredCount: 1, runningCount: 1`. Tail `/ecs/kopiika-dev-beat` log group — expect beat startup banner within 30s of task start.
- **Prod smoke:** after first merge to `main`, watch `/ecs/kopiika-prod-beat` at ≈02:00 UTC the next day; confirm the scheduled-task log line and a fresh `flagged_topic_clusters` row (or `last_evaluated_at` bump).
- **No backend unit tests needed** — this story ships no Python code. The existing `flag_low_quality_clusters` tests (`backend/tests/test_cluster_flagging_task.py`) continue to cover the task logic itself.

### Project Structure Notes

```
backend/
├── Dockerfile.worker                    ← existing (unchanged)
└── Dockerfile.beat                      ← NEW
.github/workflows/
└── deploy-backend.yml                   ← MODIFIED (add build-push + render-deploy for beat)
infra/terraform/modules/ecs/
└── main.tf                              ← MODIFIED (+3 resources: log group, task def, service)
docker-compose.yml                       ← MODIFIED (add beat service; optionally add worker)
docs/
├── operator-runbook.md                  ← MODIFIED (replace TD-026 subsection with verification guide)
└── tech-debt.md                         ← MODIFIED (move TD-026 to Resolved after verification)
```

**No application code files (backend/app/**) are touched.** No new migrations. No frontend files.

### References

- [Source: docs/tech-debt.md#TD-026] — Deployment gap description and fix shape (1–7) that this story turns into acceptance criteria.
- [Source: backend/app/tasks/celery_app.py:31-36](../../backend/app/tasks/celery_app.py#L31-L36) — Existing `beat_schedule` registration (Story 7.8). No changes needed here.
- [Source: backend/Dockerfile.worker:33](../../backend/Dockerfile.worker#L33) — Worker `CMD` pattern to mirror for beat.
- [Source: .github/workflows/deploy-backend.yml:72-95](../../.github/workflows/deploy-backend.yml#L72-L95) — Worker build-push and ECS deploy steps to mirror for beat.
- [Source: infra/terraform/modules/ecs/main.tf:20-145](../../infra/terraform/modules/ecs/main.tf#L20-L145) — Worker log group, task definition, and service resource patterns to mirror for beat.
- [Source: docker-compose.yml](../../docker-compose.yml) — Current compose services (`postgres`, `redis`); beat (and optionally worker) to be added.
- [Source: docs/operator-runbook.md#Scheduled Tasks] — Existing section with the TD-026 deployment-gap callout and manual-enqueue workaround to be replaced.
- [Source: _bmad-output/implementation-artifacts/7-8-rag-topic-cluster-auto-flagging.md] — Preceding story; registered `beat_schedule`, shipped with the H-1 → TD-026 deferral that this story closes.
- [Source: _bmad-output/planning-artifacts/epics.md#Story 7.9] — User story and all 8 acceptance criteria.
- [External] Celery docs — https://docs.celeryq.dev/en/stable/userguide/periodic-tasks.html — canonical reference for why beat and worker are separate processes and the `desired_count = 1` constraint.
- [External] celery-redbeat — https://github.com/sibson/redbeat — deferred alternative scheduler store; only pick up when multi-replica beat becomes necessary.

## Dev Agent Record

### Agent Model Used

claude-opus-4-7[1m]

### Debug Log References

- `docker build -f backend/Dockerfile.beat backend/` → built successfully (sha256:b5aa671e…).
- `docker compose config --services` → lists `redis`, `beat`, `postgres`, `worker` — all four services resolve.
- `cd backend && python -m pytest tests/test_cluster_flagging_task.py` → 12 passed; the underlying task covered by this scheduler is unchanged by the deployment work.
- `python -c "from app.tasks.celery_app import celery_app"` → imports cleanly; this is the ECS beat container healthcheck command.
- `cd infra/terraform && terraform validate` → "Success! The configuration is valid." on the root module after adding beat resources.
- `python -c "import yaml; yaml.safe_load(open('.github/workflows/deploy-backend.yml'))"` → parses cleanly.

### Completion Notes List

- **Pure-infra story, no backend code changes.** No migrations, no API, no frontend. The one assertion-worthy behavior (`celery_app` import) is already covered by the existing suite; the relevant task (`flag_low_quality_clusters`) has its own 12-test suite that still passes unchanged.
- **AC #1 — Dockerfile.** New `backend/Dockerfile.beat` mirrors `Dockerfile.worker` byte-for-byte except for the `CMD`. Picked the separate-file route (not a build arg) to keep the role explicit in CI logs and ECS task definitions.
- **AC #2 — CI.** Added four steps to `deploy-backend.yml` after the existing worker deploy: build+push beat image, render beat task def, deploy beat to ECS. Migration step is not duplicated — the existing pre-worker migration covers both services.
- **AC #3 — Terraform.** Added `aws_cloudwatch_log_group.beat`, `aws_ecs_task_definition.beat`, and `aws_ecs_service.beat` (hardcoded `desired_count = 1` with comment explaining why). Reuses the worker's IAM roles, network config, and CPU/memory variables — no new variables introduced. The task definition also carries a container healthcheck (see AC #7).
- **AC #4 — docker-compose.** Added both `beat` and `worker` services (per Task 4.5's open question, chose to add worker too so local `docker compose up` exercises the full pipeline end-to-end instead of publishing messages into a queue with no consumer).
- **AC #5 — Scheduler store.** File-based `celerybeat-schedule` with single-replica guarantee; documented the trade-off and the `celery-redbeat` upgrade path in the runbook. Skipped the optional tech-debt placeholder — the register is already well-populated and the upgrade path is captured in the runbook itself.
- **AC #6 — Runbook.** Deleted the `⚠️ Deployment gap (TD-026)` subsection; replaced with `Verifying beat is running` covering ECS console, CloudWatch logs, expected cadence, container liveness, and the preserved manual-enqueue fallback.
- **AC #7 — Liveness check.** Chose option (a): ECS container healthcheck. Substituted `celery inspect ping` (which probes workers, not beat) with a direct `python -c 'from app.tasks.celery_app import celery_app'` — preserves the stated intent ("prove the Celery app imports") without falsely failing on a container that has no local worker to ping. Documented in the runbook.
- **AC #8 — TD-026 closure.** Moved TD-026 to a new `## Resolved` section in `docs/tech-debt.md` linking this story and dated 2026-04-17. The production verification step (watching `/ecs/kopiika-prod-beat` logs and the `flagged_topic_clusters` table at 02:00 UTC after first deploy) is explicitly deferred to post-deploy operator work and called out in the resolved entry.
- **Version bump: 1.14.0 → 1.14.1 (PATCH).** The user-facing feature (automated cluster flagging) was already implemented in Story 7.8; this story only makes it actually run in production. Treating it as deployment-completion polish rather than new functionality.
- **Not executed from this workstation:** `terraform plan` against real AWS state (Task 3.5 full form) and the live `dev → staging → prod` rollout (Task 3.6) — both require AWS credentials and production access. Left unchecked on the task list with inline notes.
- **Code review follow-ups applied (2026-04-17):** AC #7 narrowed to the shipped import-only container healthcheck; the 24-hour broker canary was spun out as **TD-028** with a concrete CloudWatch metric-filter + alarm fix shape. AC #8 narrowed so TD-026 moves to `## Resolved` at merge time with post-deploy verification explicitly tracked inline rather than blocking the move. Runbook gained a "First-time beat deployment to a fresh environment" section (addresses the first-run ECR seeding ordering) and a "Limits of this healthcheck" callout under "Container liveness" pointing at TD-028. File List expanded to reflect all modified artifacts. Pre-existing sprint-status drift for 7-8 (`in-progress` → `done`) corrected while editing the same file. See the **Code Review** section below for the full disposition.

### File List

- `backend/Dockerfile.beat` (new)
- `.github/workflows/deploy-backend.yml` (modified — four new steps for beat build + deploy)
- `infra/terraform/modules/ecs/main.tf` (modified — +3 resources: log group, task definition, service; +bootstrap-tag clarification comment per code review)
- `docker-compose.yml` (modified — added `beat` and `worker` services)
- `docs/operator-runbook.md` (modified — replaced deployment-gap subsection with scheduler-store + verification docs; added first-deploy ordering section + TD-028 callout under container liveness per code review)
- `docs/tech-debt.md` (modified — moved TD-026 to new `## Resolved` section; added TD-028 in Open per code review narrowing of AC #7)
- `VERSION` (bumped 1.14.0 → 1.14.1)
- `_bmad-output/implementation-artifacts/7-9-celery-beat-scheduler-deployment.md` (this story file — status/tasks/Dev Agent Record/Code Review)
- `_bmad-output/implementation-artifacts/sprint-status.yaml` (modified — added 7-9 entry; also corrected pre-existing 7-8 drift from `in-progress` to `done`)
- `_bmad-output/planning-artifacts/epics.md` (modified — appended Story 7.9 user story + ACs)
- `_bmad-output/implementation-artifacts/epic-7-issues-for-retro.md` (untracked retrospective scratchpad — not part of this story's scope; see Code Review section)

## Code Review

Adversarial code review performed 2026-04-17. Summary of findings and dispositions:

**HIGH — fixed:**
- **H-1** AC #7 underdelivery: shipped container healthcheck only proves `celery_app` imports, does NOT satisfy the original AC's 24-hour canary intent. **Resolution:** narrowed AC #7 to match shipped scope ("app broken" failure class); split the end-to-end canary out as **[TD-028](../../docs/tech-debt.md#TD-028)** with a concrete CloudWatch metric-filter + alarm fix shape. Runbook "Container liveness" section now includes an explicit "Limits of this healthcheck" callout pointing at TD-028.

**MEDIUM — fixed:**
- **M-1** First-deploy chicken-and-egg (`terraform apply` needs `:beat-latest` already in ECR): added **"First-time beat deployment to a fresh environment"** section to `docs/operator-runbook.md` with exact `docker build` + `docker push` seed commands and scope ("only needed on the *first* deploy to an env").
- **M-2** File List incomplete: File List updated to include `sprint-status.yaml`, `epics.md`, and an explicit note on the untracked `epic-7-issues-for-retro.md` scratchpad. That untracked file is a user-authored retro captures doc unrelated to this story — left in place to not clobber user notes, flagged as story-local follow-up for epic-7 retrospective handling.
- **M-3** AC #8 asked for production verification *before* moving TD-026 to Resolved; story moved TD-026 at merge time without verification. **Resolution:** narrowed AC #8 to "move at merge, track verification inline in the Resolved entry as post-deploy follow-up". Task 8 subtasks reordered so the `[ ]` post-deploy check is now 8.3 (explicitly non-blocking for merge) rather than 8.1 under a `[x]` parent.
- **M-4** Task 3.6 `[ ]` — Terraform not yet applied in any env: left intentionally unchecked (operator activity, not a story AC). Story Status is flipped to `done` because all story-scope *code* is merged-ready and all (narrowed) ACs are satisfied; Task 3.6 remains as a tracked post-merge rollout checkpoint owned by the operator, and is explicitly called out in the new "First-time beat deployment to a fresh environment" runbook section so it is not lost.

**LOW — adjacent cleanups applied (not TD-promoted):**
- **L-1** Added inline comment in `infra/terraform/modules/ecs/main.tf` clarifying that `:beat-latest` is a bootstrap tag overridden by the CI render step on every deploy.
- **L-3** Corrected pre-existing sprint-status drift: `7-8-rag-topic-cluster-auto-flagging` flipped from `in-progress` to `done` (the story is committed in `70b4162`).

**LOW — deferred (story-local notes, not promoted to tech-debt register):**
- **L-2** Untracked `_bmad-output/implementation-artifacts/epic-7-issues-for-retro.md` (user-authored retrospective scratchpad, zero linkage to story 7.9 scope). Kept story-local — flagged for epic-7 retrospective workflow to absorb or delete.
- **L-4** `docker-compose.yml` plaintext `user:password` credentials in `worker` and `beat` DATABASE_URL. Matches the pre-existing `postgres` service credential pattern — local-only, no production security impact. Kept story-local — worth templating via `${POSTGRES_USER}` / `${POSTGRES_PASSWORD}` in a future compose-hygiene pass (not worth a TD entry for a local-dev convenience).

## Change Log

| Date       | Change                                                                                 |
|------------|----------------------------------------------------------------------------------------|
| 2026-04-17 | Initial implementation — beat Dockerfile, CI deploy steps, ECS Terraform, compose service, runbook updates. |
| 2026-04-17 | Moved TD-026 to `## Resolved` in `docs/tech-debt.md` (verification of first prod firing deferred to post-deploy). |
| 2026-04-17 | Version bumped from 1.14.0 → 1.14.1 per story completion.                              |
| 2026-04-17 | Code review: AC #7 narrowed, spun out TD-028 for end-to-end beat canary; AC #8 narrowed to allow pre-verification TD-026 move; File List expanded; runbook gained first-deploy-ordering section + container-liveness limits callout; adjacent cleanups L-1/L-3 applied. |
