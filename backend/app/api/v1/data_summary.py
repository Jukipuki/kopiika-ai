import uuid
from datetime import datetime
from typing import Annotated, Any, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel
from sqlalchemy import func
from sqlalchemy import select as sa_select
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession as SQLModelAsyncSession

from app.api.deps import get_current_user_id, get_db
from app.models.consent import UserConsent
from app.models.financial_health_score import FinancialHealthScore
from app.models.financial_profile import FinancialProfile
from app.models.insight import Insight
from app.models.transaction import Transaction
from app.models.upload import Upload

router = APIRouter(prefix="/users/me", tags=["user-data"])


class TransactionDateRange(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    earliest: datetime
    latest: datetime


class FinancialProfileSummary(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    total_income: int
    total_expenses: int
    category_totals: dict[str, Any]


class HealthScoreEntry(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    score: int
    calculated_at: datetime


class ConsentRecord(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    consent_type: str
    granted_at: datetime


class DataSummaryResponse(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    upload_count: int
    transaction_count: int
    transaction_date_range: Optional[TransactionDateRange]
    categories_detected: list[str]
    insight_count: int
    financial_profile: Optional[FinancialProfileSummary]
    health_score_history: list[HealthScoreEntry]
    consent_records: list[ConsentRecord]


@router.get("/data-summary", response_model=DataSummaryResponse)
async def get_data_summary(
    user_id: Annotated[uuid.UUID, Depends(get_current_user_id)],
    session: Annotated[SQLModelAsyncSession, Depends(get_db)],
) -> DataSummaryResponse:
    # Upload count
    upload_result = await session.exec(
        sa_select(func.count()).select_from(Upload).where(Upload.user_id == user_id)
    )
    upload_count = upload_result.scalar_one()

    # Transaction count + date range
    tx_result = await session.exec(
        sa_select(
            func.count(),
            func.min(Transaction.date),
            func.max(Transaction.date),
        ).where(Transaction.user_id == user_id)
    )
    tx_row = tx_result.one()
    transaction_count = tx_row[0]
    tx_date_range = None
    if tx_row[1] is not None:
        tx_date_range = TransactionDateRange(earliest=tx_row[1], latest=tx_row[2])

    # Distinct categories
    cat_result = await session.exec(
        sa_select(Transaction.category)
        .where(Transaction.user_id == user_id, Transaction.category.is_not(None))
        .distinct()
    )
    categories_detected = sorted(cat_result.scalars().all())

    # Insight count
    insight_result = await session.exec(
        sa_select(func.count()).select_from(Insight).where(Insight.user_id == user_id)
    )
    insight_count = insight_result.scalar_one()

    # Latest financial profile
    profile_result = await session.exec(
        select(FinancialProfile)
        .where(FinancialProfile.user_id == user_id)
        .order_by(FinancialProfile.updated_at.desc())
        .limit(1)
    )
    profile = profile_result.first()
    financial_profile = None
    if profile:
        financial_profile = FinancialProfileSummary(
            total_income=profile.total_income,
            total_expenses=profile.total_expenses,
            category_totals=profile.category_totals,
        )

    # Health score history (most recent 100)
    hs_result = await session.exec(
        select(FinancialHealthScore)
        .where(FinancialHealthScore.user_id == user_id)
        .order_by(FinancialHealthScore.calculated_at.asc())
        .limit(100)
    )
    health_score_history = [
        HealthScoreEntry(score=s.score, calculated_at=s.calculated_at)
        for s in hs_result.all()
    ]

    # Consent records (most recent 100)
    consent_result = await session.exec(
        select(UserConsent)
        .where(UserConsent.user_id == user_id)
        .order_by(UserConsent.granted_at.desc())
        .limit(100)
    )
    consent_records = [
        ConsentRecord(consent_type=c.consent_type, granted_at=c.granted_at)
        for c in consent_result.all()
    ]

    return DataSummaryResponse(
        upload_count=upload_count,
        transaction_count=transaction_count,
        transaction_date_range=tx_date_range,
        categories_detected=categories_detected,
        insight_count=insight_count,
        financial_profile=financial_profile,
        health_score_history=health_score_history,
        consent_records=consent_records,
    )
