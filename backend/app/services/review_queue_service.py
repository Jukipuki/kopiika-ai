"""Review queue service for low-confidence categorizations (Story 11.8).

Users resolve (apply a category) or dismiss queue entries produced at
persist-time for transactions categorized with confidence < 0.6. Per-user
isolation is strict: a cross-user entry_id raises QueueEntryNotFoundError
(404), never 403, to prevent ID-probing.

INVARIANT — queue/transaction drift
-----------------------------------
A pending queue row asserts "this transaction is still low-confidence
uncategorized". Any code path that changes a transaction's category/kind
OUTSIDE ``resolve()`` below (future bulk-edit endpoint, re-run-
categorization feature, SQL backfill) MUST also flip any matching pending
queue row to ``status='dismissed'`` or the queue accumulates stale
"review me" entries pointing at already-categorized transactions.

Today the pipeline is the only writer; dedup on re-entry is handled in
``processing_tasks._existing_queue_txn_ids`` (covers ``resume_upload``).
See TD-065 for the partial-unique-index hardening.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Optional

from sqlmodel import col, func, select
from sqlmodel.ext.asyncio.session import AsyncSession as SQLModelAsyncSession

from app.agents.categorization.mcc_mapping import validate_kind_category
from app.models.transaction import Transaction
from app.models.uncategorized_review_queue import UncategorizedReviewQueue


class KindCategoryMismatchError(Exception):
    """Raised when (kind, category) violates the Story 11.2 compatibility matrix."""


class QueueEntryNotFoundError(Exception):
    """Raised when a queue entry does not exist for the given user.

    Returned as HTTP 404 (never 403) to prevent cross-user ID enumeration.
    """


@dataclass
class QueueEntryWithTransaction:
    entry: UncategorizedReviewQueue
    transaction: Transaction


@dataclass
class PaginatedQueueResult:
    items: list[QueueEntryWithTransaction]
    next_cursor: Optional[str]
    has_more: bool


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


async def list_pending(
    session: SQLModelAsyncSession,
    user_id: uuid.UUID,
    limit: int = 50,
    cursor: Optional[str] = None,
    status: str = "pending",
) -> PaginatedQueueResult:
    """List queue entries joined to their transactions.

    Ordered by `transactions.date DESC, uncategorized_review_queue.created_at DESC`.
    Cursor = queue entry UUID (same shape as transaction_service).
    """
    limit = min(max(limit, 1), 200)

    # Pull the queue rows with their joined transaction date as an ordering
    # column. We query the queue entity only (avoids sqlmodel async quirks
    # when selecting two entities at once), then batch-fetch the transactions.
    stmt = (
        select(UncategorizedReviewQueue)
        .join(
            Transaction,
            col(Transaction.id) == col(UncategorizedReviewQueue.transaction_id),
        )
        .where(
            UncategorizedReviewQueue.user_id == user_id,
            UncategorizedReviewQueue.status == status,
        )
        .order_by(
            col(Transaction.date).desc(),
            col(UncategorizedReviewQueue.created_at).desc(),
            col(UncategorizedReviewQueue.id).desc(),
        )
    )

    if cursor:
        try:
            cursor_entry = await session.get(
                UncategorizedReviewQueue, uuid.UUID(cursor)
            )
        except ValueError:
            cursor_entry = None
        if cursor_entry and cursor_entry.user_id == user_id:
            cursor_txn = await session.get(
                Transaction, cursor_entry.transaction_id
            )
            if cursor_txn:
                stmt = stmt.where(
                    (col(Transaction.date) < cursor_txn.date)
                    | (
                        (col(Transaction.date) == cursor_txn.date)
                        & (
                            col(UncategorizedReviewQueue.created_at)
                            < cursor_entry.created_at
                        )
                    )
                    | (
                        (col(Transaction.date) == cursor_txn.date)
                        & (
                            col(UncategorizedReviewQueue.created_at)
                            == cursor_entry.created_at
                        )
                        & (col(UncategorizedReviewQueue.id) < cursor_entry.id)
                    )
                )

    stmt = stmt.limit(limit + 1)
    entries = list((await session.exec(stmt)).all())

    has_more = len(entries) > limit
    entries = entries[:limit]

    # Batch-fetch transactions for the page.
    txn_ids = [e.transaction_id for e in entries]
    txn_map: dict[uuid.UUID, Transaction] = {}
    if txn_ids:
        txn_stmt = select(Transaction).where(col(Transaction.id).in_(txn_ids))
        for t in (await session.exec(txn_stmt)).all():
            txn_map[t.id] = t

    items = [
        QueueEntryWithTransaction(entry=e, transaction=txn_map[e.transaction_id])
        for e in entries
        if e.transaction_id in txn_map
    ]
    next_cursor = str(items[-1].entry.id) if has_more and items else None
    return PaginatedQueueResult(items=items, next_cursor=next_cursor, has_more=has_more)


async def count_pending(
    session: SQLModelAsyncSession, user_id: uuid.UUID
) -> int:
    """Fast count of pending queue entries for the settings-page badge."""
    stmt = (
        select(func.count())
        .select_from(UncategorizedReviewQueue)
        .where(
            UncategorizedReviewQueue.user_id == user_id,
            UncategorizedReviewQueue.status == "pending",
        )
    )
    return int((await session.exec(stmt)).one())


async def _get_entry_for_user(
    session: SQLModelAsyncSession,
    user_id: uuid.UUID,
    entry_id: uuid.UUID,
) -> UncategorizedReviewQueue:
    entry = await session.get(UncategorizedReviewQueue, entry_id)
    if entry is None or entry.user_id != user_id:
        raise QueueEntryNotFoundError(str(entry_id))
    return entry


async def resolve(
    session: SQLModelAsyncSession,
    user_id: uuid.UUID,
    entry_id: uuid.UUID,
    category: str,
    kind: str,
) -> UncategorizedReviewQueue:
    """Apply a user-provided (category, kind) to both the queue row and its transaction.

    Validates against the kind×category matrix (Story 11.2). On success:
      - transactions: category, transaction_kind updated; flagged cleared;
        uncategorized_reason cleared; confidence_score bumped to 1.0
        (user correction is ground truth).
      - queue row: status='resolved', resolved_at=now, resolved_{category,kind}.
    """
    if not validate_kind_category(kind, category):
        raise KindCategoryMismatchError(f"Invalid kind/category pair: ({kind}, {category})")

    entry = await _get_entry_for_user(session, user_id, entry_id)
    txn = await session.get(Transaction, entry.transaction_id)
    if txn is None or txn.user_id != user_id:
        # Defensive: transaction should exist if queue row FK is valid.
        raise QueueEntryNotFoundError(str(entry_id))

    txn.category = category
    txn.transaction_kind = kind
    txn.is_flagged_for_review = False
    txn.uncategorized_reason = None
    txn.confidence_score = 1.0

    entry.status = "resolved"
    entry.resolved_at = _utcnow()
    entry.resolved_category = category
    entry.resolved_kind = kind

    session.add(txn)
    session.add(entry)
    await session.commit()
    await session.refresh(entry)
    return entry


async def dismiss(
    session: SQLModelAsyncSession,
    user_id: uuid.UUID,
    entry_id: uuid.UUID,
    reason: Optional[str] = None,  # noqa: ARG001  (reserved for future observability)
) -> UncategorizedReviewQueue:
    """Mark a queue entry dismissed without touching the transaction.

    Dismiss is NOT a resolution — ``resolved_at`` stays null. "When was it
    dismissed?" isn't surfaced by the UI today and would warrant its own
    column if it ever is. Keeping ``resolved_at`` strictly for the resolve
    path makes "% resolved" / "% dismissed" analytics trivial.
    """
    entry = await _get_entry_for_user(session, user_id, entry_id)
    entry.status = "dismissed"
    session.add(entry)
    await session.commit()
    await session.refresh(entry)
    return entry
