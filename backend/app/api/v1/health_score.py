import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel
from sqlmodel.ext.asyncio.session import AsyncSession as SQLModelAsyncSession

from app.api.deps import get_current_user_id, get_db
from app.services.health_score_service import get_latest_score, get_score_history

router = APIRouter(prefix="/health-score", tags=["health-score"])


class HealthScoreResponse(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    score: int
    breakdown: dict[str, Any]
    calculated_at: str


@router.get("/history", response_model=list[HealthScoreResponse])
async def get_health_score_history(
    user_id: Annotated[uuid.UUID, Depends(get_current_user_id)],
    session: Annotated[SQLModelAsyncSession, Depends(get_db)],
) -> list[HealthScoreResponse]:
    """Get all health score history for the authenticated user."""
    scores = await get_score_history(session=session, user_id=user_id)
    return [
        HealthScoreResponse(
            score=s.score,
            breakdown=s.breakdown or {},
            calculated_at=s.calculated_at.isoformat() + "Z",
        )
        for s in scores
    ]


@router.get("", response_model=HealthScoreResponse)
async def get_health_score(
    user_id: Annotated[uuid.UUID, Depends(get_current_user_id)],
    session: Annotated[SQLModelAsyncSession, Depends(get_db)],
) -> HealthScoreResponse:
    """Get the latest financial health score for the authenticated user."""
    score = await get_latest_score(session=session, user_id=user_id)

    if not score:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": "HEALTH_SCORE_NOT_FOUND",
                    "message": "No health score found. Upload a statement first.",
                }
            },
        )

    return HealthScoreResponse(
        score=score.score,
        breakdown=score.breakdown or {},
        calculated_at=score.calculated_at.isoformat() + "Z",
    )
