# Story 7.8: RAG Topic Cluster Auto-Flagging

Status: in-progress

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **developer**,
I want the system to automatically flag RAG topic clusters with high thumbs-down rates,
So that I can prioritize corpus quality improvements without manually reviewing all feedback.

## Acceptance Criteria

1. **Given** card_feedback votes have accumulated on cards within a topic cluster **When** a cluster reaches a minimum of 10 votes **Then** the system evaluates the thumbs-down rate for that cluster

2. **Given** a topic cluster has >30% thumbs-down rate with at least 10 votes **When** the auto-flagging check runs **Then** the cluster is flagged for review in a `flagged_topic_clusters` record with: cluster_id, thumbs_down_rate, total_votes, flagged_at

3. **Given** the auto-flagging logic **When** it runs **Then** it executes as a periodic batch job (Celery beat scheduled task) running daily at 02:00 UTC — NOT on every individual vote

4. **Given** a flagged topic cluster **When** the developer queries flagged clusters **Then** they can see: cluster identifier (category name), current thumbs-down rate, total votes, most common reason_chip values, and sample card IDs for review

5. **Given** the minimum sample size of 10 votes **When** a cluster has fewer than 10 votes **Then** it is never flagged regardless of thumbs-down rate, preventing false positives from small samples

## Tasks / Subtasks

- [x] Task 1: Backend — New `FlaggedTopicCluster` model and Alembic migration (AC: #2, #4)
  - [x] 1.1 Create `backend/app/models/flagged_topic_cluster.py` with `FlaggedTopicCluster` SQLModel
  - [x] 1.2 Add `FlaggedTopicCluster` to `backend/app/models/__init__.py` exports
  - [x] 1.3 Generate Alembic migration `s5t6u7v8w9x0_add_flagged_topic_clusters_table.py` (down_revision = `r4s5t6u7v8w9`)
  - [x] 1.4 Apply migration: `alembic upgrade head` — verified columns, unique constraint `uq_flagged_cluster_id`, and index `ix_flagged_topic_clusters_cluster_id` via `information_schema`

- [x] Task 2: Backend — Celery task `flag_low_quality_clusters` (AC: #1, #2, #3, #4, #5)
  - [x] 2.1 Create `backend/app/tasks/cluster_flagging_tasks.py`
  - [x] 2.2 Implement `flag_low_quality_clusters()` — Phase 1 discover, Phase 2a chip frequency + 2b sample IDs, Phase 3 dialect-aware upsert
  - [x] 2.3 Task decorator `@celery_app.task(bind=False, max_retries=1, acks_late=True)`

- [x] Task 3: Backend — Register task and configure Celery beat schedule (AC: #3)
  - [x] 3.1 Updated `backend/app/tasks/celery_app.py` with `crontab` import, `include` expanded, `beat_schedule` added (daily 02:00 UTC)

- [x] Task 4: Backend — Tests (AC: #1–#5)
  - [x] 4.1 Create `backend/tests/test_cluster_flagging_task.py`
  - [x] 4.2 `TestFlagLowQualityClusters` — all 9 scenarios implemented and passing

## Dev Notes

### Architecture Overview

Story 7.8 adds a **Layer 3 (Phase 2) data quality tool** — a purely backend, developer-facing batch job that surfaces low-quality RAG topic clusters so corpus authors can prioritize improvements.

**What is a "topic cluster"?**
The codebase does not persist which RAG doc IDs contributed to each insight. The `Insight` model (`backend/app/models/insight.py`) stores a `category` field (e.g., `"food"`, `"transport"`, `"subscriptions"`) assigned by the Education Agent at generation time. This `category` is the natural cluster identifier — it groups insights about the same financial domain and maps to the RAG corpus documents covering that domain.

**No user-facing changes**: This story adds no frontend code and no new API endpoints. Developers query `flagged_topic_clusters` directly via SQL or DB client.

**No removal of flags**: Once a cluster is flagged, it stays flagged (even if thumbs-down rate later improves). The `last_evaluated_at` field reflects the latest stats. Manual cleanup is out of scope for this story.

### Backend: `FlaggedTopicCluster` Model

```python
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, Column, UniqueConstraint
from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class FlaggedTopicCluster(SQLModel, table=True):
    __tablename__ = "flagged_topic_clusters"
    __table_args__ = (
        UniqueConstraint("cluster_id", name="uq_flagged_cluster_id"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    cluster_id: str = Field(max_length=100, index=True)  # insights.category value
    thumbs_down_rate: float  # e.g. 0.40 = 40%
    total_votes: int
    total_down_votes: int
    top_reason_chips: dict[str, Any] = Field(sa_column=Column(JSON), default_factory=dict)
    sample_card_ids: list[str] = Field(sa_column=Column(JSON), default_factory=list)
    flagged_at: datetime = Field(default_factory=_utcnow)
    last_evaluated_at: datetime = Field(default_factory=_utcnow)
```

### Backend: Core Flagging SQL

**Phase 1 — Discover qualifying clusters:**
```sql
SELECT
    i.category,
    COUNT(cf.id) AS total_votes,
    COUNT(cf.id) FILTER (WHERE cf.vote = 'down') AS down_votes
FROM card_feedback cf
JOIN insights i ON cf.card_id = i.id
WHERE cf.vote IS NOT NULL
GROUP BY i.category
HAVING COUNT(cf.id) >= 10
```
Then filter in Python: `if down_votes / total_votes > 0.30`.

**Phase 2a — Reason chip frequency:**
```sql
SELECT cf.reason_chip, COUNT(*) AS cnt
FROM card_feedback cf
JOIN insights i ON cf.card_id = i.id
WHERE i.category = :category
  AND cf.vote = 'down'
  AND cf.reason_chip IS NOT NULL
GROUP BY cf.reason_chip
ORDER BY cnt DESC
LIMIT 5
```

**Phase 2b — Sample card IDs:**
```sql
SELECT DISTINCT cf.card_id::text
FROM card_feedback cf
JOIN insights i ON cf.card_id = i.id
WHERE i.category = :category AND cf.vote = 'down'
LIMIT 5
```

**Phase 3 — PostgreSQL upsert pattern:**
```python
from sqlalchemy.dialects.postgresql import insert

stmt = insert(FlaggedTopicCluster).values(
    id=uuid.uuid4(),
    cluster_id=category,
    thumbs_down_rate=down_rate,
    total_votes=total_votes,
    total_down_votes=down_votes,
    top_reason_chips=reason_chips,
    sample_card_ids=sample_card_ids,
    flagged_at=_utcnow(),
    last_evaluated_at=_utcnow(),
)
stmt = stmt.on_conflict_do_update(
    index_elements=["cluster_id"],
    set_={
        "thumbs_down_rate": stmt.excluded.thumbs_down_rate,
        "total_votes": stmt.excluded.total_votes,
        "total_down_votes": stmt.excluded.total_down_votes,
        "top_reason_chips": stmt.excluded.top_reason_chips,
        "sample_card_ids": stmt.excluded.sample_card_ids,
        "last_evaluated_at": stmt.excluded.last_evaluated_at,
        # flagged_at intentionally NOT updated — preserves original flag date
    },
)
session.execute(stmt)
session.commit()
```

> **Important**: `sqlalchemy.dialects.postgresql.insert` requires a real PostgreSQL connection. For tests using SQLite, mock this at the task level or use the `unittest.mock.patch` approach — see test approach below.

### Backend: Celery Task File

```python
# backend/app/tasks/cluster_flagging_tasks.py
import logging
import uuid

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert

from app.core.database import get_sync_session
from app.models.flagged_topic_cluster import FlaggedTopicCluster
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)

MIN_VOTES = 10
DOWN_RATE_THRESHOLD = 0.30  # strictly greater than


def _utcnow():
    from datetime import UTC, datetime
    return datetime.now(UTC).replace(tzinfo=None)


@celery_app.task(bind=False, max_retries=1, acks_late=True)
def flag_low_quality_clusters() -> dict:
    """Scan card_feedback for RAG topic clusters with high thumbs-down rates and flag them."""
    with get_sync_session() as session:
        # Phase 1: find clusters meeting minimum votes
        rows = session.execute(text("""
            SELECT
                i.category,
                COUNT(cf.id) AS total_votes,
                COUNT(cf.id) FILTER (WHERE cf.vote = 'down') AS down_votes
            FROM card_feedback cf
            JOIN insights i ON cf.card_id = i.id
            WHERE cf.vote IS NOT NULL
            GROUP BY i.category
            HAVING COUNT(cf.id) >= :min_votes
        """), {"min_votes": MIN_VOTES}).fetchall()

        clusters_evaluated = 0
        clusters_flagged = 0

        for row in rows:
            category = row.category
            total_votes = row.total_votes
            down_votes = row.down_votes
            clusters_evaluated += 1

            down_rate = down_votes / total_votes
            if down_rate <= DOWN_RATE_THRESHOLD:
                continue

            # Phase 2a: reason chip frequency
            chip_rows = session.execute(text("""
                SELECT cf.reason_chip, COUNT(*) AS cnt
                FROM card_feedback cf
                JOIN insights i ON cf.card_id = i.id
                WHERE i.category = :cat AND cf.vote = 'down' AND cf.reason_chip IS NOT NULL
                GROUP BY cf.reason_chip
                ORDER BY cnt DESC
                LIMIT 5
            """), {"cat": category}).fetchall()
            reason_chips = {r.reason_chip: r.cnt for r in chip_rows}

            # Phase 2b: sample card IDs
            card_rows = session.execute(text("""
                SELECT DISTINCT cf.card_id::text
                FROM card_feedback cf
                JOIN insights i ON cf.card_id = i.id
                WHERE i.category = :cat AND cf.vote = 'down'
                LIMIT 5
            """), {"cat": category}).fetchall()
            sample_card_ids = [r[0] for r in card_rows]

            # Phase 3: upsert
            stmt = insert(FlaggedTopicCluster).values(
                id=uuid.uuid4(),
                cluster_id=category,
                thumbs_down_rate=round(down_rate, 4),
                total_votes=total_votes,
                total_down_votes=down_votes,
                top_reason_chips=reason_chips,
                sample_card_ids=sample_card_ids,
                flagged_at=_utcnow(),
                last_evaluated_at=_utcnow(),
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=["cluster_id"],
                set_={
                    "thumbs_down_rate": stmt.excluded.thumbs_down_rate,
                    "total_votes": stmt.excluded.total_votes,
                    "total_down_votes": stmt.excluded.total_down_votes,
                    "top_reason_chips": stmt.excluded.top_reason_chips,
                    "sample_card_ids": stmt.excluded.sample_card_ids,
                    "last_evaluated_at": stmt.excluded.last_evaluated_at,
                },
            )
            session.execute(stmt)
            clusters_flagged += 1

        session.commit()

    logger.info(
        "rag_cluster_flagging_completed",
        extra={"clusters_evaluated": clusters_evaluated, "clusters_flagged": clusters_flagged},
    )
    return {"clusters_evaluated": clusters_evaluated, "clusters_flagged": clusters_flagged}
```

### Backend: celery_app.py Changes

Two additions to `backend/app/tasks/celery_app.py`:

```python
from celery.schedules import crontab

# Change `include` to include new task module:
celery_app.conf.update(include=[
    "app.tasks.processing_tasks",
    "app.tasks.cluster_flagging_tasks",
])

# Add beat schedule after the existing conf.update blocks:
celery_app.conf.beat_schedule = {
    "flag-low-quality-rag-clusters-daily": {
        "task": "app.tasks.cluster_flagging_tasks.flag_low_quality_clusters",
        "schedule": crontab(hour=2, minute=0),  # daily at 02:00 UTC
    },
}
```

### Backend: Alembic Migration

`down_revision` must be `r4s5t6u7v8w9` (the `add_feedback_responses_table` migration from Story 7.7).

The migration must use `sa.JSON()` for `top_reason_chips` and `sample_card_ids` columns, not `JSONB` (SQLModel's `JSON` type maps to `jsonb` in Postgres but `sa.JSON()` is cross-dialect for tests).

### Backend: Test Approach

The test file must handle two constraints:
1. `sqlalchemy.dialects.postgresql.insert` is PostgreSQL-specific — SQLite (used in tests) supports only `INSERT OR REPLACE`
2. The Celery task uses `get_sync_session()` which requires a real DB

**Recommended approach**: Test the flagging logic through a service function extracted from the task body, not the task directly. OR use `patch("app.tasks.cluster_flagging_tasks.insert")` to swap the PostgreSQL `insert` with a standard SQLModel session `merge()` approach in tests.

Alternative approach (simpler): Use raw `session.merge()` or a helper that wraps the upsert in a try/except for cross-dialect compatibility. In tests, pre-insert the `FlaggedTopicCluster` rows and verify updates happen correctly.

**Test fixtures**: Follow the pattern from `test_milestone_feedback_api.py` — use `client` + `auth_headers` fixtures. For the flagging task, call the task function directly (not via Celery worker) and verify DB state after.

```python
# Example test
def test_cluster_flagged_above_threshold(db_session, test_user, test_insight):
    # Create 10 votes: 4 down, 6 up on same insight category
    for i in range(4):
        db_session.add(CardFeedback(user_id=uuid.uuid4(), card_id=test_insight.id,
                                    card_type="insight", vote="down",
                                    reason_chip="not_relevant", feedback_source="card_vote"))
    for i in range(6):
        db_session.add(CardFeedback(user_id=uuid.uuid4(), card_id=test_insight.id,
                                    card_type="insight", vote="up", feedback_source="card_vote"))
    db_session.commit()
    
    result = flag_low_quality_clusters()
    
    assert result["clusters_flagged"] == 1
    flagged = db_session.exec(select(FlaggedTopicCluster)
        .where(FlaggedTopicCluster.cluster_id == test_insight.category)).first()
    assert flagged is not None
    assert flagged.thumbs_down_rate == pytest.approx(0.4)
    assert flagged.total_votes == 10
```

### Developer Query Examples

Once the task runs, developers can query the flagged clusters directly:

```sql
-- List all flagged clusters sorted by severity
SELECT cluster_id, thumbs_down_rate, total_votes, total_down_votes, flagged_at
FROM flagged_topic_clusters
ORDER BY thumbs_down_rate DESC;

-- Inspect reason chips for a specific cluster
SELECT top_reason_chips FROM flagged_topic_clusters WHERE cluster_id = 'food';

-- Get sample card IDs for review
SELECT sample_card_ids FROM flagged_topic_clusters WHERE cluster_id = 'transport';

-- Then inspect the actual insight content:
SELECT id, headline, key_metric, category FROM insights WHERE id = ANY(:card_ids::uuid[]);
```

### Project Structure Notes

```
backend/
├── app/models/
│   └── flagged_topic_cluster.py       ← NEW: FlaggedTopicCluster SQLModel
├── app/models/__init__.py             ← MODIFIED: export FlaggedTopicCluster
├── app/tasks/
│   ├── celery_app.py                  ← MODIFIED: add beat_schedule + include cluster_flagging_tasks
│   └── cluster_flagging_tasks.py      ← NEW: flag_low_quality_clusters Celery task
├── alembic/versions/
│   └── <hash>_add_flagged_topic_clusters_table.py  ← NEW: migration (down_rev: r4s5t6u7v8w9)
tests/
└── test_cluster_flagging_task.py      ← NEW: 9 tests
```

**No frontend files touched.**

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story 7.8] — User story, all 5 acceptance criteria, `flagged_topic_clusters` table schema, FR55
- [Source: _bmad-output/planning-artifacts/epics.md#FR55] — "System can auto-flag RAG topic clusters with >30% thumbs-down rate when minimum of 10 votes has been reached on the cluster"
- [Source: backend/app/models/feedback.py] — `CardFeedback` model: `vote` field ('up'/'down'), `reason_chip`, `card_id` FK, `feedback_source` field to distinguish votes from reports
- [Source: backend/app/models/insight.py] — `Insight` model: `category` field is the cluster identifier
- [Source: backend/app/models/embedding.py] — `DocumentEmbedding.doc_id` pattern (RAG documents); insights do NOT store doc_id — category is the only cluster signal available
- [Source: backend/app/tasks/celery_app.py] — Celery app setup; `celery_app.conf.update(include=[...])` pattern; no beat schedule exists yet
- [Source: backend/app/tasks/processing_tasks.py] — Celery task pattern: `@celery_app.task(bind=True, max_retries=3, acks_late=True)`, `get_sync_session()` usage, `logger.info(...)` with `extra={}` context
- [Source: backend/app/models/feedback_response.py] — UniqueConstraint pattern on SQLModel table
- [Source: backend/alembic/versions/r4s5t6u7v8w9_add_feedback_responses_table.py] — Latest migration; `down_revision = "r4s5t6u7v8w9"` for new migration
- [Source: _bmad-output/implementation-artifacts/7-7-milestone-feedback-cards-in-the-teaching-feed.md] — Test baseline: backend 557 passing, frontend 468 passing (49 files) before this story

## Dev Agent Record

### Agent Model Used

claude-opus-4-7 (1M context)

### Debug Log References

- Initial `test_sample_card_ids_captured` failed because SQLite returns UUIDs as 32-char hex without hyphens while PostgreSQL returns hyphenated form. Fixed by normalizing via `str(uuid.UUID(str(r.card_id)))` in the task so output is deterministic across dialects.

### Completion Notes List

- `FlaggedTopicCluster` model uses `sa.JSON()` (cross-dialect) for `top_reason_chips` and `sample_card_ids`, mapping to `json` on Postgres and JSON text on SQLite.
- Added a `_dialect_insert(session)` helper in the task that picks `postgresql.insert` in production and `sqlite.insert` in tests; both support `on_conflict_do_update` with the same API, avoiding the need to mock the upsert.
- Migration `s5t6u7v8w9x0` chains off `r4s5t6u7v8w9` (Story 7.7 feedback_responses). Verified against dev Postgres: columns, unique constraint, and `cluster_id` index all created.
- Beat schedule registered as `flag-low-quality-rag-clusters-daily` → `crontab(hour=2, minute=0)` (daily 02:00 UTC).
- Threshold semantics: strictly greater than 30% (exactly 30% is not flagged) and strictly ≥ 10 votes. Issue reports (`vote IS NULL`) excluded via `WHERE cf.vote IS NOT NULL` in Phase 1 SQL.
- Full backend suite: 566 tests passing (557 baseline + 9 new). Ruff check passed on all new/modified files.

### Change Log

| Date       | Change                                                                                    |
|------------|-------------------------------------------------------------------------------------------|
| 2026-04-17 | Added `FlaggedTopicCluster` model and `flagged_topic_clusters` table (migration `s5t6u7v8w9x0`). |
| 2026-04-17 | Added `flag_low_quality_clusters` Celery task and Celery beat schedule (daily 02:00 UTC).       |
| 2026-04-17 | Added 9 tests covering thresholds, enrichment, upsert behaviour, and issue-report exclusion.     |
| 2026-04-17 | Version bumped from 1.13.0 to 1.14.0 per story completion.                                       |
| 2026-04-17 | Code review fixes M-1..M-4 (deterministic ordering, cluster_id truncation, per-cluster savepoint); +3 tests. |
| 2026-04-17 | H-1 (Celery beat undeployed) promoted to [TD-026](../../docs/tech-debt.md) + runbook note.        |

### File List

- `backend/app/models/flagged_topic_cluster.py` (new)
- `backend/app/models/__init__.py` (modified — export `FlaggedTopicCluster`)
- `backend/alembic/versions/s5t6u7v8w9x0_add_flagged_topic_clusters_table.py` (new)
- `backend/app/tasks/cluster_flagging_tasks.py` (new)
- `backend/app/tasks/celery_app.py` (modified — beat schedule + task include)
- `backend/tests/test_cluster_flagging_task.py` (new, updated in review — +3 tests)
- `VERSION` (modified — 1.13.0 → 1.14.0)
- `_bmad-output/implementation-artifacts/sprint-status.yaml` (modified — story status)
- `_bmad-output/implementation-artifacts/7-8-rag-topic-cluster-auto-flagging.md` (modified — status, Dev Agent Record, Code Review)
- `docs/tech-debt.md` (modified in review — added TD-026 for beat deployment gap)
- `docs/operator-runbook.md` (modified in review — added Scheduled Tasks section)

## Code Review (2026-04-17)

Reviewer: Claude (adversarial code review). 8 findings total: 1 HIGH, 4 MEDIUM, 3 LOW.

### Fixed in this story

- **M-1** — `sample_card_ids` was non-deterministic. Added `ORDER BY cf.card_id` to the Phase 2b sample query in [cluster_flagging_tasks.py:95-107](../../backend/app/tasks/cluster_flagging_tasks.py#L95-L107). New test: `test_sample_card_ids_are_deterministic`.
- **M-2** — `top_reason_chips` tie-break was non-deterministic. Added `, cf.reason_chip ASC` as secondary sort in the Phase 2a query.
- **M-3** — `cluster_id` column is `max_length=100` but `insight.category` is unbounded. Introduced `CLUSTER_ID_MAX_LEN = 100` and truncate before upsert. New test: `test_oversize_category_is_truncated`.
- **M-4** — Single cluster upsert failure aborted the whole batch. Each cluster's upsert now runs inside `session.begin_nested()` with a logged try/except so poison rows are skipped, not fatal. New test: `test_poison_cluster_does_not_abort_batch`.

Backend tests: 12/12 passing in `test_cluster_flagging_task.py` (9 original + 3 review-added).

### Deferred to tech-debt register

- **H-1 → [TD-026](../../docs/tech-debt.md)** — Celery beat scheduler is not deployed; `beat_schedule` never fires in production. AC #3 is only satisfied at the code level. Operator runbook documents the gap and manual-enqueue workaround until TD-026 is picked up.

### LOW findings — disposition

- **L-1** (story-local) — `_utcnow()` duplicated across [cluster_flagging_tasks.py](../../backend/app/tasks/cluster_flagging_tasks.py), [flagged_topic_cluster.py](../../backend/app/models/flagged_topic_cluster.py), [insight.py](../../backend/app/models/insight.py). Pre-existing pattern; no concrete pickup driver — left inline for opportunistic cleanup.
- **L-2 → [TD-027](../../docs/tech-debt.md)** — `insights.category` has no index. Phase 1 `GROUP BY i.category` will full-scan `insights` once the table grows. Fix shape and revisit criteria live in the tech-debt entry.
- **L-3** — withdrawn on review: tests seed `card_type="insight"` but the cluster-flagging SQL doesn't filter on `card_type`, so fixture/production divergence is harmless here. If the task ever starts filtering by `card_type`, re-open.
