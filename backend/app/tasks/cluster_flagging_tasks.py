"""Celery task for auto-flagging low-quality RAG topic clusters (Story 7.8).

Runs nightly via Celery beat. Scans card_feedback votes joined on insights,
groups by insight.category (the "topic cluster" signal), and upserts a
FlaggedTopicCluster row for every category that has >=10 votes and a
thumbs-down rate strictly greater than 30%.
"""
import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import text

from app.core.database import get_sync_session
from app.models.flagged_topic_cluster import FlaggedTopicCluster
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)

MIN_VOTES = 10
DOWN_RATE_THRESHOLD = 0.30  # strictly greater than
CLUSTER_ID_MAX_LEN = 100  # matches FlaggedTopicCluster.cluster_id column


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _dialect_insert(session):
    dialect_name = session.get_bind().dialect.name
    if dialect_name == "postgresql":
        from sqlalchemy.dialects.postgresql import insert
    elif dialect_name == "sqlite":
        from sqlalchemy.dialects.sqlite import insert
    else:
        raise NotImplementedError(
            f"upsert not supported for dialect: {dialect_name}"
        )
    return insert


@celery_app.task(bind=False, max_retries=1, acks_late=True)
def flag_low_quality_clusters() -> dict:
    """Scan card_feedback and flag RAG topic clusters above the down-vote threshold."""
    with get_sync_session() as session:
        insert_fn = _dialect_insert(session)

        rows = session.execute(
            text(
                """
                SELECT
                    i.category AS category,
                    COUNT(cf.id) AS total_votes,
                    COUNT(cf.id) FILTER (WHERE cf.vote = 'down') AS down_votes
                FROM card_feedback cf
                JOIN insights i ON cf.card_id = i.id
                WHERE cf.vote IS NOT NULL
                GROUP BY i.category
                HAVING COUNT(cf.id) >= :min_votes
                """
            ),
            {"min_votes": MIN_VOTES},
        ).fetchall()

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

            chip_rows = session.execute(
                text(
                    """
                    SELECT cf.reason_chip AS reason_chip, COUNT(*) AS cnt
                    FROM card_feedback cf
                    JOIN insights i ON cf.card_id = i.id
                    WHERE i.category = :cat
                      AND cf.vote = 'down'
                      AND cf.reason_chip IS NOT NULL
                    GROUP BY cf.reason_chip
                    ORDER BY cnt DESC, cf.reason_chip ASC
                    LIMIT 5
                    """
                ),
                {"cat": category},
            ).fetchall()
            reason_chips = {r.reason_chip: r.cnt for r in chip_rows}

            card_rows = session.execute(
                text(
                    """
                    SELECT DISTINCT cf.card_id AS card_id
                    FROM card_feedback cf
                    JOIN insights i ON cf.card_id = i.id
                    WHERE i.category = :cat AND cf.vote = 'down'
                    ORDER BY cf.card_id
                    LIMIT 5
                    """
                ),
                {"cat": category},
            ).fetchall()
            sample_card_ids = [str(uuid.UUID(str(r.card_id))) for r in card_rows]

            # Truncate to column width; insights.category has no length cap upstream.
            cluster_id_value = category[:CLUSTER_ID_MAX_LEN]

            now = _utcnow()
            stmt = insert_fn(FlaggedTopicCluster).values(
                id=uuid.uuid4(),
                cluster_id=cluster_id_value,
                thumbs_down_rate=round(down_rate, 4),
                total_votes=total_votes,
                total_down_votes=down_votes,
                top_reason_chips=reason_chips,
                sample_card_ids=sample_card_ids,
                flagged_at=now,
                last_evaluated_at=now,
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
            # Per-cluster savepoint so one poison row doesn't abort the whole batch.
            try:
                with session.begin_nested():
                    session.execute(stmt)
            except Exception:
                logger.exception(
                    "rag_cluster_flagging_upsert_failed",
                    extra={"cluster_id": cluster_id_value},
                )
                continue
            clusters_flagged += 1

        session.commit()

    logger.info(
        "rag_cluster_flagging_completed",
        extra={
            "clusters_evaluated": clusters_evaluated,
            "clusters_flagged": clusters_flagged,
        },
    )
    return {
        "clusters_evaluated": clusters_evaluated,
        "clusters_flagged": clusters_flagged,
    }
