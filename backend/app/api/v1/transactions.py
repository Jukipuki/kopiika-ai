import uuid
from typing import Annotated, Literal, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel
from sqlmodel.ext.asyncio.session import AsyncSession as SQLModelAsyncSession

from app.api.deps import get_current_user_id, get_db
from app.services.transaction_service import get_flagged_transactions_for_user, get_transactions_for_user

router = APIRouter(prefix="/transactions", tags=["transactions"])


class TransactionResponse(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    id: str
    upload_id: str
    date: str
    description: str
    mcc: Optional[int] = None
    amount: int
    balance: Optional[int] = None
    currency_code: int
    created_at: str


class TransactionListResponse(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    items: list[TransactionResponse]
    total: int
    next_cursor: Optional[str] = None
    has_more: bool


class FlaggedTransactionResponse(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    id: str
    upload_id: str
    date: str
    description: str
    amount: int
    category: str
    uncategorized_reason: Optional[Literal["low_confidence", "parse_failure", "llm_unavailable"]] = None


@router.get("/flagged", response_model=list[FlaggedTransactionResponse])
async def list_flagged_transactions(
    user_id: Annotated[uuid.UUID, Depends(get_current_user_id)],
    session: Annotated[SQLModelAsyncSession, Depends(get_db)],
) -> list[FlaggedTransactionResponse]:
    """List all flagged (uncategorized) transactions for the authenticated user."""
    txns = await get_flagged_transactions_for_user(session=session, user_id=user_id)
    return [
        FlaggedTransactionResponse(
            id=str(txn.id),
            upload_id=str(txn.upload_id),
            date=txn.date.strftime("%Y-%m-%d"),
            description=txn.description,
            amount=txn.amount,
            category=txn.category or "uncategorized",
            uncategorized_reason=txn.uncategorized_reason,
        )
        for txn in txns
    ]


@router.get("", response_model=TransactionListResponse)
async def list_transactions(
    user_id: Annotated[uuid.UUID, Depends(get_current_user_id)],
    session: Annotated[SQLModelAsyncSession, Depends(get_db)],
    cursor: Optional[str] = Query(default=None),
    page_size: int = Query(default=20, ge=1, le=100, alias="pageSize"),
) -> TransactionListResponse:
    """List all transactions for the authenticated user with cursor-based pagination."""
    result = await get_transactions_for_user(
        session=session,
        user_id=user_id,
        cursor=cursor,
        page_size=page_size,
    )

    items = [
        TransactionResponse(
            id=str(txn.id),
            upload_id=str(txn.upload_id),
            date=txn.date.strftime("%Y-%m-%d"),
            description=txn.description,
            mcc=txn.mcc,
            amount=txn.amount,
            balance=txn.balance,
            currency_code=txn.currency_code,
            created_at=txn.created_at.isoformat() + "Z",
        )
        for txn in result.items
    ]

    return TransactionListResponse(
        items=items,
        total=result.total,
        next_cursor=result.next_cursor,
        has_more=result.has_more,
    )
