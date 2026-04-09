"""Tests for health_score_service (Story 4.5)."""
import os
import tempfile
import uuid
from datetime import UTC, datetime

import pytest
import pytest_asyncio
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import Session, SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession as SQLModelAsyncSession

from app.models.financial_health_score import FinancialHealthScore
from app.models.financial_profile import FinancialProfile
from app.models.user import User


def _utcnow():
    return datetime.now(UTC).replace(tzinfo=None)


# ==================== Fixtures ====================


@pytest.fixture
def sync_engine():
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    engine = create_engine(f"sqlite:///{db_path}", echo=False)
    SQLModel.metadata.create_all(engine)
    yield engine
    SQLModel.metadata.drop_all(engine)
    engine.dispose()
    os.unlink(db_path)


@pytest.fixture
def sync_session(sync_engine):
    with Session(sync_engine) as session:
        yield session


@pytest_asyncio.fixture
async def async_engine():
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)
    await engine.dispose()
    os.unlink(db_path)


@pytest_asyncio.fixture
async def async_session(async_engine) -> SQLModelAsyncSession:
    async with SQLModelAsyncSession(async_engine) as session:
        yield session


def _create_user(session: Session, sub: str = "test-sub"):
    user_id = uuid.uuid4()
    user = User(id=user_id, email=f"{sub}@test.com", cognito_sub=sub, locale="en")
    session.add(user)
    session.flush()
    return user_id


def _create_profile(
    session: Session,
    user_id: uuid.UUID,
    total_income: int = 50000,
    total_expenses: int = -20000,
    category_totals: dict | None = None,
    period_start: datetime | None = None,
    period_end: datetime | None = None,
):
    profile = FinancialProfile(
        user_id=user_id,
        total_income=total_income,
        total_expenses=total_expenses,
        category_totals=category_totals or {"food": -15000, "transport": -5000},
        period_start=period_start or datetime(2026, 1, 1),
        period_end=period_end or datetime(2026, 3, 31),
    )
    session.add(profile)
    session.flush()
    return profile


# ==================== Service Unit Tests ====================


class TestCalculateHealthScore:
    """Tests for calculate_health_score."""

    def test_balanced_profile(self, sync_session):
        """Balanced profile with decent savings yields score in 60-80 range."""
        from app.services.health_score_service import calculate_health_score

        user_id = _create_user(sync_session, "balanced-sub")
        # 50k income, -20k expenses → 60% savings rate
        _create_profile(
            sync_session,
            user_id,
            total_income=50000,
            total_expenses=-20000,
            category_totals={
                "food": -8000,
                "transport": -4000,
                "entertainment": -4000,
                "utilities": -4000,
            },
            period_start=datetime(2026, 1, 1),
            period_end=datetime(2026, 3, 31),
        )
        sync_session.commit()

        score = calculate_health_score(sync_session, user_id)

        assert 60 <= score.score <= 100
        assert score.user_id == user_id
        assert score.breakdown["savings_ratio"] > 0
        assert score.breakdown["category_diversity"] > 0
        assert score.breakdown["expense_regularity"] > 0
        assert score.breakdown["income_coverage"] > 0

    def test_overspending_profile(self, sync_session):
        """Overspending (expenses > income) yields low score."""
        from app.services.health_score_service import calculate_health_score

        user_id = _create_user(sync_session, "overspend-sub")
        _create_profile(
            sync_session,
            user_id,
            total_income=20000,
            total_expenses=-30000,
            category_totals={"food": -20000, "transport": -10000},
            period_start=datetime(2026, 1, 1),
            period_end=datetime(2026, 3, 31),
        )
        sync_session.commit()

        score = calculate_health_score(sync_session, user_id)

        assert score.score < 40
        assert score.breakdown["savings_ratio"] == 0  # Negative savings
        assert score.breakdown["income_coverage"] == 0

    def test_single_category_concentration(self, sync_session):
        """All expenses in one category penalizes diversity score."""
        from app.services.health_score_service import calculate_health_score

        user_id = _create_user(sync_session, "single-cat-sub")
        _create_profile(
            sync_session,
            user_id,
            total_income=50000,
            total_expenses=-20000,
            category_totals={"food": -20000},
            period_start=datetime(2026, 1, 1),
            period_end=datetime(2026, 3, 31),
        )
        sync_session.commit()

        score = calculate_health_score(sync_session, user_id)

        assert score.breakdown["category_diversity"] == 0

    def test_high_savings_ratio(self, sync_session):
        """High savings ratio yields score > 80."""
        from app.services.health_score_service import calculate_health_score

        user_id = _create_user(sync_session, "high-savings-sub")
        _create_profile(
            sync_session,
            user_id,
            total_income=100000,
            total_expenses=-10000,
            category_totals={
                "food": -4000,
                "transport": -3000,
                "utilities": -3000,
            },
            period_start=datetime(2026, 1, 1),
            period_end=datetime(2026, 6, 30),
        )
        sync_session.commit()

        score = calculate_health_score(sync_session, user_id)

        assert score.score > 80
        assert score.breakdown["savings_ratio"] == 100  # 90% savings capped at 100

    def test_zero_income(self, sync_session):
        """Zero income yields savings component = 0, other components still calculated."""
        from app.services.health_score_service import calculate_health_score

        user_id = _create_user(sync_session, "zero-income-sub")
        _create_profile(
            sync_session,
            user_id,
            total_income=0,
            total_expenses=-10000,
            category_totals={"food": -5000, "transport": -5000},
            period_start=datetime(2026, 1, 1),
            period_end=datetime(2026, 3, 31),
        )
        sync_session.commit()

        score = calculate_health_score(sync_session, user_id)

        assert score.breakdown["savings_ratio"] == 0
        assert score.breakdown["income_coverage"] == 0
        # Diversity and regularity can still be calculated
        assert score.breakdown["category_diversity"] >= 0
        assert score.breakdown["expense_regularity"] >= 0

    def test_no_profile_raises(self, sync_session):
        """Raises ValueError when no financial profile exists."""
        from app.services.health_score_service import calculate_health_score

        user_id = _create_user(sync_session, "no-profile-sub")
        sync_session.commit()

        with pytest.raises(ValueError, match="No financial profile"):
            calculate_health_score(sync_session, user_id)

    def test_breakdown_contains_all_components(self, sync_session):
        """Breakdown JSONB contains all 4 component scores."""
        from app.services.health_score_service import calculate_health_score

        user_id = _create_user(sync_session, "breakdown-sub")
        _create_profile(sync_session, user_id)
        sync_session.commit()

        score = calculate_health_score(sync_session, user_id)

        assert "savings_ratio" in score.breakdown
        assert "category_diversity" in score.breakdown
        assert "expense_regularity" in score.breakdown
        assert "income_coverage" in score.breakdown
        for value in score.breakdown.values():
            assert 0 <= value <= 100

    def test_score_is_appended_not_replaced(self, sync_session):
        """Each call creates a new score record (append-only)."""
        from app.services.health_score_service import calculate_health_score

        from sqlmodel import select

        user_id = _create_user(sync_session, "append-sub")
        _create_profile(sync_session, user_id)
        sync_session.commit()

        score1 = calculate_health_score(sync_session, user_id)
        score2 = calculate_health_score(sync_session, user_id)

        assert score1.id != score2.id
        all_scores = sync_session.exec(
            select(FinancialHealthScore).where(
                FinancialHealthScore.user_id == user_id
            )
        ).all()
        assert len(all_scores) == 2


# ==================== Async Service Tests ====================


class TestGetLatestScore:
    """Tests for get_latest_score (async, used by API layer)."""

    @pytest.mark.asyncio
    async def test_returns_latest_score(self, async_session):
        """Returns the most recent health score."""
        from app.services.health_score_service import get_latest_score

        user_id = uuid.uuid4()
        user = User(id=user_id, email="async@test.com", cognito_sub="async-hs-sub", locale="en")
        async_session.add(user)

        older = FinancialHealthScore(
            user_id=user_id,
            score=50,
            calculated_at=datetime(2026, 1, 1),
            breakdown={"savings_ratio": 50, "category_diversity": 50, "expense_regularity": 50, "income_coverage": 50},
        )
        newer = FinancialHealthScore(
            user_id=user_id,
            score=75,
            calculated_at=datetime(2026, 3, 1),
            breakdown={"savings_ratio": 80, "category_diversity": 70, "expense_regularity": 75, "income_coverage": 70},
        )
        async_session.add(older)
        async_session.add(newer)
        await async_session.commit()

        result = await get_latest_score(async_session, user_id)
        assert result is not None
        assert result.score == 75

    @pytest.mark.asyncio
    async def test_returns_none_when_no_score(self, async_session):
        """Returns None when no score exists."""
        from app.services.health_score_service import get_latest_score

        result = await get_latest_score(async_session, uuid.uuid4())
        assert result is None
