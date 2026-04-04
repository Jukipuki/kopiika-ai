import uuid
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel
from sqlmodel.ext.asyncio.session import AsyncSession as SQLModelAsyncSession

from app.api.deps import get_current_user_id, get_db
from app.services.insight_service import get_insights_for_user

router = APIRouter(prefix="/insights", tags=["insights"])


class InsightResponse(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    id: str
    upload_id: Optional[str] = None
    headline: str
    key_metric: str
    why_it_matters: str
    deep_dive: str
    severity: str
    category: str
    created_at: str


class InsightListResponse(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    items: list[InsightResponse]
    total: int
    next_cursor: Optional[str] = None
    has_more: bool


@router.get("", response_model=InsightListResponse)
async def list_insights(
    user_id: Annotated[uuid.UUID, Depends(get_current_user_id)],
    session: Annotated[SQLModelAsyncSession, Depends(get_db)],
    cursor: Optional[str] = Query(default=None),
    page_size: int = Query(default=20, ge=1, le=100, alias="pageSize"),
) -> InsightListResponse:
    """List all insights for the authenticated user, sorted by severity triage."""
    result = await get_insights_for_user(
        session=session,
        user_id=user_id,
        cursor=cursor,
        page_size=page_size,
    )

    items = [
        InsightResponse(
            id=str(insight.id),
            upload_id=str(insight.upload_id) if insight.upload_id else None,
            headline=insight.headline,
            key_metric=insight.key_metric,
            why_it_matters=insight.why_it_matters,
            deep_dive=insight.deep_dive,
            severity=insight.severity,
            category=insight.category,
            created_at=insight.created_at.isoformat() + "Z",
        )
        for insight in result.items
    ]

    return InsightListResponse(
        items=items,
        total=result.total,
        next_cursor=result.next_cursor,
        has_more=result.has_more,
    )
