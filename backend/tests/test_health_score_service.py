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
from app.models.transaction import Transaction
from app.models.upload import Upload
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
    period_start: datetime | None = datetime(2026, 1, 1),
    period_end: datetime | None = datetime(2026, 3, 31),
):
    profile = FinancialProfile(
        user_id=user_id,
        total_income=total_income,
        total_expenses=total_expenses,
        category_totals=category_totals or {"food": -15000, "transport": -5000},
        period_start=period_start,
        period_end=period_end,
    )
    session.add(profile)
    session.flush()
    return profile


def _create_upload(session: Session, user_id: uuid.UUID) -> uuid.UUID:
    upload = Upload(
        user_id=user_id,
        file_name="test.csv",
        s3_key=f"test/{uuid.uuid4()}",
        file_size=100,
        mime_type="text/csv",
    )
    session.add(upload)
    session.flush()
    return upload.id


def _add_transaction(
    session: Session,
    user_id: uuid.UUID,
    upload_id: uuid.UUID,
    amount: int,
    kind: str,
    date: datetime = datetime(2026, 2, 1),
    category: str | None = None,
):
    txn = Transaction(
        user_id=user_id,
        upload_id=upload_id,
        date=date,
        description=f"{kind} txn",
        amount=amount,
        transaction_kind=kind,
        dedup_hash=str(uuid.uuid4()),
        category=category,
    )
    session.add(txn)
    session.flush()
    return txn


# ==================== Service Unit Tests ====================


class TestCalculateHealthScore:
    """Tests for calculate_health_score."""

    def test_balanced_profile(self, sync_session):
        """Balanced profile with decent savings yields score in 60-80 range."""
        from app.services.health_score_service import calculate_health_score

        user_id = _create_user(sync_session, "balanced-sub")
        upload_id = _create_upload(sync_session, user_id)
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
        )
        # Story 4.9: savings_ratio now reads transaction_kind directly.
        _add_transaction(sync_session, user_id, upload_id, 50000, "income")
        _add_transaction(sync_session, user_id, upload_id, -30000, "savings")
        _add_transaction(sync_session, user_id, upload_id, -5000, "spending")
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
        upload_id = _create_upload(sync_session, user_id)
        _create_profile(
            sync_session,
            user_id,
            total_income=20000,
            total_expenses=-30000,
            category_totals={"food": -20000, "transport": -10000},
        )
        # Income but no savings kind → savings_ratio = 0 (real zero).
        _add_transaction(sync_session, user_id, upload_id, 20000, "income")
        _add_transaction(sync_session, user_id, upload_id, -20000, "spending")
        _add_transaction(sync_session, user_id, upload_id, -10000, "spending")
        sync_session.commit()

        score = calculate_health_score(sync_session, user_id)

        assert score.score < 40
        assert score.breakdown["savings_ratio"] == 0
        assert score.breakdown["income_coverage"] == 0

    def test_single_category_concentration(self, sync_session):
        """All expenses in one category penalizes diversity score."""
        from app.services.health_score_service import calculate_health_score

        user_id = _create_user(sync_session, "single-cat-sub")
        upload_id = _create_upload(sync_session, user_id)
        _create_profile(
            sync_session,
            user_id,
            total_income=50000,
            total_expenses=-20000,
            category_totals={"food": -20000},
        )
        _add_transaction(sync_session, user_id, upload_id, 50000, "income")
        _add_transaction(sync_session, user_id, upload_id, -20000, "spending")
        sync_session.commit()

        score = calculate_health_score(sync_session, user_id)

        assert score.breakdown["category_diversity"] == 0

    def test_high_savings_ratio(self, sync_session):
        """High savings ratio (savings >= income) clamps to 100."""
        from app.services.health_score_service import calculate_health_score

        user_id = _create_user(sync_session, "high-savings-sub")
        upload_id = _create_upload(sync_session, user_id)
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
            period_end=datetime(2026, 6, 30),
        )
        _add_transaction(sync_session, user_id, upload_id, 100000, "income")
        # AC #1: raw_ratio clamps at 1.0; savings > income → 100
        _add_transaction(sync_session, user_id, upload_id, -120000, "savings")
        _add_transaction(sync_session, user_id, upload_id, -10000, "spending")
        sync_session.commit()

        score = calculate_health_score(sync_session, user_id)

        assert score.score > 80
        assert score.breakdown["savings_ratio"] == 100

    def test_zero_income(self, sync_session):
        """No income-kind transactions → savings_ratio is None (AC #2)."""
        from app.services.health_score_service import calculate_health_score

        user_id = _create_user(sync_session, "zero-income-sub")
        upload_id = _create_upload(sync_session, user_id)
        _create_profile(
            sync_session,
            user_id,
            total_income=0,
            total_expenses=-10000,
            category_totals={"food": -5000, "transport": -5000},
        )
        _add_transaction(sync_session, user_id, upload_id, -5000, "spending")
        _add_transaction(sync_session, user_id, upload_id, -5000, "spending")
        sync_session.commit()

        score = calculate_health_score(sync_session, user_id)

        assert score.breakdown["savings_ratio"] is None
        assert score.breakdown["income_coverage"] == 0
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
        """Breakdown JSONB contains all 4 component keys."""
        from app.services.health_score_service import calculate_health_score

        user_id = _create_user(sync_session, "breakdown-sub")
        upload_id = _create_upload(sync_session, user_id)
        _create_profile(sync_session, user_id)
        _add_transaction(sync_session, user_id, upload_id, 50000, "income")
        _add_transaction(sync_session, user_id, upload_id, -15000, "spending")
        _add_transaction(sync_session, user_id, upload_id, -5000, "spending")
        sync_session.commit()

        score = calculate_health_score(sync_session, user_id)

        assert "savings_ratio" in score.breakdown
        assert "category_diversity" in score.breakdown
        assert "expense_regularity" in score.breakdown
        assert "income_coverage" in score.breakdown
        for value in score.breakdown.values():
            assert value is None or 0 <= value <= 100

    def test_score_is_appended_not_replaced(self, sync_session):
        """Each call creates a new score record (append-only)."""
        from app.services.health_score_service import calculate_health_score

        from sqlmodel import select

        user_id = _create_user(sync_session, "append-sub")
        upload_id = _create_upload(sync_session, user_id)
        _create_profile(sync_session, user_id)
        _add_transaction(sync_session, user_id, upload_id, 50000, "income")
        _add_transaction(sync_session, user_id, upload_id, -15000, "spending")
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


# ==================== Story 4.9: transaction_kind wiring ====================


class TestSavingsRatioFromTransactionKind:
    """Story 4.9: savings_ratio reads transaction_kind, not amount signs or category."""

    def test_savings_ratio_from_kind_sums(self, sync_session):
        """AC #1, #5: savings / income = 10000 / 50000 → 20."""
        from app.services.health_score_service import calculate_health_score

        user_id = _create_user(sync_session, "sr-basic-sub")
        upload_id = _create_upload(sync_session, user_id)
        _create_profile(sync_session, user_id)
        _add_transaction(sync_session, user_id, upload_id, 50000, "income")
        _add_transaction(sync_session, user_id, upload_id, -10000, "savings")
        _add_transaction(sync_session, user_id, upload_id, -3000, "spending")
        sync_session.commit()

        score = calculate_health_score(sync_session, user_id)
        assert score.breakdown["savings_ratio"] == 20

    def test_no_income_returns_null(self, sync_session):
        """AC #2: no income-kind entries → savings_ratio is None, final score re-normalizes."""
        from app.services.health_score_service import calculate_health_score

        user_id = _create_user(sync_session, "sr-no-income-sub")
        upload_id = _create_upload(sync_session, user_id)
        _create_profile(
            sync_session,
            user_id,
            total_income=0,
            total_expenses=-10000,
            category_totals={"food": -5000, "transport": -5000},
        )
        _add_transaction(sync_session, user_id, upload_id, -5000, "spending")
        _add_transaction(sync_session, user_id, upload_id, -5000, "spending")
        sync_session.commit()

        score = calculate_health_score(sync_session, user_id)

        assert score.breakdown["savings_ratio"] is None
        # Final score should be the average of the remaining three components.
        d = score.breakdown["category_diversity"]
        r = score.breakdown["expense_regularity"]
        c = score.breakdown["income_coverage"]
        expected = int(round((0.2 * d + 0.2 * r + 0.2 * c) / 0.6))
        assert score.score == expected

    def test_income_but_no_savings_returns_zero(self, sync_session):
        """AC #3: income with no savings kind → savings_ratio = 0 (real zero)."""
        from app.services.health_score_service import calculate_health_score

        user_id = _create_user(sync_session, "sr-zero-sub")
        upload_id = _create_upload(sync_session, user_id)
        _create_profile(sync_session, user_id)
        _add_transaction(sync_session, user_id, upload_id, 50000, "income")
        _add_transaction(sync_session, user_id, upload_id, -10000, "spending")
        sync_session.commit()

        score = calculate_health_score(sync_session, user_id)
        assert score.breakdown["savings_ratio"] == 0
        assert isinstance(score.breakdown["savings_ratio"], int)

    def test_savings_greater_than_income_clamps_to_100(self, sync_session):
        """AC #1: raw_ratio clamps to [0.0, 1.0]."""
        from app.services.health_score_service import calculate_health_score

        user_id = _create_user(sync_session, "sr-clamp-sub")
        upload_id = _create_upload(sync_session, user_id)
        _create_profile(sync_session, user_id)
        _add_transaction(sync_session, user_id, upload_id, 30000, "income")
        _add_transaction(sync_session, user_id, upload_id, -80000, "savings")
        sync_session.commit()

        score = calculate_health_score(sync_session, user_id)
        assert score.breakdown["savings_ratio"] == 100

    def test_legacy_spending_default_returns_null(self, sync_session):
        """AC #6: pre-Epic-11 rows default to kind='spending' → savings_ratio None."""
        from app.services.health_score_service import calculate_health_score

        user_id = _create_user(sync_session, "sr-legacy-sub")
        upload_id = _create_upload(sync_session, user_id)
        _create_profile(sync_session, user_id)
        # Legacy: every row defaulted to 'spending' (even what was really salary).
        _add_transaction(sync_session, user_id, upload_id, 50000, "spending")
        _add_transaction(sync_session, user_id, upload_id, -10000, "spending")
        _add_transaction(sync_session, user_id, upload_id, -5000, "spending")
        sync_session.commit()

        score = calculate_health_score(sync_session, user_id)
        assert score.breakdown["savings_ratio"] is None

    def test_reads_kind_not_amount_sign(self, sync_session):
        """AC #4: implementation reads transaction_kind, not amount sign."""
        from app.services.health_score_service import calculate_health_score

        user_id = _create_user(sync_session, "sr-kind-only-sub")
        upload_id = _create_upload(sync_session, user_id)
        _create_profile(sync_session, user_id)
        # Pathological mix: sign and kind disagree. Code must trust kind.
        # income: 40000 (positive), but we add a negative row tagged 'income' too.
        _add_transaction(sync_session, user_id, upload_id, 40000, "income")
        _add_transaction(sync_session, user_id, upload_id, -10000, "income")  # kind wins
        _add_transaction(sync_session, user_id, upload_id, -5000, "savings")
        sync_session.commit()

        score = calculate_health_score(sync_session, user_id)
        # abs-sum by kind: income=50000, savings=5000 → 10.
        assert score.breakdown["savings_ratio"] == 10

    def test_empty_profile_short_circuits(self, sync_session):
        """Empty profile (period_start/end=None) → savings_ratio None, no query needed."""
        from app.services.health_score_service import calculate_health_score

        user_id = _create_user(sync_session, "sr-empty-sub")
        _create_profile(
            sync_session,
            user_id,
            total_income=0,
            total_expenses=0,
            category_totals={},
            period_start=None,
            period_end=None,
        )
        sync_session.commit()

        score = calculate_health_score(sync_session, user_id)
        assert score.breakdown["savings_ratio"] is None

    def test_transactions_outside_period_ignored(self, sync_session):
        """The GROUP BY is scoped to profile's [period_start, period_end]."""
        from app.services.health_score_service import calculate_health_score

        user_id = _create_user(sync_session, "sr-scope-sub")
        upload_id = _create_upload(sync_session, user_id)
        _create_profile(
            sync_session,
            user_id,
            period_start=datetime(2026, 2, 1),
            period_end=datetime(2026, 2, 28),
        )
        # Inside window
        _add_transaction(sync_session, user_id, upload_id, 30000, "income", date=datetime(2026, 2, 10))
        _add_transaction(sync_session, user_id, upload_id, -6000, "savings", date=datetime(2026, 2, 15))
        # Outside window — should be ignored by the kind query
        _add_transaction(sync_session, user_id, upload_id, 100000, "income", date=datetime(2026, 1, 5))
        _add_transaction(sync_session, user_id, upload_id, -50000, "savings", date=datetime(2026, 3, 5))
        sync_session.commit()

        score = calculate_health_score(sync_session, user_id)
        # Only the February rows count: 6000 / 30000 → 20.
        assert score.breakdown["savings_ratio"] == 20


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


class TestGetScoreHistory:
    """Tests for get_score_history (async, used by API layer)."""

    @pytest.mark.asyncio
    async def test_returns_scores_ordered_by_date(self, async_session):
        """Returns all scores ordered by calculated_at ascending."""
        from app.services.health_score_service import get_score_history

        user_id = uuid.uuid4()
        user = User(id=user_id, email="hist@test.com", cognito_sub="hist-sub", locale="en")
        async_session.add(user)

        breakdown = {"savings_ratio": 50, "category_diversity": 50, "expense_regularity": 50, "income_coverage": 50}
        s1 = FinancialHealthScore(user_id=user_id, score=40, calculated_at=datetime(2026, 3, 1), breakdown=breakdown)
        s2 = FinancialHealthScore(user_id=user_id, score=60, calculated_at=datetime(2026, 1, 1), breakdown=breakdown)
        s3 = FinancialHealthScore(user_id=user_id, score=75, calculated_at=datetime(2026, 2, 1), breakdown=breakdown)
        async_session.add_all([s1, s2, s3])
        await async_session.commit()

        result = await get_score_history(async_session, user_id)
        assert len(result) == 3
        assert result[0].score == 60  # Jan (earliest)
        assert result[1].score == 75  # Feb
        assert result[2].score == 40  # Mar (latest)

    @pytest.mark.asyncio
    async def test_returns_empty_list_for_new_user(self, async_session):
        """Returns empty list when no scores exist."""
        from app.services.health_score_service import get_score_history

        result = await get_score_history(async_session, uuid.uuid4())
        assert result == []

    @pytest.mark.asyncio
    async def test_returns_only_scores_for_requesting_user(self, async_session):
        """Tenant isolation — only returns scores for the given user."""
        from app.services.health_score_service import get_score_history

        user_a = uuid.uuid4()
        user_b = uuid.uuid4()
        ua = User(id=user_a, email="a@test.com", cognito_sub="a-sub", locale="en")
        ub = User(id=user_b, email="b@test.com", cognito_sub="b-sub", locale="en")
        async_session.add_all([ua, ub])

        breakdown = {"savings_ratio": 50, "category_diversity": 50, "expense_regularity": 50, "income_coverage": 50}
        async_session.add(FinancialHealthScore(user_id=user_a, score=70, calculated_at=datetime(2026, 1, 1), breakdown=breakdown))
        async_session.add(FinancialHealthScore(user_id=user_b, score=80, calculated_at=datetime(2026, 1, 1), breakdown=breakdown))
        await async_session.commit()

        result = await get_score_history(async_session, user_a)
        assert len(result) == 1
        assert result[0].score == 70
