import uuid

from sqlalchemy import case
from sqlmodel import col, func, select
from sqlmodel.ext.asyncio.session import AsyncSession as SQLModelAsyncSession

from app.models.insight import Insight
from app.services.transaction_service import PaginatedResult

# Severity triage order: high=0, medium=1, low=2
severity_order = case(
    (Insight.severity == "high", 0),
    (Insight.severity == "medium", 1),
    else_=2,
)

_SEV_MAP = {"high": 0, "medium": 1, "low": 2}


async def get_insights_for_user(
    session: SQLModelAsyncSession,
    user_id: uuid.UUID,
    cursor: str | None = None,
    page_size: int = 20,
) -> PaginatedResult:
    """Get paginated insights for a user, sorted by severity triage (high first), then created_at DESC."""
    page_size = min(max(page_size, 1), 100)

    # Total count
    count_stmt = select(func.count()).select_from(Insight).where(Insight.user_id == user_id)
    total = (await session.exec(count_stmt)).one()

    # Main query
    stmt = (
        select(Insight)
        .where(Insight.user_id == user_id)
        .order_by(severity_order.asc(), col(Insight.created_at).desc())
    )

    if cursor:
        try:
            cursor_insight = await session.get(Insight, uuid.UUID(cursor))
        except ValueError:
            cursor_insight = None
        if cursor_insight:
            cursor_sev = _SEV_MAP.get(cursor_insight.severity, 2)
            stmt = stmt.where(
                (severity_order > cursor_sev)
                | (
                    (severity_order == cursor_sev)
                    & (col(Insight.created_at) < cursor_insight.created_at)
                )
                | (
                    (severity_order == cursor_sev)
                    & (col(Insight.created_at) == cursor_insight.created_at)
                    & (col(Insight.id) < cursor_insight.id)
                )
            )

    stmt = stmt.limit(page_size + 1)
    rows = (await session.exec(stmt)).all()

    has_more = len(rows) > page_size
    items = list(rows[:page_size])
    next_cursor = str(items[-1].id) if has_more and items else None

    return PaginatedResult(items=items, total=total, next_cursor=next_cursor, has_more=has_more)
