"""Review queue API (Story 11.8 AC #6).

Endpoints (mounted under /api/v1/transactions/review-queue):
  GET    /                      → paginated list of pending (or other status) entries
  GET    /count                 → {count: int} of pending entries (cheap)
  POST   /{id}/resolve          → apply (category, kind) — 400 on matrix violation
  POST   /{id}/dismiss          → mark dismissed — optional {reason}

Per-user isolation: cross-user entry IDs return 404 (not 403) to prevent
ID-probing.
"""
from __future__ import annotations

import uuid
from typing import Annotated, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel
from sqlmodel.ext.asyncio.session import AsyncSession as SQLModelAsyncSession

from app.api.deps import get_current_user_id, get_db
from app.services import review_queue_service as svc

router = APIRouter(
    prefix="/transactions/review-queue", tags=["review-queue"]
)


class ReviewQueueEntryResponse(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    id: str
    transaction_id: str
    description: str
    amount: int
    date: str
    suggested_category: Optional[str] = None
    suggested_kind: Optional[str] = None
    categorization_confidence: float
    created_at: str
    status: Literal["pending", "resolved", "dismissed"]
    currency_code: Optional[int] = None


class ReviewQueueListResponse(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    items: list[ReviewQueueEntryResponse]
    next_cursor: Optional[str] = None
    has_more: bool


class ReviewQueueCountResponse(BaseModel):
    count: int


class ResolveBody(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    category: str
    kind: str


class DismissBody(BaseModel):
    reason: Optional[str] = None


class ResolvedEntryResponse(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    id: str
    transaction_id: str
    status: Literal["pending", "resolved", "dismissed"]
    resolved_category: Optional[str] = None
    resolved_kind: Optional[str] = None
    resolved_at: Optional[str] = None


def _list_item(entry, txn) -> ReviewQueueEntryResponse:
    return ReviewQueueEntryResponse(
        id=str(entry.id),
        transaction_id=str(entry.transaction_id),
        description=txn.description,
        amount=txn.amount,
        date=txn.date.strftime("%Y-%m-%d"),
        suggested_category=entry.suggested_category,
        suggested_kind=entry.suggested_kind,
        categorization_confidence=entry.categorization_confidence,
        created_at=entry.created_at.isoformat() + "Z",
        status=entry.status,
        currency_code=txn.currency_code,
    )


def _entry_response(entry) -> ResolvedEntryResponse:
    return ResolvedEntryResponse(
        id=str(entry.id),
        transaction_id=str(entry.transaction_id),
        status=entry.status,
        resolved_category=entry.resolved_category,
        resolved_kind=entry.resolved_kind,
        resolved_at=entry.resolved_at.isoformat() + "Z" if entry.resolved_at else None,
    )


@router.get("", response_model=ReviewQueueListResponse)
async def list_review_queue(
    user_id: Annotated[uuid.UUID, Depends(get_current_user_id)],
    session: Annotated[SQLModelAsyncSession, Depends(get_db)],
    status_filter: Literal["pending", "resolved", "dismissed"] = Query(
        default="pending", alias="status"
    ),
    limit: int = Query(default=50, ge=1, le=200),
    cursor: Optional[str] = Query(default=None),
) -> ReviewQueueListResponse:
    """List review-queue entries for the authenticated user with keyset pagination.

    Default status is ``pending`` (the actionable subset); ``resolved`` and
    ``dismissed`` are exposed so a future undo action can roundtrip.
    """
    result = await svc.list_pending(
        session, user_id=user_id, limit=limit, cursor=cursor, status=status_filter
    )
    return ReviewQueueListResponse(
        items=[_list_item(i.entry, i.transaction) for i in result.items],
        next_cursor=result.next_cursor,
        has_more=result.has_more,
    )


@router.get("/count", response_model=ReviewQueueCountResponse)
async def review_queue_count(
    user_id: Annotated[uuid.UUID, Depends(get_current_user_id)],
    session: Annotated[SQLModelAsyncSession, Depends(get_db)],
) -> ReviewQueueCountResponse:
    """Cheap count of pending entries for the settings-page badge."""
    n = await svc.count_pending(session, user_id=user_id)
    return ReviewQueueCountResponse(count=n)


@router.post("/{entry_id}/resolve", response_model=ResolvedEntryResponse)
async def resolve_entry(
    entry_id: uuid.UUID,
    body: ResolveBody,
    user_id: Annotated[uuid.UUID, Depends(get_current_user_id)],
    session: Annotated[SQLModelAsyncSession, Depends(get_db)],
) -> ResolvedEntryResponse:
    try:
        entry = await svc.resolve(
            session,
            user_id=user_id,
            entry_id=entry_id,
            category=body.category,
            kind=body.kind,
        )
    except svc.KindCategoryMismatchError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except svc.QueueEntryNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Queue entry not found") from exc
    return _entry_response(entry)


@router.post("/{entry_id}/dismiss", response_model=ResolvedEntryResponse)
async def dismiss_entry(
    entry_id: uuid.UUID,
    user_id: Annotated[uuid.UUID, Depends(get_current_user_id)],
    session: Annotated[SQLModelAsyncSession, Depends(get_db)],
    body: Optional[DismissBody] = None,
) -> ResolvedEntryResponse:
    try:
        entry = await svc.dismiss(
            session,
            user_id=user_id,
            entry_id=entry_id,
            reason=body.reason if body else None,
        )
    except svc.QueueEntryNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Queue entry not found") from exc
    return _entry_response(entry)
