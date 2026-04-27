import uuid
from datetime import datetime
from typing import Annotated, Any, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel
from sqlalchemy import case, func
from sqlalchemy import select as sa_select
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession as SQLModelAsyncSession

from app.api.deps import get_current_user_id, get_db
from app.models.chat_message import ChatMessage
from app.models.chat_session import ChatSession
from app.models.consent import UserConsent
from app.models.feedback import CardFeedback
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


class ChatActivityRange(BaseModel):
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
    # Mutually-exclusive event timestamps (Story 10.1a H1 fix): grant rows
    # have ``granted_at`` set and ``revoked_at`` null; revoke rows have
    # ``granted_at`` null and ``revoked_at`` set. Clients can discriminate
    # event type from which field is populated.
    granted_at: datetime | None = None
    revoked_at: datetime | None = None


class FeedbackVoteCounts(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    up: int
    down: int


class FreeTextFeedbackEntry(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    card_id: uuid.UUID
    free_text: str
    feedback_source: str
    created_at: datetime


class FeedbackSummary(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    vote_counts: FeedbackVoteCounts
    issue_report_count: int
    free_text_entries: list[FreeTextFeedbackEntry]
    # feedback_responses table is introduced by Story 7.7 (Layer 3 milestone cards).
    # Until it exists, we return an empty list so AC #4 ("graceful empty list if
    # table/rows absent") holds and the API contract stays stable.
    feedback_responses: list[dict[str, Any]] = []


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
    feedback_summary: FeedbackSummary
    # Story 10.10 — chat-history footprint for FR35 ("view what data we hold").
    # Counts include `tool`-role rows (forensic data is still data we hold);
    # the transcript GET filters them out for user-facing display.
    chat_session_count: int = 0
    chat_message_count: int = 0
    chat_activity_range: Optional[ChatActivityRange] = None


@router.get("/data-summary", response_model=DataSummaryResponse)
async def get_data_summary(
    user_id: Annotated[uuid.UUID, Depends(get_current_user_id)],
    session: Annotated[SQLModelAsyncSession, Depends(get_db)],
) -> DataSummaryResponse:
    """Aggregated user data summary for the /onboarding and settings screens.

    `financial_profile` fields (`total_income` / `total_expenses` /
    `category_totals`) reflect kind-based aggregates (spending / income) since
    Story 4.10 — same passthrough, tighter semantics.
    """
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

    # Consent records (most recent 100). Revoke rows carry granted_at=NULL;
    # sort by event-time = COALESCE(granted_at, revoked_at) so grants and
    # revokes interleave chronologically.
    consent_event_time = func.coalesce(UserConsent.granted_at, UserConsent.revoked_at)
    consent_result = await session.exec(
        select(UserConsent)
        .where(UserConsent.user_id == user_id)
        .order_by(consent_event_time.desc(), UserConsent.id.desc())
        .limit(100)
    )
    consent_records = [
        ConsentRecord(
            consent_type=c.consent_type,
            granted_at=c.granted_at,
            revoked_at=c.revoked_at,
        )
        for c in consent_result.all()
    ]

    # Feedback vote counts (card_vote source only, up/down in one query)
    vote_result = await session.exec(
        sa_select(
            func.sum(case((CardFeedback.vote == "up", 1), else_=0)),
            func.sum(case((CardFeedback.vote == "down", 1), else_=0)),
        ).where(
            CardFeedback.user_id == user_id,
            CardFeedback.feedback_source == "card_vote",
        )
    )
    vote_row = vote_result.one()
    vote_counts = FeedbackVoteCounts(
        up=vote_row[0] or 0,
        down=vote_row[1] or 0,
    )

    # Issue report count
    issue_result = await session.exec(
        sa_select(func.count()).select_from(CardFeedback).where(
            CardFeedback.user_id == user_id,
            CardFeedback.feedback_source == "issue_report",
        )
    )
    issue_report_count = issue_result.scalar_one()

    # Free-text entries — capped at most recent 100 to bound response size
    # (CardFeedback.free_text has no max_length enforced on the model; see TD entry).
    ft_result = await session.exec(
        select(CardFeedback)
        .where(
            CardFeedback.user_id == user_id,
            CardFeedback.free_text.is_not(None),
        )
        .order_by(CardFeedback.created_at.desc())
        .limit(100)
    )
    free_text_entries = [
        FreeTextFeedbackEntry(
            card_id=row.card_id,
            free_text=row.free_text,
            feedback_source=row.feedback_source,
            created_at=row.created_at,
        )
        for row in ft_result.all()
    ]

    feedback_summary = FeedbackSummary(
        vote_counts=vote_counts,
        issue_report_count=issue_report_count,
        free_text_entries=free_text_entries,
    )

    # Chat-history footprint (Story 10.10).
    chat_sess_result = await session.exec(
        sa_select(
            func.count(),
            func.min(ChatSession.last_active_at),
            func.max(ChatSession.last_active_at),
        ).where(ChatSession.user_id == user_id)
    )
    chat_sess_row = chat_sess_result.one()
    chat_session_count = int(chat_sess_row[0] or 0)
    chat_activity_range = None
    if chat_sess_row[1] is not None:
        chat_activity_range = ChatActivityRange(
            earliest=chat_sess_row[1], latest=chat_sess_row[2]
        )

    chat_msg_result = await session.exec(
        sa_select(func.count())
        .select_from(ChatMessage)
        .join(ChatSession, ChatMessage.session_id == ChatSession.id)
        .where(ChatSession.user_id == user_id)
    )
    chat_message_count = int(chat_msg_result.scalar_one() or 0)

    return DataSummaryResponse(
        upload_count=upload_count,
        transaction_count=transaction_count,
        transaction_date_range=tx_date_range,
        categories_detected=categories_detected,
        insight_count=insight_count,
        financial_profile=financial_profile,
        health_score_history=health_score_history,
        consent_records=consent_records,
        feedback_summary=feedback_summary,
        chat_session_count=chat_session_count,
        chat_message_count=chat_message_count,
        chat_activity_range=chat_activity_range,
    )
