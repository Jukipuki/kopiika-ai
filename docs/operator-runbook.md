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
