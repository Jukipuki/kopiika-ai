"""Tests for ProfileService (Story 4.4, 4.7)."""
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

from app.models.financial_profile import FinancialProfile
from app.models.transaction import Transaction
from app.models.upload import Upload
from app.models.user import User


def _utcnow():
    return datetime.now(UTC).replace(tzinfo=None)


# ==================== Fixtures ====================


@pytest_asyncio.fixture
async def profile_async_engine():
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
async def profile_async_session(profile_async_engine) -> SQLModelAsyncSession:
    async with SQLModelAsyncSession(profile_async_engine) as session:
        yield session


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


def _create_user_sync(session: Session, cognito_sub: str = "test-sub"):
    user_id = uuid.uuid4()
    user = User(id=user_id, email=f"{cognito_sub}@test.com", cognito_sub=cognito_sub, locale="en")
    session.add(user)
    session.flush()
    return user_id


def _create_upload_sync(session: Session, user_id: uuid.UUID):
    upload_id = uuid.uuid4()
    upload = Upload(
        id=upload_id, user_id=user_id, file_name="test.csv",
        s3_key=f"{user_id}/test.csv", file_size=100,
        mime_type="text/csv", detected_format="monobank",
    )
    session.add(upload)
    session.flush()
    return upload_id


def _create_transaction_sync(
    session: Session,
    user_id: uuid.UUID,
    upload_id: uuid.UUID,
    amount: int,
    category: str | None = None,
    date: datetime | None = None,
):
    txn = Transaction(
        user_id=user_id,
        upload_id=upload_id,
        date=date or _utcnow(),
        description="Test transaction",
        amount=amount,
        dedup_hash=uuid.uuid4().hex,
        category=category,
    )
    session.add(txn)
    session.flush()
    return txn


# ==================== Service Unit Tests ====================


class TestBuildOrUpdateProfile:
    """Unit tests for build_or_update_profile."""

    def test_creates_profile_from_transactions(self, sync_session):
        """Profile is created from user transactions with correct aggregation."""
        from app.services.profile_service import build_or_update_profile

        user_id = _create_user_sync(sync_session, "profile-create-sub")
        upload_id = _create_upload_sync(sync_session, user_id)

        _create_transaction_sync(sync_session, user_id, upload_id, amount=50000, category="salary",
                                 date=datetime(2026, 1, 15))
        _create_transaction_sync(sync_session, user_id, upload_id, amount=-15000, category="food",
                                 date=datetime(2026, 1, 20))
        _create_transaction_sync(sync_session, user_id, upload_id, amount=-5000, category="transport",
                                 date=datetime(2026, 1, 25))
        sync_session.commit()

        profile = build_or_update_profile(sync_session, user_id)

        assert profile.total_income == 50000
        assert profile.total_expenses == -20000
        assert profile.category_totals["salary"] == 50000
        assert profile.category_totals["food"] == -15000
        assert profile.category_totals["transport"] == -5000
        assert profile.period_start == datetime(2026, 1, 15)
        assert profile.period_end == datetime(2026, 1, 25)

    def test_updates_existing_profile(self, sync_session):
        """Second call recalculates from all transactions (upsert)."""
        from app.services.profile_service import build_or_update_profile

        user_id = _create_user_sync(sync_session, "profile-update-sub")
        upload_id = _create_upload_sync(sync_session, user_id)

        _create_transaction_sync(sync_session, user_id, upload_id, amount=10000, category="salary")
        sync_session.commit()

        profile1 = build_or_update_profile(sync_session, user_id)
        assert profile1.total_income == 10000

        # Add more transactions (simulating second upload)
        upload_id2 = _create_upload_sync(sync_session, user_id)
        _create_transaction_sync(sync_session, user_id, upload_id2, amount=20000, category="salary")
        _create_transaction_sync(sync_session, user_id, upload_id2, amount=-8000, category="food")
        sync_session.commit()

        profile2 = build_or_update_profile(sync_session, user_id)

        # Should be recalculated from ALL transactions
        assert profile2.total_income == 30000
        assert profile2.total_expenses == -8000
        assert profile2.id == profile1.id  # Same profile row updated

    def test_empty_transactions(self, sync_session):
        """Profile created with zero values when no transactions exist."""
        from app.services.profile_service import build_or_update_profile

        user_id = _create_user_sync(sync_session, "profile-empty-sub")
        sync_session.commit()

        profile = build_or_update_profile(sync_session, user_id)

        assert profile.total_income == 0
        assert profile.total_expenses == 0
        assert profile.category_totals == {}
        assert profile.period_start is None
        assert profile.period_end is None

    def test_uncategorized_transactions(self, sync_session):
        """Transactions without category are grouped as 'uncategorized'."""
        from app.services.profile_service import build_or_update_profile

        user_id = _create_user_sync(sync_session, "profile-uncat-sub")
        upload_id = _create_upload_sync(sync_session, user_id)

        _create_transaction_sync(sync_session, user_id, upload_id, amount=-5000, category=None)
        _create_transaction_sync(sync_session, user_id, upload_id, amount=-3000, category=None)
        sync_session.commit()

        profile = build_or_update_profile(sync_session, user_id)

        assert profile.category_totals["uncategorized"] == -8000

    def test_mixed_categories(self, sync_session):
        """Multiple categories aggregated correctly."""
        from app.services.profile_service import build_or_update_profile

        user_id = _create_user_sync(sync_session, "profile-mixed-sub")
        upload_id = _create_upload_sync(sync_session, user_id)

        _create_transaction_sync(sync_session, user_id, upload_id, amount=-10000, category="food")
        _create_transaction_sync(sync_session, user_id, upload_id, amount=-5000, category="food")
        _create_transaction_sync(sync_session, user_id, upload_id, amount=-3000, category="transport")
        _create_transaction_sync(sync_session, user_id, upload_id, amount=80000, category="salary")
        sync_session.commit()

        profile = build_or_update_profile(sync_session, user_id)

        assert profile.category_totals["food"] == -15000
        assert profile.category_totals["transport"] == -3000
        assert profile.category_totals["salary"] == 80000


# ==================== Async Service Tests ====================


class TestGetProfileForUser:
    """Tests for get_profile_for_user (async, used by API layer)."""

    @pytest.mark.asyncio
    async def test_returns_profile(self, profile_async_session):
        """Returns profile when it exists."""
        from app.services.profile_service import get_profile_for_user

        user_id = uuid.uuid4()
        user = User(id=user_id, email="async@test.com", cognito_sub="async-sub", locale="en")
        profile = FinancialProfile(
            user_id=user_id,
            total_income=50000,
            total_expenses=-20000,
            category_totals={"food": -20000},
        )
        profile_async_session.add(user)
        profile_async_session.add(profile)
        await profile_async_session.commit()

        result = await get_profile_for_user(profile_async_session, user_id)
        assert result is not None
        assert result.total_income == 50000
        assert result.total_expenses == -20000

    @pytest.mark.asyncio
    async def test_returns_none_when_no_profile(self, profile_async_session):
        """Returns None when no profile exists for user."""
        from app.services.profile_service import get_profile_for_user

        result = await get_profile_for_user(profile_async_session, uuid.uuid4())
        assert result is None


# ==================== Monthly Comparison Tests (Story 4.7) ====================


async def _create_user_async(session: SQLModelAsyncSession, cognito_sub: str = "test-sub"):
    user_id = uuid.uuid4()
    user = User(id=user_id, email=f"{cognito_sub}@test.com", cognito_sub=cognito_sub, locale="en")
    session.add(user)
    await session.flush()
    return user_id


async def _create_upload_async(session: SQLModelAsyncSession, user_id: uuid.UUID):
    upload_id = uuid.uuid4()
    upload = Upload(
        id=upload_id, user_id=user_id, file_name="test.csv",
        s3_key=f"{user_id}/test.csv", file_size=100,
        mime_type="text/csv", detected_format="monobank",
    )
    session.add(upload)
    await session.flush()
    return upload_id


async def _create_txn_async(
    session: SQLModelAsyncSession,
    user_id: uuid.UUID,
    upload_id: uuid.UUID,
    amount: int,
    category: str | None = None,
    date: datetime | None = None,
):
    txn = Transaction(
        user_id=user_id,
        upload_id=upload_id,
        date=date or _utcnow(),
        description="Test transaction",
        amount=amount,
        dedup_hash=uuid.uuid4().hex,
        category=category,
    )
    session.add(txn)
    await session.flush()
    return txn


class TestGetMonthlyComparison:
    """Tests for get_monthly_comparison (async, Story 4.7)."""

    @pytest.mark.asyncio
    async def test_returns_comparison_for_two_months(self, profile_async_session):
        """Returns correct per-category comparison for 2 months of data."""
        from app.services.profile_service import get_monthly_comparison

        user_id = await _create_user_async(profile_async_session, "comp-2m-sub")
        upload_id = await _create_upload_async(profile_async_session, user_id)

        # February transactions
        await _create_txn_async(profile_async_session, user_id, upload_id, -10000, "food", datetime(2026, 2, 10))
        await _create_txn_async(profile_async_session, user_id, upload_id, -5000, "transport", datetime(2026, 2, 15))

        # March transactions
        await _create_txn_async(profile_async_session, user_id, upload_id, -12000, "food", datetime(2026, 3, 10))
        await _create_txn_async(profile_async_session, user_id, upload_id, -3000, "transport", datetime(2026, 3, 15))

        await profile_async_session.commit()

        result = await get_monthly_comparison(profile_async_session, user_id)
        assert result is not None
        assert result["current_month"] == "2026-03"
        assert result["previous_month"] == "2026-02"
        assert len(result["categories"]) == 2
        assert result["total_current"] == 15000  # abs values
        assert result["total_previous"] == 15000

        # Find food category
        food = next(c for c in result["categories"] if c["category"] == "food")
        assert food["current_amount"] == 12000
        assert food["previous_amount"] == 10000
        assert food["change_percent"] == 20.0

        # Find transport category
        transport = next(c for c in result["categories"] if c["category"] == "transport")
        assert transport["current_amount"] == 3000
        assert transport["previous_amount"] == 5000
        assert transport["change_percent"] == -40.0

    @pytest.mark.asyncio
    async def test_returns_none_for_single_month(self, profile_async_session):
        """Returns None when only one month of data exists."""
        from app.services.profile_service import get_monthly_comparison

        user_id = await _create_user_async(profile_async_session, "comp-1m-sub")
        upload_id = await _create_upload_async(profile_async_session, user_id)

        await _create_txn_async(profile_async_session, user_id, upload_id, -10000, "food", datetime(2026, 3, 10))
        await profile_async_session.commit()

        result = await get_monthly_comparison(profile_async_session, user_id)
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_for_zero_transactions(self, profile_async_session):
        """Returns None when no transactions exist."""
        from app.services.profile_service import get_monthly_comparison

        user_id = await _create_user_async(profile_async_session, "comp-0t-sub")
        await profile_async_session.commit()

        result = await get_monthly_comparison(profile_async_session, user_id)
        assert result is None

    @pytest.mark.asyncio
    async def test_category_in_one_month_only(self, profile_async_session):
        """Category present in only one month treats missing as 0."""
        from app.services.profile_service import get_monthly_comparison

        user_id = await _create_user_async(profile_async_session, "comp-1cat-sub")
        upload_id = await _create_upload_async(profile_async_session, user_id)

        # February: food only
        await _create_txn_async(profile_async_session, user_id, upload_id, -10000, "food", datetime(2026, 2, 10))
        # March: transport only
        await _create_txn_async(profile_async_session, user_id, upload_id, -5000, "transport", datetime(2026, 3, 10))

        await profile_async_session.commit()

        result = await get_monthly_comparison(profile_async_session, user_id)
        assert result is not None

        food = next(c for c in result["categories"] if c["category"] == "food")
        assert food["current_amount"] == 0  # Not in March
        assert food["previous_amount"] == 10000
        assert food["change_percent"] == -100.0

        transport = next(c for c in result["categories"] if c["category"] == "transport")
        assert transport["current_amount"] == 5000
        assert transport["previous_amount"] == 0
        assert transport["change_percent"] == 100.0

    @pytest.mark.asyncio
    async def test_null_category_grouped_as_uncategorized(self, profile_async_session):
        """Transactions with NULL category are grouped as 'uncategorized'."""
        from app.services.profile_service import get_monthly_comparison

        user_id = await _create_user_async(profile_async_session, "comp-uncat-sub")
        upload_id = await _create_upload_async(profile_async_session, user_id)

        await _create_txn_async(profile_async_session, user_id, upload_id, -5000, None, datetime(2026, 2, 10))
        await _create_txn_async(profile_async_session, user_id, upload_id, -8000, None, datetime(2026, 3, 10))

        await profile_async_session.commit()

        result = await get_monthly_comparison(profile_async_session, user_id)
        assert result is not None

        uncat = next(c for c in result["categories"] if c["category"] == "uncategorized")
        assert uncat["current_amount"] == 8000
        assert uncat["previous_amount"] == 5000

    @pytest.mark.asyncio
    async def test_sorted_by_biggest_movers(self, profile_async_session):
        """Categories sorted by absolute change_amount descending."""
        from app.services.profile_service import get_monthly_comparison

        user_id = await _create_user_async(profile_async_session, "comp-sort-sub")
        upload_id = await _create_upload_async(profile_async_session, user_id)

        # February
        await _create_txn_async(profile_async_session, user_id, upload_id, -10000, "food", datetime(2026, 2, 10))
        await _create_txn_async(profile_async_session, user_id, upload_id, -5000, "transport", datetime(2026, 2, 15))
        await _create_txn_async(profile_async_session, user_id, upload_id, -2000, "entertainment", datetime(2026, 2, 20))

        # March - food changed most, entertainment changed least
        await _create_txn_async(profile_async_session, user_id, upload_id, -20000, "food", datetime(2026, 3, 10))
        await _create_txn_async(profile_async_session, user_id, upload_id, -3000, "transport", datetime(2026, 3, 15))
        await _create_txn_async(profile_async_session, user_id, upload_id, -2500, "entertainment", datetime(2026, 3, 20))

        await profile_async_session.commit()

        result = await get_monthly_comparison(profile_async_session, user_id)
        assert result is not None
        assert result["categories"][0]["category"] == "food"  # +10000 change
        assert result["categories"][1]["category"] == "transport"  # -2000 change
        assert result["categories"][2]["category"] == "entertainment"  # +500 change

    @pytest.mark.asyncio
    async def test_excludes_income_transactions(self, profile_async_session):
        """Only expenses (amount < 0) are included in comparison."""
        from app.services.profile_service import get_monthly_comparison

        user_id = await _create_user_async(profile_async_session, "comp-inc-sub")
        upload_id = await _create_upload_async(profile_async_session, user_id)

        # Feb & March expenses
        await _create_txn_async(profile_async_session, user_id, upload_id, -10000, "food", datetime(2026, 2, 10))
        await _create_txn_async(profile_async_session, user_id, upload_id, -12000, "food", datetime(2026, 3, 10))

        # Income transactions (should be excluded)
        await _create_txn_async(profile_async_session, user_id, upload_id, 50000, "salary", datetime(2026, 2, 1))
        await _create_txn_async(profile_async_session, user_id, upload_id, 60000, "salary", datetime(2026, 3, 1))

        await profile_async_session.commit()

        result = await get_monthly_comparison(profile_async_session, user_id)
        assert result is not None
        # Only food should appear (salary is income, excluded)
        assert len(result["categories"]) == 1
        assert result["categories"][0]["category"] == "food"

    @pytest.mark.asyncio
    async def test_cross_year_boundary(self, profile_async_session):
        """Correctly compares Dec vs Jan across year boundary without leaking other months."""
        from app.services.profile_service import get_monthly_comparison

        user_id = await _create_user_async(profile_async_session, "comp-xyr-sub")
        upload_id = await _create_upload_async(profile_async_session, user_id)

        # Dec 2025
        await _create_txn_async(profile_async_session, user_id, upload_id, -10000, "food", datetime(2025, 12, 10))
        # Jan 2026
        await _create_txn_async(profile_async_session, user_id, upload_id, -15000, "food", datetime(2026, 1, 10))
        # Jan 2025 (old data that should NOT leak into comparison)
        await _create_txn_async(profile_async_session, user_id, upload_id, -99000, "food", datetime(2025, 1, 10))

        await profile_async_session.commit()

        result = await get_monthly_comparison(profile_async_session, user_id)
        assert result is not None
        assert result["current_month"] == "2026-01"
        assert result["previous_month"] == "2025-12"

        food = next(c for c in result["categories"] if c["category"] == "food")
        assert food["current_amount"] == 15000
        assert food["previous_amount"] == 10000  # Only Dec 2025, not Jan 2025 leaking in

    @pytest.mark.asyncio
    async def test_tenant_isolation(self, profile_async_session):
        """Only returns data for the requesting user."""
        from app.services.profile_service import get_monthly_comparison

        user_a = await _create_user_async(profile_async_session, "comp-a-sub")
        user_b = await _create_user_async(profile_async_session, "comp-b-sub")
        upload_a = await _create_upload_async(profile_async_session, user_a)
        upload_b = await _create_upload_async(profile_async_session, user_b)

        # User A: 2 months
        await _create_txn_async(profile_async_session, user_a, upload_a, -10000, "food", datetime(2026, 2, 10))
        await _create_txn_async(profile_async_session, user_a, upload_a, -15000, "food", datetime(2026, 3, 10))

        # User B: 1 month only
        await _create_txn_async(profile_async_session, user_b, upload_b, -5000, "food", datetime(2026, 3, 10))

        await profile_async_session.commit()

        result_a = await get_monthly_comparison(profile_async_session, user_a)
        assert result_a is not None
        assert result_a["total_current"] == 15000

        result_b = await get_monthly_comparison(profile_async_session, user_b)
        assert result_b is None  # Only 1 month
