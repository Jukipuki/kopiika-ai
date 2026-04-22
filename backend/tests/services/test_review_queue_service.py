"""Unit tests for review_queue_service (Story 11.8 AC #11 item 2)."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest

import app.models  # noqa: F401  (ensure all SQLModel tables register)
from app.models.transaction import Transaction
from app.models.uncategorized_review_queue import UncategorizedReviewQueue
from app.models.upload import Upload
from app.models.user import User
from app.services import review_queue_service as svc


async def _mk_user(session, email_suffix: str = "a") -> uuid.UUID:
    uid = uuid.uuid4()
    user = User(id=uid, cognito_sub=f"sub-{uuid.uuid4()}", email=f"{uuid.uuid4()}-{email_suffix}@e.co")
    session.add(user)
    await session.commit()
    return uid


async def _mk_upload(session, user_id: uuid.UUID) -> uuid.UUID:
    upid = uuid.uuid4()
    up = Upload(
        id=upid,
        user_id=user_id,
        file_name="f.csv",
        s3_key=f"s3/{uuid.uuid4()}",
        file_size=1,
        mime_type="text/csv",
    )
    session.add(up)
    await session.commit()
    return upid


async def _mk_txn(session, user_id, upload_id, *, date=None, amount=-1000, desc="coffee") -> uuid.UUID:
    txn_id = uuid.uuid4()
    txn = Transaction(
        id=txn_id,
        user_id=user_id,
        upload_id=upload_id,
        date=date or datetime(2026, 4, 21),
        description=desc,
        amount=amount,
        currency_code=980,
        dedup_hash=uuid.uuid4().hex,
        category="uncategorized",
        is_flagged_for_review=True,
        uncategorized_reason="low_confidence",
        transaction_kind="spending",
        confidence_score=0.45,
    )
    session.add(txn)
    await session.commit()
    return txn_id


async def _mk_queue_entry(session, user_id, txn_id, *, created_at=None, suggested_category="shopping", suggested_kind="spending", confidence=0.45) -> uuid.UUID:
    eid = uuid.uuid4()
    entry = UncategorizedReviewQueue(
        id=eid,
        user_id=user_id,
        transaction_id=txn_id,
        categorization_confidence=confidence,
        suggested_category=suggested_category,
        suggested_kind=suggested_kind,
        status="pending",
        created_at=created_at or datetime.now(UTC).replace(tzinfo=None),
    )
    session.add(entry)
    await session.commit()
    return eid


@pytest.mark.asyncio
async def test_list_pending_returns_joined_transaction_context(async_session):
    user_id = await _mk_user(async_session)
    upload_id = await _mk_upload(async_session, user_id)
    t1 = await _mk_txn(async_session, user_id, upload_id, date=datetime(2026, 4, 20))
    t2 = await _mk_txn(async_session, user_id, upload_id, date=datetime(2026, 4, 21))
    await _mk_queue_entry(async_session, user_id, t1)
    await _mk_queue_entry(async_session, user_id, t2)

    result = await svc.list_pending(async_session, user_id=user_id)
    assert len(result.items) == 2
    # Newer date first
    assert result.items[0].transaction.id == t2
    assert result.items[0].entry.suggested_category == "shopping"


@pytest.mark.asyncio
async def test_list_pending_cursor_paginates(async_session):
    user_id = await _mk_user(async_session)
    upload_id = await _mk_upload(async_session, user_id)
    # Three entries across three dates.
    for i, d in enumerate([datetime(2026, 4, 19), datetime(2026, 4, 20), datetime(2026, 4, 21)]):
        t = await _mk_txn(async_session, user_id, upload_id, date=d)
        await _mk_queue_entry(async_session, user_id, t, created_at=datetime(2026, 4, 21, 12, i))

    page1 = await svc.list_pending(async_session, user_id=user_id, limit=2)
    assert len(page1.items) == 2
    assert page1.has_more is True
    assert page1.next_cursor is not None

    page2 = await svc.list_pending(async_session, user_id=user_id, limit=2, cursor=page1.next_cursor)
    assert len(page2.items) == 1
    assert page2.has_more is False


@pytest.mark.asyncio
async def test_list_pending_cross_user_isolation(async_session):
    u1 = await _mk_user(async_session, "1")
    u2 = await _mk_user(async_session, "2")
    up1 = await _mk_upload(async_session, u1)
    up2 = await _mk_upload(async_session, u2)
    t1 = await _mk_txn(async_session, u1, up1)
    t2 = await _mk_txn(async_session, u2, up2)
    await _mk_queue_entry(async_session, u1, t1)
    await _mk_queue_entry(async_session, u2, t2)

    r1 = await svc.list_pending(async_session, user_id=u1)
    r2 = await svc.list_pending(async_session, user_id=u2)
    assert len(r1.items) == 1 and r1.items[0].transaction.id == t1
    assert len(r2.items) == 1 and r2.items[0].transaction.id == t2


@pytest.mark.asyncio
async def test_resolve_updates_both_tables_and_bumps_confidence(async_session):
    user_id = await _mk_user(async_session)
    upload_id = await _mk_upload(async_session, user_id)
    txn_id = await _mk_txn(async_session, user_id, upload_id)
    entry_id = await _mk_queue_entry(async_session, user_id, txn_id)

    updated = await svc.resolve(
        async_session, user_id=user_id, entry_id=entry_id,
        category="groceries", kind="spending",
    )
    assert updated.status == "resolved"
    assert updated.resolved_category == "groceries"
    assert updated.resolved_kind == "spending"
    assert updated.resolved_at is not None

    txn = await async_session.get(Transaction, txn_id)
    assert txn.category == "groceries"
    assert txn.transaction_kind == "spending"
    assert txn.is_flagged_for_review is False
    assert txn.uncategorized_reason is None
    assert txn.confidence_score == 1.0


@pytest.mark.asyncio
async def test_resolve_matrix_violation_raises(async_session):
    user_id = await _mk_user(async_session)
    upload_id = await _mk_upload(async_session, user_id)
    txn_id = await _mk_txn(async_session, user_id, upload_id)
    entry_id = await _mk_queue_entry(async_session, user_id, txn_id)

    with pytest.raises(svc.KindCategoryMismatchError):
        # income × groceries is enum-valid but matrix-invalid.
        await svc.resolve(
            async_session, user_id=user_id, entry_id=entry_id,
            category="groceries", kind="income",
        )


@pytest.mark.asyncio
async def test_resolve_cross_user_raises_not_found(async_session):
    u1 = await _mk_user(async_session, "1")
    u2 = await _mk_user(async_session, "2")
    up1 = await _mk_upload(async_session, u1)
    t = await _mk_txn(async_session, u1, up1)
    entry_id = await _mk_queue_entry(async_session, u1, t)

    with pytest.raises(svc.QueueEntryNotFoundError):
        await svc.resolve(
            async_session, user_id=u2, entry_id=entry_id,
            category="groceries", kind="spending",
        )


@pytest.mark.asyncio
async def test_dismiss_only_touches_queue_row(async_session):
    user_id = await _mk_user(async_session)
    upload_id = await _mk_upload(async_session, user_id)
    txn_id = await _mk_txn(async_session, user_id, upload_id)
    entry_id = await _mk_queue_entry(async_session, user_id, txn_id)

    updated = await svc.dismiss(async_session, user_id=user_id, entry_id=entry_id)
    assert updated.status == "dismissed"

    txn = await async_session.get(Transaction, txn_id)
    # Transaction stays as-is.
    assert txn.category == "uncategorized"
    assert txn.is_flagged_for_review is True
    assert txn.uncategorized_reason == "low_confidence"


@pytest.mark.asyncio
async def test_count_pending(async_session):
    u1 = await _mk_user(async_session, "1")
    u2 = await _mk_user(async_session, "2")
    up1 = await _mk_upload(async_session, u1)
    up2 = await _mk_upload(async_session, u2)
    t1 = await _mk_txn(async_session, u1, up1)
    t2 = await _mk_txn(async_session, u1, up1)
    t3 = await _mk_txn(async_session, u2, up2)
    await _mk_queue_entry(async_session, u1, t1)
    e2 = await _mk_queue_entry(async_session, u1, t2)
    await _mk_queue_entry(async_session, u2, t3)
    # Dismiss one for u1 — should not count.
    await svc.dismiss(async_session, user_id=u1, entry_id=e2)

    assert await svc.count_pending(async_session, u1) == 1
    assert await svc.count_pending(async_session, u2) == 1
