"""Tests for the RAG topic cluster auto-flagging Celery task (Story 7.8)."""
import uuid
from contextlib import contextmanager
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, select

from app.models.feedback import CardFeedback
from app.models.flagged_topic_cluster import FlaggedTopicCluster
from app.models.insight import Insight
from app.models.user import User


@pytest.fixture
def sync_engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    yield engine
    SQLModel.metadata.drop_all(engine)
    engine.dispose()


def _mock_sync_session_cm(engine):
    @contextmanager
    def _cm():
        session = Session(engine)
        try:
            yield session
        finally:
            session.close()

    return _cm


def _seed_user(engine) -> uuid.UUID:
    user_id = uuid.uuid4()
    with Session(engine) as session:
        session.add(
            User(
                id=user_id,
                email=f"{user_id}@test.com",
                cognito_sub=f"sub-{user_id}",
                locale="en",
            )
        )
        session.commit()
    return user_id


def _seed_insight(engine, owner_id: uuid.UUID, category: str) -> uuid.UUID:
    insight_id = uuid.uuid4()
    with Session(engine) as session:
        session.add(
            Insight(
                id=insight_id,
                user_id=owner_id,
                headline=f"{category} insight",
                key_metric="100 UAH",
                why_it_matters="because",
                deep_dive="details",
                severity="medium",
                category=category,
            )
        )
        session.commit()
    return insight_id


def _add_feedback(
    engine,
    *,
    user_id: uuid.UUID,
    card_id: uuid.UUID,
    vote: str | None,
    reason_chip: str | None = None,
    feedback_source: str = "card_vote",
    card_type: str = "insight",
) -> None:
    with Session(engine) as session:
        session.add(
            CardFeedback(
                user_id=user_id,
                card_id=card_id,
                card_type=card_type,
                vote=vote,
                reason_chip=reason_chip,
                feedback_source=feedback_source,
            )
        )
        session.commit()


def _add_votes_distinct_users(
    engine,
    *,
    card_id: uuid.UUID,
    vote: str,
    count: int,
    reason_chip: str | None = None,
) -> None:
    """Add N votes each from a fresh dummy user (satisfies unique constraint)."""
    for _ in range(count):
        u = uuid.uuid4()
        with Session(engine) as session:
            session.add(
                User(
                    id=u,
                    email=f"{u}@test.com",
                    cognito_sub=f"sub-{u}",
                    locale="en",
                )
            )
            session.add(
                CardFeedback(
                    user_id=u,
                    card_id=card_id,
                    card_type="insight",
                    vote=vote,
                    reason_chip=reason_chip,
                    feedback_source="card_vote",
                )
            )
            session.commit()


class TestFlagLowQualityClusters:
    """Covers AC #1–#5 for the cluster auto-flagging task."""

    @patch("app.tasks.cluster_flagging_tasks.get_sync_session")
    def test_cluster_not_flagged_below_10_votes(self, mock_get_session, sync_engine):
        """AC #1, #5: a cluster with 9 down-votes is never flagged."""
        mock_get_session.side_effect = _mock_sync_session_cm(sync_engine)

        owner = _seed_user(sync_engine)
        card = _seed_insight(sync_engine, owner, "food")
        _add_votes_distinct_users(
            sync_engine, card_id=card, vote="down", count=9
        )

        from app.tasks.cluster_flagging_tasks import flag_low_quality_clusters

        result = flag_low_quality_clusters()

        assert result["clusters_evaluated"] == 0
        assert result["clusters_flagged"] == 0
        with Session(sync_engine) as s:
            assert s.exec(select(FlaggedTopicCluster)).all() == []

    @patch("app.tasks.cluster_flagging_tasks.get_sync_session")
    def test_cluster_not_flagged_at_30_percent_exactly(
        self, mock_get_session, sync_engine
    ):
        """AC #2: 30% exactly is not flagged (strictly greater than 30%)."""
        mock_get_session.side_effect = _mock_sync_session_cm(sync_engine)

        owner = _seed_user(sync_engine)
        card = _seed_insight(sync_engine, owner, "transport")
        _add_votes_distinct_users(sync_engine, card_id=card, vote="down", count=3)
        _add_votes_distinct_users(sync_engine, card_id=card, vote="up", count=7)

        from app.tasks.cluster_flagging_tasks import flag_low_quality_clusters

        result = flag_low_quality_clusters()

        assert result["clusters_evaluated"] == 1
        assert result["clusters_flagged"] == 0
        with Session(sync_engine) as s:
            assert s.exec(select(FlaggedTopicCluster)).all() == []

    @patch("app.tasks.cluster_flagging_tasks.get_sync_session")
    def test_cluster_flagged_above_threshold(self, mock_get_session, sync_engine):
        """AC #2: 40% down with 10 votes → flagged with correct stats."""
        mock_get_session.side_effect = _mock_sync_session_cm(sync_engine)

        owner = _seed_user(sync_engine)
        card = _seed_insight(sync_engine, owner, "food")
        _add_votes_distinct_users(sync_engine, card_id=card, vote="down", count=4)
        _add_votes_distinct_users(sync_engine, card_id=card, vote="up", count=6)

        from app.tasks.cluster_flagging_tasks import flag_low_quality_clusters

        result = flag_low_quality_clusters()

        assert result["clusters_flagged"] == 1

        with Session(sync_engine) as s:
            flagged = s.exec(
                select(FlaggedTopicCluster).where(
                    FlaggedTopicCluster.cluster_id == "food"
                )
            ).one()
            assert flagged.thumbs_down_rate == pytest.approx(0.4)
            assert flagged.total_votes == 10
            assert flagged.total_down_votes == 4

    @patch("app.tasks.cluster_flagging_tasks.get_sync_session")
    def test_reason_chips_captured(self, mock_get_session, sync_engine):
        """AC #4: top_reason_chips reflects down-vote chip frequencies."""
        mock_get_session.side_effect = _mock_sync_session_cm(sync_engine)

        owner = _seed_user(sync_engine)
        card = _seed_insight(sync_engine, owner, "food")
        _add_votes_distinct_users(
            sync_engine, card_id=card, vote="down", count=3,
            reason_chip="not_relevant",
        )
        _add_votes_distinct_users(
            sync_engine, card_id=card, vote="down", count=2,
            reason_chip="seems_incorrect",
        )
        _add_votes_distinct_users(sync_engine, card_id=card, vote="up", count=5)

        from app.tasks.cluster_flagging_tasks import flag_low_quality_clusters

        flag_low_quality_clusters()

        with Session(sync_engine) as s:
            flagged = s.exec(
                select(FlaggedTopicCluster).where(
                    FlaggedTopicCluster.cluster_id == "food"
                )
            ).one()
            assert flagged.top_reason_chips == {
                "not_relevant": 3,
                "seems_incorrect": 2,
            }

    @patch("app.tasks.cluster_flagging_tasks.get_sync_session")
    def test_sample_card_ids_captured(self, mock_get_session, sync_engine):
        """AC #4: sample_card_ids contains up to 5 UUIDs of down-voted cards."""
        mock_get_session.side_effect = _mock_sync_session_cm(sync_engine)

        owner = _seed_user(sync_engine)
        # 7 distinct cards in the same cluster, each with one down-vote,
        # plus enough up-votes on one of them to reach 10 total votes.
        cards = [
            _seed_insight(sync_engine, owner, "food") for _ in range(7)
        ]
        for c in cards:
            _add_votes_distinct_users(
                sync_engine, card_id=c, vote="down", count=1
            )
        # Pad to >=10 votes total via ups on first card
        _add_votes_distinct_users(sync_engine, card_id=cards[0], vote="up", count=3)

        from app.tasks.cluster_flagging_tasks import flag_low_quality_clusters

        flag_low_quality_clusters()

        with Session(sync_engine) as s:
            flagged = s.exec(
                select(FlaggedTopicCluster).where(
                    FlaggedTopicCluster.cluster_id == "food"
                )
            ).one()
            assert len(flagged.sample_card_ids) == 5
            all_card_ids = {str(c) for c in cards}
            assert set(flagged.sample_card_ids).issubset(all_card_ids)

    @patch("app.tasks.cluster_flagging_tasks.get_sync_session")
    def test_upsert_updates_existing_flag(self, mock_get_session, sync_engine):
        """AC #2/#4: re-running the task updates stats but preserves flagged_at."""
        mock_get_session.side_effect = _mock_sync_session_cm(sync_engine)

        owner = _seed_user(sync_engine)
        card = _seed_insight(sync_engine, owner, "food")
        _add_votes_distinct_users(sync_engine, card_id=card, vote="down", count=4)
        _add_votes_distinct_users(sync_engine, card_id=card, vote="up", count=6)

        from app.tasks.cluster_flagging_tasks import flag_low_quality_clusters

        flag_low_quality_clusters()
        with Session(sync_engine) as s:
            original = s.exec(
                select(FlaggedTopicCluster).where(
                    FlaggedTopicCluster.cluster_id == "food"
                )
            ).one()
            original_flagged_at = original.flagged_at
            original_last_eval = original.last_evaluated_at

        # Add more down-votes and re-run
        _add_votes_distinct_users(sync_engine, card_id=card, vote="down", count=3)

        flag_low_quality_clusters()

        with Session(sync_engine) as s:
            updated = s.exec(
                select(FlaggedTopicCluster).where(
                    FlaggedTopicCluster.cluster_id == "food"
                )
            ).one()
            # total_votes went from 10 → 13, down_votes 4 → 7
            assert updated.total_votes == 13
            assert updated.total_down_votes == 7
            assert updated.thumbs_down_rate == pytest.approx(7 / 13, abs=1e-4)
            # flagged_at unchanged, last_evaluated_at refreshed
            assert updated.flagged_at == original_flagged_at
            assert updated.last_evaluated_at >= original_last_eval

    @patch("app.tasks.cluster_flagging_tasks.get_sync_session")
    def test_multiple_clusters_independent(self, mock_get_session, sync_engine):
        """AC #2/#5: only qualifying clusters are flagged; others ignored."""
        mock_get_session.side_effect = _mock_sync_session_cm(sync_engine)

        owner = _seed_user(sync_engine)
        food_card = _seed_insight(sync_engine, owner, "food")
        transport_card = _seed_insight(sync_engine, owner, "transport")

        # food: 40% down → flagged
        _add_votes_distinct_users(
            sync_engine, card_id=food_card, vote="down", count=4
        )
        _add_votes_distinct_users(
            sync_engine, card_id=food_card, vote="up", count=6
        )

        # transport: 20% down → not flagged
        _add_votes_distinct_users(
            sync_engine, card_id=transport_card, vote="down", count=2
        )
        _add_votes_distinct_users(
            sync_engine, card_id=transport_card, vote="up", count=8
        )

        from app.tasks.cluster_flagging_tasks import flag_low_quality_clusters

        result = flag_low_quality_clusters()

        assert result["clusters_evaluated"] == 2
        assert result["clusters_flagged"] == 1
        with Session(sync_engine) as s:
            flagged = s.exec(select(FlaggedTopicCluster)).all()
            assert len(flagged) == 1
            assert flagged[0].cluster_id == "food"

    @patch("app.tasks.cluster_flagging_tasks.get_sync_session")
    def test_issue_reports_excluded(self, mock_get_session, sync_engine):
        """AC #1: feedback rows with vote=NULL (issue reports) do not count."""
        mock_get_session.side_effect = _mock_sync_session_cm(sync_engine)

        owner = _seed_user(sync_engine)
        card = _seed_insight(sync_engine, owner, "food")

        # 4 real down-votes + 5 ups + 3 issue reports (vote=NULL)
        _add_votes_distinct_users(sync_engine, card_id=card, vote="down", count=4)
        _add_votes_distinct_users(sync_engine, card_id=card, vote="up", count=5)
        for _ in range(3):
            u = uuid.uuid4()
            with Session(sync_engine) as s:
                s.add(
                    User(
                        id=u,
                        email=f"{u}@test.com",
                        cognito_sub=f"sub-{u}",
                        locale="en",
                    )
                )
                s.add(
                    CardFeedback(
                        user_id=u,
                        card_id=card,
                        card_type="insight",
                        vote=None,
                        feedback_source="issue_report",
                        issue_category="wrong_info",
                    )
                )
                s.commit()

        from app.tasks.cluster_flagging_tasks import flag_low_quality_clusters

        result = flag_low_quality_clusters()

        # Only 9 vote rows count → below MIN_VOTES → not evaluated, not flagged
        assert result["clusters_evaluated"] == 0
        assert result["clusters_flagged"] == 0
        with Session(sync_engine) as s:
            assert s.exec(select(FlaggedTopicCluster)).all() == []

    @patch("app.tasks.cluster_flagging_tasks.get_sync_session")
    def test_sample_card_ids_are_deterministic(
        self, mock_get_session, sync_engine
    ):
        """M-1: sample_card_ids order is stable across runs (ORDER BY card_id)."""
        mock_get_session.side_effect = _mock_sync_session_cm(sync_engine)

        owner = _seed_user(sync_engine)
        cards = [_seed_insight(sync_engine, owner, "food") for _ in range(7)]
        for c in cards:
            _add_votes_distinct_users(sync_engine, card_id=c, vote="down", count=1)
        _add_votes_distinct_users(sync_engine, card_id=cards[0], vote="up", count=3)

        from app.tasks.cluster_flagging_tasks import flag_low_quality_clusters

        flag_low_quality_clusters()
        with Session(sync_engine) as s:
            first = s.exec(
                select(FlaggedTopicCluster).where(
                    FlaggedTopicCluster.cluster_id == "food"
                )
            ).one()
            first_sample = list(first.sample_card_ids)

        flag_low_quality_clusters()
        with Session(sync_engine) as s:
            second = s.exec(
                select(FlaggedTopicCluster).where(
                    FlaggedTopicCluster.cluster_id == "food"
                )
            ).one()
            assert second.sample_card_ids == first_sample
            # Stable means sorted — the smallest UUID (string sort) is first.
            assert second.sample_card_ids == sorted(first_sample)

    @patch("app.tasks.cluster_flagging_tasks.get_sync_session")
    def test_poison_cluster_does_not_abort_batch(
        self, mock_get_session, sync_engine
    ):
        """M-4: a failing upsert on one cluster does not block others."""
        mock_get_session.side_effect = _mock_sync_session_cm(sync_engine)

        owner = _seed_user(sync_engine)
        food_card = _seed_insight(sync_engine, owner, "food")
        transport_card = _seed_insight(sync_engine, owner, "transport")

        _add_votes_distinct_users(sync_engine, card_id=food_card, vote="down", count=4)
        _add_votes_distinct_users(sync_engine, card_id=food_card, vote="up", count=6)
        _add_votes_distinct_users(
            sync_engine, card_id=transport_card, vote="down", count=5
        )
        _add_votes_distinct_users(
            sync_engine, card_id=transport_card, vote="up", count=5
        )

        from app.tasks import cluster_flagging_tasks

        real_execute = Session.execute
        calls = {"n": 0}

        def poisoned_execute(self, statement, *args, **kwargs):
            # Let SELECTs through; fail only the first upsert (insert stmt),
            # which is the food cluster's upsert (clusters are ordered by category).
            from sqlalchemy.dialects.postgresql import Insert as PgInsert
            from sqlalchemy.dialects.sqlite import Insert as SqliteInsert
            if isinstance(statement, (PgInsert, SqliteInsert)):
                calls["n"] += 1
                if calls["n"] == 1:
                    raise RuntimeError("simulated upsert failure")
            return real_execute(self, statement, *args, **kwargs)

        with patch.object(Session, "execute", poisoned_execute):
            result = cluster_flagging_tasks.flag_low_quality_clusters()

        # Both clusters qualified; one upsert failed, the other succeeded.
        assert result["clusters_evaluated"] == 2
        assert result["clusters_flagged"] == 1
        with Session(sync_engine) as s:
            flagged = s.exec(select(FlaggedTopicCluster)).all()
            assert len(flagged) == 1
            assert flagged[0].cluster_id == "transport"

    @patch("app.tasks.cluster_flagging_tasks.get_sync_session")
    def test_oversize_category_is_truncated(self, mock_get_session, sync_engine):
        """M-3: a >100-char category is truncated into cluster_id."""
        mock_get_session.side_effect = _mock_sync_session_cm(sync_engine)

        owner = _seed_user(sync_engine)
        oversize_category = "x" * 250
        card = _seed_insight(sync_engine, owner, oversize_category)
        _add_votes_distinct_users(sync_engine, card_id=card, vote="down", count=4)
        _add_votes_distinct_users(sync_engine, card_id=card, vote="up", count=6)

        from app.tasks.cluster_flagging_tasks import (
            CLUSTER_ID_MAX_LEN,
            flag_low_quality_clusters,
        )

        result = flag_low_quality_clusters()
        assert result["clusters_flagged"] == 1

        with Session(sync_engine) as s:
            flagged = s.exec(select(FlaggedTopicCluster)).one()
            assert flagged.cluster_id == "x" * CLUSTER_ID_MAX_LEN
            assert len(flagged.cluster_id) == CLUSTER_ID_MAX_LEN

    @patch("app.tasks.cluster_flagging_tasks.get_sync_session")
    def test_returns_summary_dict(self, mock_get_session, sync_engine):
        """Task returns a dict with clusters_evaluated and clusters_flagged keys."""
        mock_get_session.side_effect = _mock_sync_session_cm(sync_engine)

        from app.tasks.cluster_flagging_tasks import flag_low_quality_clusters

        result = flag_low_quality_clusters()

        assert set(result.keys()) == {"clusters_evaluated", "clusters_flagged"}
        assert result["clusters_evaluated"] == 0
        assert result["clusters_flagged"] == 0
