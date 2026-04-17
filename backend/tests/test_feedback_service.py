"""Unit tests for feedback_service (Story 7.1: engagement score, Story 7.2: card votes)."""
import uuid

import pytest

from app.services.feedback_service import (
    compute_engagement_score,
    get_card_feedback,
    store_card_interactions,
    submit_card_vote,
)


class TestComputeEngagementScore:
    """Tests for the weighted engagement score formula."""

    def test_zero_signals_produce_zero(self):
        """AC #3: all-zero signals produce 0 (with position beyond max → 0)."""
        score = compute_engagement_score(
            time_on_card_ms=0,
            education_expanded=False,
            education_depth_reached=0,
            swipe_direction="left",
            card_position_in_feed=10,
        )
        assert score == 0

    def test_time_contribution_capped_at_30_seconds(self):
        """AC #3: time_on_card_ms > 30,000ms saturates at 30 pts contribution."""
        over = compute_engagement_score(60_000, False, 0, "left", 10)
        at_cap = compute_engagement_score(30_000, False, 0, "left", 10)
        assert over == at_cap == 30

    def test_half_time_contribution(self):
        """AC #3: 12,000ms = 40% of 30s cap → 40% of 30 pts = 12 pts."""
        score = compute_engagement_score(12_000, False, 0, "left", 10)
        assert score == 12

    def test_education_expanded_contributes_25(self):
        """AC #3: education_expanded=True alone contributes 25 pts."""
        score = compute_engagement_score(0, True, 0, "left", 10)
        assert score == 25

    def test_education_depth_scales_linearly(self):
        """AC #3: education_depth_reached 0 → 0, 1 → 12 (rounded), 2 → 25."""
        assert compute_engagement_score(0, False, 0, "left", 10) == 0
        assert compute_engagement_score(0, False, 1, "left", 10) == 12  # 12.5 → 12
        assert compute_engagement_score(0, False, 2, "left", 10) == 25

    def test_swipe_direction_values(self):
        """AC #3: swipe_direction → right=10, none=5, left=0."""
        assert compute_engagement_score(0, False, 0, "right", 10) == 10
        assert compute_engagement_score(0, False, 0, "none", 10) == 5
        assert compute_engagement_score(0, False, 0, "left", 10) == 0

    def test_swipe_unknown_direction_defaults_to_none(self):
        """Defensive: unknown swipe_direction normalizes to 'none' (0.5) semantics."""
        assert compute_engagement_score(0, False, 0, "diagonal", 10) == 5

    def test_position_zero_max_points(self):
        """AC #3: position 0 → 10 pts; decays by 1 per position."""
        assert compute_engagement_score(0, False, 0, "left", 0) == 10
        assert compute_engagement_score(0, False, 0, "left", 3) == 7
        assert compute_engagement_score(0, False, 0, "left", 10) == 0
        # Position beyond 10 capped at 0
        assert compute_engagement_score(0, False, 0, "left", 15) == 0

    def test_story_example_total_79(self):
        """AC #3: story example — 12s, expanded, depth 2, right swipe, pos 3 → 79."""
        score = compute_engagement_score(
            time_on_card_ms=12_000,
            education_expanded=True,
            education_depth_reached=2,
            swipe_direction="right",
            card_position_in_feed=3,
        )
        # time 12 + expanded 25 + depth 25 + swipe 10 + pos 7 = 79
        assert score == 79

    def test_perfect_score_is_100(self):
        """AC #3: all signals at max → score = 100 (clamped)."""
        score = compute_engagement_score(
            time_on_card_ms=30_000,
            education_expanded=True,
            education_depth_reached=2,
            swipe_direction="right",
            card_position_in_feed=0,
        )
        assert score == 100

    def test_score_clamped_to_range(self):
        """Regression: final score always in [0, 100]."""
        assert 0 <= compute_engagement_score(-1_000, False, -5, "left", -3) <= 100
        assert 0 <= compute_engagement_score(10**9, True, 10, "right", 0) <= 100


# ==================== Service Persistence Tests ====================


class _FakeInteractionIn:
    """Stand-in for Pydantic CardInteractionIn (service accepts by shape)."""

    def __init__(
        self,
        card_id: uuid.UUID,
        time_on_card_ms: int = 5_000,
        education_expanded: bool = True,
        education_depth_reached: int = 1,
        swipe_direction: str = "right",
        card_position_in_feed: int = 0,
    ):
        self.card_id = card_id
        self.time_on_card_ms = time_on_card_ms
        self.education_expanded = education_expanded
        self.education_depth_reached = education_depth_reached
        self.swipe_direction = swipe_direction
        self.card_position_in_feed = card_position_in_feed


@pytest.mark.asyncio
async def test_store_card_interactions_empty_noop(async_session):
    """Empty batch → no-op, no rows inserted."""
    from sqlmodel import func, select
    from app.models.feedback import CardInteraction

    await store_card_interactions([], uuid.uuid4(), async_session)
    total = (await async_session.exec(select(func.count()).select_from(CardInteraction))).one()
    assert total == 0


@pytest.mark.asyncio
async def test_store_card_interactions_inserts_with_scores(async_session):
    """AC #2/#3: bulk-insert batch, each row has a computed engagement_score."""
    from sqlmodel import select
    from app.models.feedback import CardInteraction
    from app.models.insight import Insight
    from app.models.user import User

    user = User(email="store@test.com", cognito_sub="store-sub", locale="en")
    async_session.add(user)
    await async_session.flush()

    card_a = Insight(
        user_id=user.id,
        headline="A",
        key_metric="$1",
        why_it_matters="a",
        deep_dive="a",
        severity="high",
        category="food",
    )
    card_b = Insight(
        user_id=user.id,
        headline="B",
        key_metric="$2",
        why_it_matters="b",
        deep_dive="b",
        severity="low",
        category="food",
    )
    async_session.add_all([card_a, card_b])
    await async_session.flush()
    card_a_id, card_b_id, user_id = card_a.id, card_b.id, user.id

    batch = [
        _FakeInteractionIn(
            card_id=card_a_id,
            time_on_card_ms=12_000,
            education_expanded=True,
            education_depth_reached=2,
            swipe_direction="right",
            card_position_in_feed=3,
        ),
        _FakeInteractionIn(
            card_id=card_b_id,
            time_on_card_ms=0,
            education_expanded=False,
            education_depth_reached=0,
            swipe_direction="left",
            card_position_in_feed=10,
        ),
    ]

    await store_card_interactions(batch, user_id, async_session)

    rows = (
        await async_session.exec(
            select(CardInteraction).order_by(CardInteraction.card_position_in_feed)
        )
    ).all()
    assert len(rows) == 2
    assert rows[0].engagement_score == 79  # card_a from story example
    assert rows[1].engagement_score == 0  # card_b zero-signals
    assert {r.card_id for r in rows} == {card_a_id, card_b_id}
    assert all(r.user_id == user_id for r in rows)


# ==================== Card Vote Service Tests (Story 7.2) ====================


async def _setup_user_and_card(session):
    """Helper to create a user and insight card for vote tests."""
    from app.models.insight import Insight
    from app.models.user import User

    user = User(email="vote@test.com", cognito_sub="vote-sub", locale="en")
    session.add(user)
    await session.flush()

    card = Insight(
        user_id=user.id,
        headline="Vote test",
        key_metric="$1",
        why_it_matters="why",
        deep_dive="deep",
        severity="medium",
        category="food",
    )
    session.add(card)
    await session.flush()
    return user.id, card.id


@pytest.mark.asyncio
async def test_submit_card_vote_creates_new_record(async_session):
    """AC #2: first vote creates a new card_feedback row."""
    user_id, card_id = await _setup_user_and_card(async_session)

    result = await submit_card_vote(
        card_id=card_id,
        user_id=user_id,
        vote="up",
        card_type="food",
        session=async_session,
    )
    assert result.vote == "up"
    assert result.card_id == card_id
    assert result.user_id == user_id
    assert result.feedback_source == "card_vote"


@pytest.mark.asyncio
async def test_submit_card_vote_upsert_changes_vote(async_session):
    """AC #5: voting opposite direction updates existing row, not duplicates."""
    user_id, card_id = await _setup_user_and_card(async_session)

    first = await submit_card_vote(
        card_id=card_id,
        user_id=user_id,
        vote="up",
        card_type="food",
        session=async_session,
    )
    assert first.vote == "up"

    second = await submit_card_vote(
        card_id=card_id,
        user_id=user_id,
        vote="down",
        card_type="food",
        session=async_session,
    )
    assert second.vote == "down"

    # Verify only one row exists (upsert, not insert)
    from sqlmodel import func, select
    from app.models.feedback import CardFeedback

    count = (
        await async_session.exec(
            select(func.count()).select_from(CardFeedback).where(
                CardFeedback.user_id == user_id,
                CardFeedback.card_id == card_id,
            )
        )
    ).one()
    assert count == 1


@pytest.mark.asyncio
async def test_submit_card_vote_idempotent(async_session):
    """Voting the same way twice is idempotent."""
    user_id, card_id = await _setup_user_and_card(async_session)

    await submit_card_vote(card_id=card_id, user_id=user_id, vote="up", card_type="food", session=async_session)
    await submit_card_vote(card_id=card_id, user_id=user_id, vote="up", card_type="food", session=async_session)

    from sqlmodel import func, select
    from app.models.feedback import CardFeedback

    count = (
        await async_session.exec(
            select(func.count()).select_from(CardFeedback).where(
                CardFeedback.user_id == user_id,
                CardFeedback.card_id == card_id,
            )
        )
    ).one()
    assert count == 1


@pytest.mark.asyncio
async def test_get_card_feedback_found(async_session):
    """AC #4: get_card_feedback returns the existing vote."""
    user_id, card_id = await _setup_user_and_card(async_session)

    await submit_card_vote(card_id=card_id, user_id=user_id, vote="down", card_type="food", session=async_session)

    result = await get_card_feedback(card_id=card_id, user_id=user_id, session=async_session)
    assert result is not None
    assert result.vote == "down"


@pytest.mark.asyncio
async def test_get_card_feedback_not_found(async_session):
    """AC #4: get_card_feedback returns None when no vote exists."""
    result = await get_card_feedback(
        card_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        session=async_session,
    )
    assert result is None
