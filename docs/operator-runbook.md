# Operator Runbook: Job Status, Pipeline Health & Compliance Audit Queries

Queries run against PostgreSQL via `psql` or any client with read access.
Sections cover the `processing_jobs` table (operational pipeline) and the
`audit_logs` table (GDPR compliance audit trail — see Story 5.6).

## processing_jobs Schema

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary key |
| `user_id` | UUID | Owner (FK to users) |
| `upload_id` | UUID | Source file (FK to uploads) |
| `status` | text | `pending` / `processing` / `completed` / `failed` / `retrying` |
| `step` | text | Current pipeline step: `ingestion` / `categorization` / `profile` / `health-score` / `done` |
| `progress` | int | 0-100 progress percentage |
| `error_code` | text | Standardized error code (e.g., `llm_unavailable`) |
| `error_message` | text | Human-readable error detail |
| `failed_step` | text | Which pipeline step caused the failure |
| `retry_count` | int | Number of retry attempts made |
| `max_retries` | int | Max retries allowed (default 3) |
| `is_retryable` | bool | Whether failure can be retried |
| `last_error_at` | timestamp | Most recent error timestamp |
| `started_at` | timestamp | When Celery worker started processing (NULL = still queued) |
| `created_at` | timestamp | When job was created (= upload submission time) |
| `updated_at` | timestamp | Last modification (serves as completion time for done/failed jobs) |
| `result_data` | JSON | Processing results (see `result_data` Structure below) |

### `result_data` Structure

The `result_data` JSON column is populated when a job completes. Keys available:

| Key | Type | Description |
|-----|------|-------------|
| `total_rows` | int | Total rows detected in the uploaded file |
| `parsed_count` | int | Rows successfully parsed |
| `flagged_count` | int | Rows flagged for review |
| `persisted_count` | int | Rows persisted to the database |
| `duplicates_skipped` | int | Duplicate rows skipped |
| `categorization_count` | int | Rows categorized by the AI agent |
| `total_tokens_used` | int | Total LLM tokens consumed |
| `total_ms` | int | Total in-worker processing time (ms) |
| `agent_timings` | object | Per-stage timing breakdown (see below) |

**`agent_timings` sub-keys:**

| Key | Type | Description |
|-----|------|-------------|
| `ingestion_ms` | int | Time spent on CSV parsing and validation |
| `categorization_ms` | int | Time spent on AI transaction categorization |
| `education_ms` | int | Time spent generating teaching feed insights |

### Indexes

| Index | Column(s) | Purpose |
|-------|-----------|---------|
| `idx_processing_jobs_user_id` | `user_id` | User-scoped queries |
| `idx_processing_jobs_status` | `status` | Status-filtered queries |
| `idx_processing_jobs_upload_id` | `upload_id` | Upload-scoped queries |
| `ix_processing_jobs_status_started_at` | `status, started_at` | Performance queries by status + time |
| `ix_processing_jobs_created_at` | `created_at` | Time-range queries without status filter |

### Timestamp Notes

There is no dedicated `completed_at` column. Use `updated_at` as a proxy -- it is updated on every status change, so for `status='completed'` or `status='failed'` jobs, `updated_at` represents the completion time.

- **Queue latency** = `started_at - created_at`
- **Processing duration** = `updated_at - started_at` (for completed jobs)
- **Precise in-worker timing** = `result_data->'total_ms'`

---

## Job Detail Queries (AC #1)

### Full details of a specific job

```sql
SELECT id, user_id, status, step, progress,
       error_code, error_message, failed_step,
       retry_count, started_at, created_at, updated_at,
       result_data
FROM processing_jobs
WHERE id = '<job-uuid>';
```

### All jobs for a user (most recent first)

```sql
SELECT id, status, step, progress, error_code, created_at, updated_at
FROM processing_jobs
WHERE user_id = '<user-uuid>'
ORDER BY created_at DESC
LIMIT 20;
```

---

## Pipeline Health Queries (AC #2)

### Count of jobs by status (snapshot)

```sql
SELECT status, COUNT(*) AS count
FROM processing_jobs
GROUP BY status
ORDER BY count DESC;
```

### Average completion time (last 24 hours)

```sql
SELECT
  AVG(EXTRACT(EPOCH FROM (updated_at - started_at)) * 1000)::int AS avg_completion_ms,
  COUNT(*) AS completed_count
FROM processing_jobs
WHERE status = 'completed'
  AND started_at IS NOT NULL
  AND created_at >= NOW() - INTERVAL '24 hours';
```

### Failure rate (last 24 hours)

```sql
SELECT
  COUNT(*) FILTER (WHERE status = 'completed') AS successes,
  COUNT(*) FILTER (WHERE status = 'failed')    AS failures,
  ROUND(
    100.0 * COUNT(*) FILTER (WHERE status = 'failed')
    / NULLIF(COUNT(*), 0), 1
  ) AS failure_rate_pct
FROM processing_jobs
WHERE created_at >= NOW() - INTERVAL '24 hours';
```

### Stuck jobs (processing > 5 minutes without update)

```sql
SELECT id, user_id, upload_id, step, progress,
       started_at, updated_at,
       EXTRACT(EPOCH FROM (NOW() - updated_at)) / 60 AS minutes_stalled
FROM processing_jobs
WHERE status = 'processing'
  AND updated_at < NOW() - INTERVAL '5 minutes'
ORDER BY updated_at ASC;
```

---

## Performance Metrics (from Story 6.5)

### Average processing time per pipeline stage (last 7 days)

```sql
SELECT
  AVG((result_data->'agent_timings'->>'ingestion_ms')::int)      AS avg_ingestion_ms,
  AVG((result_data->'agent_timings'->>'categorization_ms')::int) AS avg_categorization_ms,
  AVG((result_data->'agent_timings'->>'education_ms')::int)      AS avg_education_ms,
  AVG((result_data->>'total_ms')::int)                           AS avg_total_ms
FROM processing_jobs
WHERE status = 'completed'
  AND started_at >= NOW() - INTERVAL '7 days';
```

### p95 total processing time (last 24 hours)

```sql
SELECT PERCENTILE_CONT(0.95)
       WITHIN GROUP (ORDER BY (result_data->>'total_ms')::int) AS p95_ms
FROM processing_jobs
WHERE status = 'completed'
  AND started_at >= NOW() - INTERVAL '24 hours';
```

### Success/failure rate by day (last 30 days)

```sql
SELECT
  DATE_TRUNC('day', created_at) AS day,
  COUNT(*) FILTER (WHERE status = 'completed') AS successes,
  COUNT(*) FILTER (WHERE status = 'failed')    AS failures,
  ROUND(100.0 * COUNT(*) FILTER (WHERE status = 'failed') / NULLIF(COUNT(*), 0), 1) AS failure_rate_pct
FROM processing_jobs
WHERE created_at >= NOW() - INTERVAL '30 days'
GROUP BY 1
ORDER BY 1 DESC;
```

### Most common error types (last 30 days)

```sql
SELECT error_code, COUNT(*) AS occurrences
FROM processing_jobs
WHERE status = 'failed'
  AND error_code IS NOT NULL
  AND created_at >= NOW() - INTERVAL '30 days'
GROUP BY error_code
ORDER BY occurrences DESC;
```

### Queue latency (last 24 hours)

```sql
SELECT
  AVG(EXTRACT(EPOCH FROM (started_at - created_at)) * 1000)::int AS avg_queue_latency_ms
FROM processing_jobs
WHERE started_at IS NOT NULL
  AND created_at >= NOW() - INTERVAL '24 hours';
```

---

## Compliance Audit Log Queries (Story 5.6, AC #4)

The `audit_logs` table records every successful financial-data access event for
GDPR accountability. The four indexed filter dimensions are `user_id`, `timestamp`,
`action_type`, and `resource_type`.

### `audit_logs` Schema

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary key |
| `user_id` | varchar(64) | Cognito `sub` for live users; SHA-256 hex digest after account deletion (no FK — records survive user deletion) |
| `timestamp` | timestamp | When the access occurred (UTC) |
| `action_type` | varchar(10) | `read` (GET) / `write` (POST/PUT/PATCH) / `delete` (DELETE) |
| `resource_type` | varchar(50) | `transactions` / `insights` / `profile` / `health_scores` / `uploads` / `user_data` / `user` |
| `resource_id` | varchar(255) | UUID extracted from path tail when present |
| `ip_address` | varchar(45) | IPv4 or IPv6 of the requester |
| `user_agent` | varchar(500) | Browser/client UA string |

### Reconstruct one user's full access history

```sql
SELECT timestamp, action_type, resource_type, resource_id, ip_address
FROM audit_logs
WHERE user_id = '<cognito-sub-or-sha256-hex>'
ORDER BY timestamp DESC;
```

For a deleted user, look up the hash with:
`SELECT encode(digest('<original-cognito-sub>', 'sha256'), 'hex');`
(requires `pgcrypto`; otherwise compute the SHA-256 client-side).

### Filter by date range

```sql
SELECT user_id, timestamp, action_type, resource_type, resource_id
FROM audit_logs
WHERE timestamp >= '2026-04-01'
  AND timestamp <  '2026-05-01'
ORDER BY timestamp DESC;
```

### Filter by action type (e.g., all deletions in last 30 days)

```sql
SELECT user_id, timestamp, resource_type, resource_id, ip_address
FROM audit_logs
WHERE action_type = 'delete'
  AND timestamp >= NOW() - INTERVAL '30 days'
ORDER BY timestamp DESC;
```

### Filter by resource type (e.g., who read a specific user's transactions)

```sql
SELECT user_id, timestamp, action_type, resource_id, ip_address
FROM audit_logs
WHERE resource_type = 'transactions'
  AND timestamp >= NOW() - INTERVAL '7 days'
ORDER BY timestamp DESC;
```

### Combined filter: one user's writes in a date range

```sql
SELECT timestamp, resource_type, resource_id, ip_address, user_agent
FROM audit_logs
WHERE user_id = '<cognito-sub>'
  AND action_type = 'write'
  AND timestamp >= '2026-04-01' AND timestamp < '2026-05-01'
ORDER BY timestamp ASC;
```

### Access volume per resource type (last 24 hours)

```sql
SELECT resource_type, action_type, COUNT(*) AS events
FROM audit_logs
WHERE timestamp >= NOW() - INTERVAL '24 hours'
GROUP BY resource_type, action_type
ORDER BY events DESC;
```

### Notes

- The middleware logs only **successful** (status `< 400`) requests; failed/unauthorized
  attempts are not currently captured (see TD-013).
- Records are **append-only**: there is no application-level deletion. Long-term
  retention enforcement is tracked in TD-014.
- Anonymized rows (post-deletion) keep all columns except `user_id`, which becomes
  the SHA-256 hex of the original Cognito `sub`.

---

## Scheduled Tasks (Celery beat)

Periodic jobs are registered in
[`backend/app/tasks/celery_app.py`](../backend/app/tasks/celery_app.py) via
`celery_app.conf.beat_schedule`. They are published by a dedicated **Celery
beat** process (Story 7.9) running as ECS service `kopiika-${env}-beat` and
consumed by the existing worker service.

| Task | Schedule (UTC) | Source |
|------|----------------|--------|
| `app.tasks.cluster_flagging_tasks.flag_low_quality_clusters` | Daily 02:00 | Story 7.8 |

### Scheduler store

Beat uses Celery's default file-based schedule store (`celerybeat-schedule`)
written inside the Fargate task's ephemeral filesystem. Two implications:

- **Single-replica by design.** The beat ECS service is hardcoded to
  `desired_count = 1`. Two beat replicas connected to the same broker would
  each fire every scheduled task at every cadence. If high-availability beat
  becomes necessary, switch to [`celery-redbeat`](https://github.com/sibson/redbeat)
  (Redis-backed store with leader election) before scaling past one replica.
- **Restarts may re-fire a window.** If the beat container restarts across a
  scheduled instant, the file-based store does not remember "02:00 UTC already
  ran" — the next start can re-publish that cadence. Acceptable for today's
  single daily idempotent job; revisit when a schedule entry becomes expensive
  or non-idempotent.

### Verifying beat is running

- **ECS console:** find the service `kopiika-${env}-beat` in cluster
  `kopiika-${env}-cluster`. Desired and running counts must both be `1`.
- **CloudWatch logs:** log group `/ecs/kopiika-${env}-beat`, stream prefix
  `beat/`. Within ~30s of task start expect the banner `beat: Starting...`,
  followed by one `Scheduler: Sending due task
  flag-low-quality-rag-clusters-daily` line per UTC day at 02:00.
- **Container liveness:** ECS task definition includes a container-level
  healthcheck that asserts the Celery app still imports
  (`python -c 'from app.tasks.celery_app import celery_app'`, interval 60s,
  retries 3). A failing healthcheck stops the task and ECS replaces it; watch
  for restart churn in the service events tab if the signal escalates.

  **Limits of this healthcheck:** it only catches the "app broken" failure
  class. A beat container whose import succeeds but whose main loop is
  wedged, whose `beat_schedule` is empty, or whose system clock has drifted
  will pass the healthcheck while quietly failing to schedule. The 24-hour
  end-to-end canary (CloudWatch log metric filter + alarm on
  `"Scheduler: Sending due task"` lines) is tracked as **TD-028** in
  `docs/tech-debt.md` and should be added before anything in `beat_schedule`
  becomes business-critical.
- **Ad-hoc manual enqueue (kept for incident re-runs, not routine use):**

  ```bash
  docker compose exec worker \
    celery -A app.tasks.celery_app call app.tasks.cluster_flagging_tasks.flag_low_quality_clusters
  ```

  or from a Python shell against the DB-connected worker image:

  ```python
  from app.tasks.cluster_flagging_tasks import flag_low_quality_clusters
  flag_low_quality_clusters.delay()
  ```

### First-time beat deployment to a fresh environment

The ECS beat task definition pins `image = "${ecr_repository_url}:beat-latest"`.
If the `beat-latest` tag does not yet exist in ECR when Terraform runs,
`aws_ecs_task_definition.beat` creates cleanly but `aws_ecs_service.beat`
fails to start tasks (image pull error), and the `wait-for-service-stability`
step in the deploy workflow will time out.

One-time seeding for a new environment (only needed on the *first* deploy to
an env where no `beat-latest` tag has ever been pushed):

```bash
# From a workstation with AWS creds + ECR push permissions for the target env
aws ecr get-login-password --region eu-central-1 \
  | docker login --username AWS --password-stdin <account>.dkr.ecr.eu-central-1.amazonaws.com
docker build -t <account>.dkr.ecr.eu-central-1.amazonaws.com/kopiika-backend:beat-latest \
  -f backend/Dockerfile.beat backend/
docker push <account>.dkr.ecr.eu-central-1.amazonaws.com/kopiika-backend:beat-latest
# Then run `terraform apply` for the env. Subsequent deploys work via the normal CI pipeline.
```

From the second deploy onward, the GitHub Actions workflow keeps `beat-latest`
current — no manual step needed.

### Inspecting flagged clusters

```sql
SELECT cluster_id, thumbs_down_rate, total_votes, total_down_votes, flagged_at
FROM flagged_topic_clusters
ORDER BY thumbs_down_rate DESC;

SELECT cluster_id, top_reason_chips, sample_card_ids
FROM flagged_topic_clusters
WHERE cluster_id = :category;
```

## Chat Safety Operations (Story 10.9)

Story 10.9 metricifies the `chat.*` structured-log events emitted by the
Epic 10 chat agent (Stories 10.4b – 10.7) into the `Kopiika/Chat`
CloudWatch namespace, plus alarms covering the architecture's observability
table at `_bmad-output/planning-artifacts/architecture.md` §Observability
& Alarms (L1761-L1774). All chat events stream through the App Runner
**application** log group:

```
${LOG_GROUP_NAME} = /aws/apprunner/kopiika-prod-api/<service-id>/application
```

The `<service-id>` is the trailing hex segment of the App Runner service
ARN. Read it once via `aws apprunner describe-service` and substitute
literally into the snippets below before pasting into Logs Insights.

### Metric Inventory

| Metric (Kopiika/Chat) | Source event | Alarm name(s) | Severity |
|---|---|---|---|
| `ChatStreamOpenedCount` | `chat.stream.opened` | (denominator only) | — |
| `ChatStreamFirstTokenLatencyMs` | `chat.stream.first_token` (`ttfb_ms`) | `kopiika-prod-chat-first-token-p95-warn`, `kopiika-prod-chat-first-token-p95-page` | warn / page |
| `ChatStreamCompletedCount` | `chat.stream.completed` | — | — |
| `ChatStreamRefusedCount` | `chat.stream.refused` (any reason) | `kopiika-prod-chat-refusal-rate-warn` | warn |
| `ChatStreamRefusedUngroundedCount` | `chat.stream.refused` (`reason=ungrounded`) | `kopiika-prod-chat-grounding-block-rate-warn`, `kopiika-prod-chat-grounding-block-rate-page` | warn / page |
| `ChatStreamGuardrailIntervenedCount` | `chat.stream.guardrail_intervened` | (Bedrock-Guardrail block-rate alarm pair, see below) | — |
| `ChatStreamGuardrailDetachedCount` | `chat.stream.guardrail_detached` | — | — |
| `ChatStreamFinalizerFailedCount` | `chat.stream.finalizer_failed` | `kopiika-prod-chat-stream-finalizer-failed-sev2` | sev-2 |
| `ChatStreamDisconnectedCount` | `chat.stream.disconnected` | — | — |
| `ChatStreamConsentDriftCount` | `chat.stream.consent_drift` | — | — |
| `ChatInputBlockedCount` | `chat.input.blocked` | — (used in jailbreak triage) | — |
| `ChatCanaryLeakedCount` | `chat.canary.leaked` (any `finalizer_path`) | `kopiika-prod-chat-canary-leaked-sev1` | sev-1 |
| `ChatCanaryLoadFailedCount` | `chat.canary.load_failed` | `kopiika-prod-chat-canary-load-failed-warn` | warn |
| `ChatToolLoopExceededCount` | `chat.tool.loop_exceeded` | — (used in abuse triage) | — |
| `ChatToolAuthorizationFailedCount` | `chat.tool.authorization_failed` | — | — |
| `ChatTurnCompletedCount` | `chat.turn.completed` | — | — |
| `ChatTurnTotalTokensUsed` (dim `UserBucket`) | `chat.turn.completed` (`total_tokens_used`, `user_bucket`) | `kopiika-prod-chat-token-spend-anomaly-warn-{0..f}`, `kopiika-prod-chat-token-spend-anomaly-page-{0..f}` (16 buckets each) | warn / page |
| `ChatCitationCount` | `chat.citations.attached` (`citation_count`; emitted unconditionally with 0 when tools didn't fire) | `kopiika-prod-chat-citation-count-p95-zero` (P95 stat at query time) | warn |
| `ChatSummarizationTriggeredCount` | `chat.summarization.triggered` | — | — |
| `ChatSummarizationFailedCount` | `chat.summarization.failed` | (TD-095 — post-30d audit) | — |
| `AWS/Bedrock` `InvocationsIntervened` / `Invocations` | Bedrock Guardrails | `kopiika-prod-chat-block-rate-warn`, `kopiika-prod-chat-guardrail-block-rate-anomaly` | warn / page |

The `UserBucket` dimension on `ChatTurnTotalTokensUsed` is the first hex
character of `user_id_hash` (16 buckets total) and is emitted as the
precomputed `user_bucket` field on `chat.turn.completed` (CloudWatch
JSON metric filters cannot slice strings). Anomaly attribution is
per-bucket, not per-user; the warn/page alarms are fanned out as 16
resources each (one per bucket) — CloudWatch does not aggregate across
dimensions, so a non-dimensioned alarm would see an empty stream. If
higher resolution is needed, file a follow-up TD widening the bucket
field once active-user count grows.

### Guardrails Violation Triage

Triggered by `kopiika-prod-chat-block-rate-warn` (Bedrock) or by an
elevated `kopiika-prod-chat-grounding-block-rate-warn`.

1. Open the warn alarm in CloudWatch and click through to the Logs
   Insights link below to identify the dominant `reason` value:

   ```
   fields @timestamp, reason, exception_class, correlation_id
   | filter message = "chat.stream.refused"
   | stats count() by reason
   | sort count desc
   ```

2. Sample 3–5 representative `chat.stream.refused` records to inspect
   the prompt patterns:

   ```
   fields @timestamp, correlation_id, reason, exception_class, db_session_id
   | filter message = "chat.stream.refused"
   | sort @timestamp desc
   | limit 5
   ```

3. Decide:
   - **Transient noise** (single dominant `reason`, count returning to
     baseline within one alarm period): note in the on-call log, return
     to monitoring.
   - **Policy tightening** (sustained shift in `reason` mix): file a
     Story 10.2 follow-up TD to retune Bedrock Guardrail thresholds.
   - **Active jailbreak campaign** (rising `chat.input.blocked` rate
     alongside `chat.stream.refused`): escalate to **Jailbreak Incident
     Response** below.

### Jailbreak Incident Response

1. Confirm the suspicion — `chat.input.blocked` rate is elevated
   alongside `chat.stream.refused`:

   ```
   fields @timestamp, message
   | filter message in ["chat.input.blocked", "chat.stream.refused"]
   | stats count() by message, bin(5m)
   ```

2. Pull the affected user-hash set:

   ```
   fields user_id_hash
   | filter message = "chat.input.blocked"
   | stats count() as hits by user_id_hash
   | sort hits desc
   | limit 50
   ```

3. Cross-reference the matched regex family with
   [`backend/app/agents/chat/jailbreak_patterns.yaml`](../backend/app/agents/chat/jailbreak_patterns.yaml).
4. Decide on user-level abuse action via Story 10.11's rate-limit +
   soft-block envelope (60 msgs/hr, 10 concurrent sessions, daily token
   cap).
5. If a **novel** jailbreak pattern (no matching regex), file a Story
   10.4b follow-up TD AND add a 10.8a corpus quarterly-review entry so
   the next red-team baseline catches it.

### Canary Leak Response (sev-1)

Triggered by `kopiika-prod-chat-canary-leaked-sev1` — count > 0 over 5m.
Treat as a security incident.

1. **Page chain**: SNS topic → security on-call (24/7).
2. **Immediate action**: rotate the leaked canary slot per the
   **Canary Rotation Runbook** below. Do this BEFORE any forensic work —
   the slot's value is now in the model's training surface.
3. **Forensic — pull the offending event + recent canary-leak history**:

   ```
   fields @timestamp, correlation_id, db_session_id, canary_slot, finalizer_path, output_char_len
   | filter message = "chat.canary.leaked"
   | sort @timestamp desc
   | limit 50
   ```

4. **Path classification** — check `finalizer_path`:
   - `finalizer_path` absent / false → happy-path leak (model emitted
     the canary in the streaming response). RCA target: the prompt that
     elicited it.
   - `finalizer_path = true` → post-disconnect persistence-time leak
     (different RCA per Story 10.5a AC #2 Step F.1). RCA target: the
     accumulated text path; check whether the leak survived disconnect.
5. If the leak originated from a **tool payload** (cross-reference
   `chat.tool.result` records around the same `correlation_id`),
   evaluate whether the widen-canary-scan path in
   [TD-101](../docs/tech-debt.md#TD-101) needs to be promoted.

### Canary Rotation Runbook

Manual-rotation steps. The chat backend hydrates canary slots
process-locally from the `kopiika-ai/<env>/chat-canaries` Secrets
Manager secret, schema:

```json
{
  "slots": [
    { "id": "<slot>", "value": "<token>", "version_id": "<uuid>" }
  ]
}
```

Steps:

1. Generate replacement canary value(s). For routine rotation do all
   slots; for an active leak rotate **at minimum** the leaked slot ID
   plus one neighbour. The token must be high-entropy and contain no
   English-word fragments.
2. Update the secret in place — bump `version_id` (UUID v4) at the same
   time so the canary loader detects the change:

   ```bash
   aws secretsmanager update-secret \
     --region eu-central-1 \
     --secret-id kopiika-ai/prod/chat-canaries \
     --secret-string '{"slots":[{"id":"a","value":"<new-token>","version_id":"<new-uuid>"}, ...]}'
   ```

3. Trigger an App Runner restart so the new secret hydrates (the canary
   loader is process-local — running pods continue to use the cached
   prior value until restart):

   ```bash
   aws apprunner start-deployment \
     --region eu-central-1 \
     --service-arn <kopiika-prod-api service ARN>
   ```

4. Verify uptake — `ChatCanaryLoadFailedCount` must remain 0 for the
   next 5 minutes. Failures here indicate a malformed secret or
   missing IAM grant; roll back via the previous Secrets Manager
   version (`aws secretsmanager restore-secret --secret-id ...
   --version-id <prior version>`) before chat traffic resumes.

NOTE: the canary value MUST be set in prod before chat traffic is
served. The dev-fallback canary baked into
[`backend/app/agents/chat/canaries.py`](../backend/app/agents/chat/canaries.py)
is for local development only.

### Chat Abuse Handling

1. Check the suspect user's recent `chat.tool.loop_exceeded` count and
   per-user-bucket token-spend band:

   ```
   fields @timestamp, db_session_id, user_id_hash
   | filter message = "chat.tool.loop_exceeded"
   | stats count() as hits by user_id_hash
   | sort hits desc
   ```

2. Cross-reference with Story 10.11's rate-limit envelope (60 msgs/hr,
   10 concurrent sessions, daily token cap) — the soft-block path is
   automatic and will already be quietly enforcing.
3. Decide between automatic soft-block (10.11 already handles it
   transparently) or manual account-level action via the user-admin
   tooling in `backend/scripts/`.

### CloudWatch Logs Insights Snippets

Set `${LOG_GROUP_NAME}` to the App Runner application log group at the
top of your Insights query session, then paste the snippets below
verbatim.

**(a) Refusal reasons distribution over the last 1h**:

```
fields @timestamp, reason
| filter message = "chat.stream.refused"
| stats count() by reason
| sort count desc
```

Supports: `kopiika-prod-chat-refusal-rate-warn`,
`kopiika-prod-chat-grounding-block-rate-warn`.

**(b) Per-user-bucket top 20 token-spend over the last 24h**:

```
fields user_id_hash, total_tokens_used
| filter message = "chat.turn.completed"
| stats sum(total_tokens_used) as spend by user_id_hash
| sort spend desc
| limit 20
```

Supports: `kopiika-prod-chat-token-spend-anomaly-warn`,
`kopiika-prod-chat-token-spend-anomaly-page`.

**(c) Canary-leak forensic for a specific `correlation_id`**:

```
fields @timestamp, message, correlation_id, canary_slot, finalizer_path, output_char_len, output_prefix_hash
| filter correlation_id = "<paste correlation id here>"
| filter message in ["chat.canary.leaked", "chat.stream.refused", "chat.turn.completed", "chat.tool.result"]
| sort @timestamp asc
```

Supports: `kopiika-prod-chat-canary-leaked-sev1`.

**(d) Finalizer-failed event chain for a specific session**:

```
fields @timestamp, message, correlation_id, error_class, error_message, accumulated_char_len
| filter db_session_id = "<paste db session id here>"
| filter message like /chat\.stream\./
| sort @timestamp asc
```

Supports: `kopiika-prod-chat-stream-finalizer-failed-sev2`.

**(e) Citation-count P50/P95 over the last 7d**:

```
fields @timestamp, citation_count, truncated, contract_version
| filter message = "chat.citations.attached"
| stats pct(citation_count, 50) as p50, pct(citation_count, 95) as p95, count() as turns by bin(1d)
```

Supports: `kopiika-prod-chat-citation-count-p95-zero`.

### Pre-Merge Smoke Test

Each metric filter pattern is verified before merge by running
`infra/terraform/modules/app-runner/test_chat_metric_filters.sh` against
representative log lines captured from the dev environment. Run with
`AWS_PROFILE=personal` (account 573562677570, eu-central-1):

```bash
AWS_PROFILE=personal \
  bash infra/terraform/modules/app-runner/test_chat_metric_filters.sh
```

Each block prints the matched events; an empty match list for any
filter is a regression — investigate before merging.

---

## Overriding a detected bank format mapping (Story 11.7)

The AI-assisted schema-detection pipeline caches one row per distinct statement
header shape in `bank_format_registry`, keyed by a SHA-256 fingerprint of the
canonical header. When an operator spots a misdetection (rows rejected by
validation, column mismatches in the SSE partial-import response, or a
`parser.schema_detection` log event with `suspect_detection: true`), the fix
path is a direct DB update — no UI exists as of Story 11.7.

### 1. Inspect recent registry rows

```sql
SELECT id,
       header_fingerprint,
       detected_bank_hint,
       detection_confidence,
       use_count,
       last_used_at
FROM bank_format_registry
ORDER BY last_used_at DESC
LIMIT 50;
```

To find the fingerprint for a specific problem upload, grep for
`parser.schema_detection` events in the worker logs with the matching
`upload_id`; the `fingerprint` field is logged on every invocation.

### 2. View the existing mapping

```sql
SELECT jsonb_pretty(detected_mapping) AS detected,
       jsonb_pretty(override_mapping) AS override,
       sample_header
FROM bank_format_registry
WHERE header_fingerprint = '<hash>';
```

### 3. Apply the override

The `override_mapping` JSON must match the shape from tech spec §2.4 — keys
`date_column`, `date_format`, `amount_column`, `amount_sign_convention`,
`description_column`, `currency_column`, `mcc_column`, `balance_column`,
`delimiter`, `encoding_hint`. Counterparty keys are optional (persisted
verbatim but not yet consumed by the categorization pipeline — TD-049).

```sql
UPDATE bank_format_registry
SET override_mapping = '{
  "date_column": "Дата",
  "date_format": "%d.%m.%Y",
  "amount_column": "Сума",
  "amount_sign_convention": "negative_is_outflow",
  "description_column": "Призначення",
  "currency_column": "Валюта",
  "mcc_column": null,
  "balance_column": null,
  "delimiter": ";",
  "encoding_hint": "windows-1251"
}'::jsonb,
    updated_at = now()
WHERE header_fingerprint = '<hash>';
```

### 4. Validate the override

Re-upload the problem statement and confirm:

- The SSE partial-import payload has `schemaDetectionSource: "cached_override"`.
- The transaction count matches the number of data rows in the CSV.
- Spot-check a few rows: the date, amount sign, description, and currency
  appear correctly in the transactions list for that upload.
- No `parser.schema_detection` event with `suspect_detection: true` fires for
  the new upload.

### Warnings

- **Mapping shape drift**: overrides must include every required key. A
  missing `amount_sign_convention` or `date_format` will cause the parser to
  reject rows wholesale. Run step 2 first to copy the detected shape.
- **Column names must exist verbatim in the CSV header** — use the
  `sample_header` column as a reference. Trailing whitespace is stripped by
  the parser, but other transformations (case, NFKC) are not; match exactly.
- **Do not delete registry rows** unless you are certain the fingerprint will
  never recur — dropping a row forces a fresh LLM call on the next upload of
  the same format.


## Rotating the IBAN encryption KMS key (Story 11.10)

`user_iban_registry` stores application-level AES-GCM ciphertext; each row's
data encryption key (DEK) is generated per-call by the KMS CMK named in
`settings.KMS_IBAN_KEY_ARN`. Rotation is an operator-initiated event — not
cron-automated — because it requires a maintenance window and a row-level
lock sweep.

### When to rotate

- Scheduled annual key rotation per compliance policy.
- After a suspected key-material compromise (treat as emergency).
- When migrating an environment from the local-Fernet dev fallback to KMS
  (each row carries a prefix byte that routes decryption, so the script
  transparently reads Fernet rows and writes KMS rows).

### How to rotate

1. Create a new CMK version in AWS KMS or point `KMS_IBAN_KEY_ARN` at the
   new CMK ARN. KMS resolves historical key versions on decrypt
   automatically — no downtime on reads during rotation.
2. Coordinate a short maintenance window (row-level locks acquired during
   the UPDATE). Expected runtime: ~1s per 500 rows on a well-connected
   worker; single-shot even for typical user bases.
3. Run a dry-run first to confirm row counts:
   ```bash
   python scripts/rotate_iban_encryption.py --dry-run
   ```
4. Execute the rotation:
   ```bash
   python scripts/rotate_iban_encryption.py
   ```
5. Verify: `SELECT COUNT(*) FROM user_iban_registry;` matches the row count
   the script reported. Spot-check a row by calling
   `UserIbanRegistryService.is_user_iban(user_id, known_plaintext)` — it
   must still return True after rotation (fingerprint is key-independent).

### Warnings

- The script takes a row lock during re-encrypt; writes during the window
  are blocked. Keep the window short.
- Do NOT delete the old CMK version until the script reports success and a
  post-rotation verification pass completes. KMS retains old versions for
  decrypt; deleting too early breaks old ciphertexts that weren't yet
  re-encrypted (shouldn't happen after a clean run, but defense in depth).

## Ingestion & Categorization Observability (Story 11.9)

Five structured log events drive the ingestion/categorization dashboards:

| Event | Source | Level | Purpose |
|-------|--------|-------|---------|
| `categorization.confidence_tier` | `app/agents/categorization/node.py` | INFO | Tier decision (`soft-flag` / `queue`) per txn |
| `categorization.review_queue_insert` | `app/tasks/processing_tasks.py` | INFO | Post-commit row into the review queue |
| `categorization.kind_mismatch` | `app/tasks/processing_tasks.py` | WARNING | LLM returned an invalid (kind, category) pair; fallback applied |
| `parser.schema_detection` | `app/services/schema_detection.py` | INFO | Schema resolution outcome (cache / llm / fallback_generic) |
| `parser.validation_rejected` | `app/services/parser_service.py` | INFO | Single row failed post-parse validation |
| `parser.mojibake_detected` | `app/services/parser_service.py` + task aggregate in `processing_tasks.py` | WARNING | Replacement-char density over threshold |

All events land in the worker log group `/ecs/kopiika-<env>-worker`. The
following "panels" are Insights queries — paste into the CloudWatch console
after selecting the worker log group.

> **Note on the Grafana reference in epic docs.** Epic 11's text mentions a
> "Grafana dashboard". No Grafana instance is deployed in this infrastructure
> (see `infra/terraform/modules/` — no grafana/prometheus module). The
> canonical substrate is CloudWatch Insights + metric-filter alarms. If
> Grafana is adopted later, the queries below port 1-for-1.

### Panel 1 — Categorization confidence distribution (24h)

```
fields @timestamp, tier, tx_id
| filter message = "categorization.confidence_tier"
| stats count(*) as n by tier
| sort n desc
```

Read: the paired alarm fires when `(queue + soft-flag) / total > 50%` over
24h (see Alarms section below). If you see the distribution drifting toward
that threshold, investigate LLM drift early — re-run the golden-set harness
(see Panel 2).

### Panel 2 — Golden-set accuracy trend

There is no CloudWatch query for this. The golden-set harness runs in CI,
not in the worker; each run writes a JSON artifact under
`backend/tests/fixtures/categorization_golden_set/runs/<timestamp>.json`.
Inspect the last 10 runs' artifacts in GitHub Actions (or locally via
`ls backend/tests/fixtures/categorization_golden_set/runs/ | tail -10`).
The harness source is [test_golden_set.py](../backend/tests/agents/categorization/test_golden_set.py).

### Panel 3 — Unknown-format detection rate + cache hit rate

```
fields @timestamp, source, detection_confidence, latency_ms
| filter message = "parser.schema_detection"
| stats count(*) as n by source
| sort n desc
```

`source` values: `cached_detected`, `cached_override`, `llm_detected`,
`fallback_generic`. Falling `cache*` share with rising `llm_detected` means
new formats are being seen and cached; rising `fallback_generic` means
detection is failing and needs investigation.

### Panel 4 — Validation rejection rate by reason

```
fields @timestamp, reason, row_number, upload_id
| filter message = "parser.validation_rejected"
| stats count(*) as rejected by reason
| sort rejected desc
```

### Panel 5 — Uploads with mojibake detected (last 7d)

```
fields @timestamp, upload_id, encoding, replacement_char_rate, transaction_count
| filter message = "parser.mojibake_detected"
| stats count(*) as n by upload_id, encoding
| sort n desc
```

A true per-upload rate would require joining against `pipeline_completed`;
the list form above is the pragmatic version.

### Operational playbooks

**(a) Reading the confidence distribution panel.**
The three tier thresholds are defined in [`backend/app/core/config.py`](../backend/app/core/config.py)
as `CATEGORIZATION_AUTO_APPLY_THRESHOLD` and `CATEGORIZATION_SOFT_FLAG_THRESHOLD`.
Always read the deployed config for current values — thresholds may be
tuned without a runbook update. Rough intuition as of Story 11.8:
≥0.85 → auto-apply (no event), 0.60–0.84 → soft-flag event, <0.60 → queue event.

**(b) Inspecting `bank_format_registry` and applying overrides.**
See the existing section [Overriding a detected bank format mapping (Story 11.7)](#overriding-a-detected-bank-format-mapping-story-117)
for the `psql` workflow. Don't duplicate the procedure here.

**(c) Triaging a high validation-rejection alarm.**
1. Confirm the alarm firing window and count in CloudWatch Alarms.
2. Run Panel 4 scoped to the alarm window (add `| filter @timestamp > X`).
3. If one `reason` dominates, join to `FlaggedImportRow` in Postgres:
   ```sql
   select row_number, reason, raw_data
   from flagged_import_row
   where upload_id = '<id>'
   order by row_number
   limit 50;
   ```
4. If reasons are widely distributed across uploads, suspect a pipeline
   regression — bisect recent deploys / rollbacks.

### Alarms

Two CloudWatch alarms are provisioned by `infra/terraform/modules/ecs/observability.tf`:

- `{project}-{env}-categorization-low-confidence-median` — fires when
  (queue+soft-flag) / total > 0.5 over 24h. Proxy for median confidence
  < 0.85; see TD-050 for the EMF-based follow-on.
- `{project}-{env}-validation-rejection-rate-high` — fires when
  rejected/total > 0.15 over 24h.

Both gated on `var.enable_observability_alarms` (false in dev, true in
staging/prod). Neither has an SNS action wired by default; set
`var.observability_sns_topic_arn` when the notification pipeline is ready.
