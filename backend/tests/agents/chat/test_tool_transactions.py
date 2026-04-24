"""Tests for the ``get_transactions`` tool handler (Story 10.4c AC #2 + #12)."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Optional

import pytest
import pytest_asyncio
from sqlmodel.ext.asyncio.session import AsyncSession as SQLModelAsyncSession

from app.agents.chat.tools.transactions_tool import (
    GetTransactionsOutput,
    get_transactions_handler,
)
from app.models.transaction import Transaction
from app.models.upload import Upload


async def _make_upload(db: SQLModelAsyncSession, user_id: uuid.UUID) -> uuid.UUID:
    upload = Upload(
        user_id=user_id,
        file_name="t.csv",
        s3_key=f"k/{uuid.uuid4()}",
        file_size=1,
        mime_type="text/csv",
    )
    db.add(upload)
    await db.commit()
    await db.refresh(upload)
    return upload.id


async def _make_txn(
    db: SQLModelAsyncSession,
    *,
    user_id: uuid.UUID,
    upload_id: uuid.UUID,
    txn_date: date,
    amount: int,
    description: str,
    category: Optional[str] = None,
    currency_code: int = 980,
    transaction_kind: str = "spending",
) -> Transaction:
    t = Transaction(
        user_id=user_id,
        upload_id=upload_id,
        date=datetime.combine(txn_date, datetime.min.time()),
        description=description,
        amount=amount,
        currency_code=currency_code,
        dedup_hash=f"{uuid.uuid4()}",
        category=category,
        transaction_kind=transaction_kind,
    )
    db.add(t)
    await db.commit()
    await db.refresh(t)
    return t


@pytest_asyncio.fixture
async def seeded(fk_engine, make_user):
    """Two users; user A with 10 transactions across categories/months, user B with 5."""
    user_a = await make_user()
    user_b = await make_user()

    async with SQLModelAsyncSession(fk_engine, expire_on_commit=False) as db:
        up_a = await _make_upload(db, user_a.id)
        up_b = await _make_upload(db, user_b.id)

        # User A: 3 Jan (groceries), 4 Feb (dining × 2, groceries × 2), 3 Mar (rent × 3)
        for i in range(3):
            await _make_txn(
                db,
                user_id=user_a.id,
                upload_id=up_a,
                txn_date=date(2026, 1, i + 1),
                amount=-1000,
                description=f"A-groc-jan-{i}",
                category="groceries",
            )
        for i in range(2):
            await _make_txn(
                db,
                user_id=user_a.id,
                upload_id=up_a,
                txn_date=date(2026, 2, i + 1),
                amount=-2000,
                description=f"A-din-feb-{i}",
                category="dining",
            )
        for i in range(2):
            await _make_txn(
                db,
                user_id=user_a.id,
                upload_id=up_a,
                txn_date=date(2026, 2, 10 + i),
                amount=-1500,
                description=f"A-groc-feb-{i}",
                category="groceries",
            )
        for i in range(3):
            await _make_txn(
                db,
                user_id=user_a.id,
                upload_id=up_a,
                txn_date=date(2026, 3, i + 1),
                amount=-50000,
                description=f"A-rent-mar-{i}",
                category="rent",
            )
        # User B: 5 rows
        for i in range(5):
            await _make_txn(
                db,
                user_id=user_b.id,
                upload_id=up_b,
                txn_date=date(2026, 1, i + 1),
                amount=-500,
                description=f"B-{i}",
                category="other",
            )

    return {"user_a": user_a, "user_b": user_b}


@pytest.mark.asyncio
async def test_no_filters_returns_only_owner_transactions(fk_engine, seeded):
    async with SQLModelAsyncSession(fk_engine) as db:
        out = await get_transactions_handler(
            user_id=seeded["user_a"].id, db=db, limit=200
        )
    assert out.row_count == 10
    for row in out.rows:
        assert row.description.startswith("A-")


@pytest.mark.asyncio
async def test_category_filter_narrows(fk_engine, seeded):
    async with SQLModelAsyncSession(fk_engine) as db:
        out = await get_transactions_handler(
            user_id=seeded["user_a"].id, db=db, category="dining", limit=200
        )
    assert out.row_count == 2
    assert all(r.category_code == "dining" for r in out.rows)


@pytest.mark.asyncio
async def test_date_range_inclusive_boundary(fk_engine, seeded):
    async with SQLModelAsyncSession(fk_engine) as db:
        out = await get_transactions_handler(
            user_id=seeded["user_a"].id,
            db=db,
            start_date=date(2026, 2, 1),
            end_date=date(2026, 2, 28),
            limit=200,
        )
    assert out.row_count == 4
    assert all(date(2026, 2, 1) <= r.booked_at <= date(2026, 2, 28) for r in out.rows)


@pytest.mark.asyncio
async def test_limit_cap_sets_truncated(fk_engine, seeded):
    async with SQLModelAsyncSession(fk_engine) as db:
        out = await get_transactions_handler(
            user_id=seeded["user_a"].id, db=db, limit=2
        )
    assert out.row_count == 2
    assert out.truncated is True


@pytest.mark.asyncio
async def test_output_schema_round_trip(fk_engine, seeded):
    async with SQLModelAsyncSession(fk_engine) as db:
        out = await get_transactions_handler(
            user_id=seeded["user_a"].id, db=db, limit=200
        )
    # Round-trip through model_validate: if the handler output drifts from
    # the declared schema, this raises ValidationError.
    GetTransactionsOutput.model_validate(out.model_dump())


@pytest.mark.asyncio
async def test_empty_user_returns_empty_rows(fk_engine, make_user):
    user = await make_user()
    async with SQLModelAsyncSession(fk_engine) as db:
        out = await get_transactions_handler(user_id=user.id, db=db, limit=200)
    assert out.row_count == 0
    assert out.truncated is False
    assert out.rows == []


@pytest.mark.asyncio
async def test_currency_code_maps_to_iso_alpha(fk_engine, make_user):
    user = await make_user()
    async with SQLModelAsyncSession(fk_engine, expire_on_commit=False) as db:
        up = await _make_upload(db, user.id)
        await _make_txn(
            db,
            user_id=user.id,
            upload_id=up,
            txn_date=date(2026, 1, 1),
            amount=-100,
            description="x",
            category=None,
            currency_code=840,  # USD
        )
    async with SQLModelAsyncSession(fk_engine) as db:
        out = await get_transactions_handler(user_id=user.id, db=db, limit=10)
    assert out.rows[0].currency == "USD"
