"""Tests for the ``get_profile`` tool handler (Story 10.4c AC #3 + #12)."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta

import pytest
import pytest_asyncio
from sqlmodel.ext.asyncio.session import AsyncSession as SQLModelAsyncSession

from app.agents.chat.tools.profile_tool import (
    GetProfileOutput,
    get_profile_handler,
)
from app.models.financial_health_score import FinancialHealthScore
from app.models.financial_profile import FinancialProfile
from app.models.transaction import Transaction
from app.models.upload import Upload


@pytest_asyncio.fixture
async def seeded(fk_engine, make_user):
    user = await make_user()
    async with SQLModelAsyncSession(fk_engine, expire_on_commit=False) as db:
        upload = Upload(
            user_id=user.id,
            file_name="t.csv",
            s3_key=f"k/{uuid.uuid4()}",
            file_size=1,
            mime_type="text/csv",
        )
        db.add(upload)
        await db.commit()
        await db.refresh(upload)

        profile = FinancialProfile(
            user_id=user.id,
            total_income=500000,
            total_expenses=-300000,
            category_totals={
                "groceries": -100000,
                "dining": -80000,
                "rent": -120000,
            },
            period_start=datetime(2026, 1, 1),
            period_end=datetime(2026, 3, 31),
            updated_at=datetime(2026, 3, 31),
        )
        db.add(profile)

        score = FinancialHealthScore(
            user_id=user.id,
            score=75,
            calculated_at=datetime(2026, 3, 31),
            breakdown={
                "savings_ratio": 40,
                "category_diversity": 60,
                "expense_regularity": 80,
                "income_coverage": 20,
            },
        )
        db.add(score)

        # Transactions across two distinct months so get_monthly_comparison
        # returns a real comparison.
        for month in (2, 3):
            for i in range(3):
                db.add(
                    Transaction(
                        user_id=user.id,
                        upload_id=upload.id,
                        date=datetime(2026, month, i + 1),
                        description=f"m{month}-{i}",
                        amount=-10000 * (i + 1),
                        currency_code=980,
                        dedup_hash=f"{uuid.uuid4()}",
                        category="groceries" if i == 0 else "dining",
                        transaction_kind="spending",
                    )
                )
        await db.commit()

    return user


@pytest.mark.asyncio
async def test_default_returns_only_summary(fk_engine, seeded):
    async with SQLModelAsyncSession(fk_engine) as db:
        out = await get_profile_handler(user_id=seeded.id, db=db)
    assert out.summary.monthly_income_kopiykas == 500000
    assert out.summary.monthly_expenses_kopiykas == -300000
    assert out.summary.savings_ratio == 40
    assert out.summary.health_score == 75
    assert out.summary.currency == "UAH"
    assert out.category_breakdown == []
    assert out.monthly_comparison == []


@pytest.mark.asyncio
async def test_category_breakdown_returns_sorted_top_categories(fk_engine, seeded):
    async with SQLModelAsyncSession(fk_engine) as db:
        out = await get_profile_handler(
            user_id=seeded.id, db=db, include_category_breakdown=True
        )
    codes = [r.category_code for r in out.category_breakdown]
    # Sorted descending by amount — rent is the largest at 120000.
    assert codes[0] == "rent"
    assert len(out.category_breakdown) <= 12
    for row in out.category_breakdown:
        assert 0 <= row.share_percent <= 100


@pytest.mark.asyncio
async def test_monthly_comparison_returns_rows(fk_engine, seeded):
    async with SQLModelAsyncSession(fk_engine) as db:
        out = await get_profile_handler(
            user_id=seeded.id, db=db, include_monthly_comparison=True
        )
    # Two months were seeded, so the handler returns up to 2 flat rows.
    assert 1 <= len(out.monthly_comparison) <= 12


@pytest.mark.asyncio
async def test_no_profile_returns_all_none_summary(fk_engine, make_user):
    user = await make_user()
    async with SQLModelAsyncSession(fk_engine) as db:
        out = await get_profile_handler(user_id=user.id, db=db)
    assert out.summary.monthly_income_kopiykas is None
    assert out.summary.monthly_expenses_kopiykas is None
    assert out.summary.savings_ratio is None
    assert out.summary.health_score is None
    assert out.summary.currency == "UAH"
    assert out.summary.as_of is not None
    assert out.category_breakdown == []
    assert out.monthly_comparison == []


@pytest.mark.asyncio
async def test_output_schema_round_trip(fk_engine, seeded):
    async with SQLModelAsyncSession(fk_engine) as db:
        out = await get_profile_handler(
            user_id=seeded.id,
            db=db,
            include_category_breakdown=True,
            include_monthly_comparison=True,
        )
    GetProfileOutput.model_validate(out.model_dump())


# Silence unused-import warnings — timedelta reserved for future enhancements.
_ = timedelta
_ = date
