import hashlib
import uuid
from dataclasses import dataclass
from datetime import date, datetime, time

from sqlmodel import col, func, select
from sqlmodel.ext.asyncio.session import AsyncSession as SQLModelAsyncSession

from app.models.transaction import Transaction


def compute_dedup_hash(
    user_id: uuid.UUID,
    txn_date: date | datetime,
    amount: int,
    description: str,
) -> str:
    """Compute SHA-256 dedup hash for a transaction.

    Uses normalized f"{user_id}:{date_iso}:{amount_kopiykas}:{description_stripped_lower}"
    to produce a fixed-length fingerprint for duplicate detection.
    """
    date_str = txn_date.strftime("%Y-%m-%d") if isinstance(txn_date, (date, datetime)) else str(txn_date)[:10]
    normalized = f"{user_id}:{date_str}:{amount}:{description.strip().lower()}"
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


@dataclass
class PaginatedResult:
    items: list
    total: int
    next_cursor: str | None
    has_more: bool


async def get_flagged_transactions_for_user(
    session: SQLModelAsyncSession,
    user_id: uuid.UUID,
    limit: int = 100,
) -> list[Transaction]:
    """Return flagged transactions for a user, ordered by date DESC."""
    stmt = (
        select(Transaction)
        .where(Transaction.user_id == user_id, Transaction.is_flagged_for_review == True)  # noqa: E712
        .order_by(col(Transaction.date).desc())
        .limit(limit)
    )
    return list((await session.exec(stmt)).all())


async def get_transactions_for_user(
    session: SQLModelAsyncSession,
    user_id: uuid.UUID,
    cursor: str | None = None,
    page_size: int = 20,
) -> PaginatedResult:
    """Get paginated transactions for a user, sorted by date DESC then created_at DESC.

    Uses cursor-based pagination with the transaction ID.
    """
    page_size = min(max(page_size, 1), 100)

    # Total count
    count_stmt = select(func.count()).select_from(Transaction).where(Transaction.user_id == user_id)
    total = (await session.exec(count_stmt)).one()

    # Main query, ordered by date DESC, created_at DESC
    stmt = (
        select(Transaction)
        .where(Transaction.user_id == user_id)
        .order_by(col(Transaction.date).desc(), col(Transaction.created_at).desc())
    )

    if cursor:
        # Cursor is a transaction ID — fetch the cursor row to get its sort values
        try:
            cursor_txn = await session.get(Transaction, uuid.UUID(cursor))
        except ValueError:
            cursor_txn = None
        if cursor_txn:
            # Seek past the cursor: transactions older than cursor, or same date but created earlier
            stmt = stmt.where(
                (col(Transaction.date) < cursor_txn.date)
                | (
                    (col(Transaction.date) == cursor_txn.date)
                    & (col(Transaction.created_at) < cursor_txn.created_at)
                )
                | (
                    (col(Transaction.date) == cursor_txn.date)
                    & (col(Transaction.created_at) == cursor_txn.created_at)
                    & (col(Transaction.id) < cursor_txn.id)
                )
            )

    # Fetch one extra to determine has_more
    stmt = stmt.limit(page_size + 1)
    rows = (await session.exec(stmt)).all()

    has_more = len(rows) > page_size
    items = list(rows[:page_size])
    next_cursor = str(items[-1].id) if has_more and items else None

    return PaginatedResult(items=items, total=total, next_cursor=next_cursor, has_more=has_more)


async def get_transactions_for_chat(
    session: SQLModelAsyncSession,
    user_id: uuid.UUID,
    *,
    start_date: date | None = None,
    end_date: date | None = None,
    category: str | None = None,
    limit: int = 50,
) -> tuple[list[Transaction], bool]:
    """Return ``(rows, truncated)`` for the chat ``get_transactions`` tool.

    User-scoped by ``user_id`` — the WHERE clause always pins to the caller;
    optional filters (inclusive date range, exact category, row limit) are
    layered on top. Fetches ``limit + 1`` rows so truncation can be reported
    accurately. Ordered by ``date DESC, created_at DESC`` to match the
    cursor-paginated REST path for consistency.

    Owned by the service layer so the chat tool handler does not write raw
    SQL — preserves the Epic 10 invariant that user-data access paths live
    in ``app.services``.
    """
    stmt = (
        select(Transaction)
        .where(Transaction.user_id == user_id)
        .order_by(col(Transaction.date).desc(), col(Transaction.created_at).desc())
    )
    if start_date is not None:
        stmt = stmt.where(Transaction.date >= datetime.combine(start_date, time.min))
    if end_date is not None:
        stmt = stmt.where(Transaction.date <= datetime.combine(end_date, time.max))
    if category is not None:
        stmt = stmt.where(Transaction.category == category)
    stmt = stmt.limit(limit + 1)
    rows = list((await session.exec(stmt)).all())
    truncated = len(rows) > limit
    return rows[:limit], truncated
