# Read-only — MUST NOT mutate. Any INSERT/UPDATE/DELETE introduction breaks the Epic 10 no-write-tools invariant.
"""``get_transactions`` — return the authenticated user's transactions.

Story 10.4c. User-scoped via the ``user_id`` kwarg threaded from the
handler; the SQL ``WHERE`` always carries ``Transaction.user_id == user_id``
plus optional filters (date range, category, limit).
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field
from sqlmodel.ext.asyncio.session import AsyncSession as SQLModelAsyncSession

from app.services.currency import alpha_for_numeric
from app.services.transaction_service import get_transactions_for_chat


class GetTransactionsInput(BaseModel):
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    category: Optional[str] = None
    limit: int = Field(default=50, ge=1, le=200)


class TransactionRow(BaseModel):
    id: uuid.UUID
    booked_at: date
    description: str
    amount_kopiykas: int
    currency: str
    category_code: Optional[str] = None
    transaction_kind: Optional[str] = None


class GetTransactionsOutput(BaseModel):
    rows: list[TransactionRow]
    row_count: int
    truncated: bool


def _currency_str(numeric_code: int) -> str:
    # Map ISO 4217 numeric to alpha (e.g. 980 → "UAH"); fall back to str(int)
    # for codes not in the central map. Numeric strings are still valid JSON
    # and the model will not confuse them with locale text.
    alpha = alpha_for_numeric(numeric_code)
    return alpha if alpha else str(numeric_code)


def _coerce_date(value: datetime | date) -> date:
    if isinstance(value, datetime):
        return value.date()
    return value


async def get_transactions_handler(
    *,
    user_id: uuid.UUID,
    db: SQLModelAsyncSession,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    category: Optional[str] = None,
    limit: int = 50,
) -> GetTransactionsOutput:
    """Query the user's transactions with optional filters. Always user-scoped.

    Delegates to ``transaction_service.get_transactions_for_chat`` so the
    SQL lives in the service layer — the handler only shapes the model-
    facing envelope and currency mapping.
    """
    sliced, truncated = await get_transactions_for_chat(
        db,
        user_id,
        start_date=start_date,
        end_date=end_date,
        category=category,
        limit=limit,
    )

    out_rows = [
        TransactionRow(
            id=t.id,
            booked_at=_coerce_date(t.date),
            description=t.description,
            amount_kopiykas=t.amount,
            currency=_currency_str(t.currency_code),
            category_code=t.category,
            transaction_kind=t.transaction_kind,
        )
        for t in sliced
    ]

    return GetTransactionsOutput(
        rows=out_rows,
        row_count=len(out_rows),
        truncated=truncated,
    )
