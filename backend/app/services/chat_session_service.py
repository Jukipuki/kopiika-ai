"""Chat session service — creates a new ``chat_sessions`` row after checking
that the user holds current ``chat_processing`` consent.

Story 10.1b. Consumed by Story 10.4a (AgentCore session handler) — this
module is a library helper only; no HTTP endpoint, no Celery task, no
AgentCore call ships here. The HTTP translation of
``ChatConsentRequiredError`` lives in Story 10.5's streaming endpoint.
"""
from __future__ import annotations

from sqlmodel.ext.asyncio.session import AsyncSession as SQLModelAsyncSession

from app.core.consent import (
    CONSENT_TYPE_CHAT_PROCESSING,
    CURRENT_CHAT_CONSENT_VERSION,
)
from app.models.chat_session import ChatSession
from app.models.user import User
from app.services import consent_service


class ChatConsentRequiredError(Exception):
    """Raised when ``create_chat_session`` is called without current
    ``chat_processing`` consent. Plain ``Exception`` (not
    ``HTTPException``) — the HTTP translation belongs to Story 10.5.
    """


async def create_chat_session(
    session: SQLModelAsyncSession, user: User
) -> ChatSession:
    """Create a new chat session for ``user`` after verifying current consent.

    Pins ``consent_version_at_creation`` to ``CURRENT_CHAT_CONSENT_VERSION``
    per the Consent Drift Policy. Uses the detached-copy pattern from
    ``consent_service.grant_consent`` so the returned instance's attributes
    remain accessible after commit under the async session.
    """
    status = await consent_service.get_current_consent_status(
        session=session,
        user=user,
        consent_type=CONSENT_TYPE_CHAT_PROCESSING,
        version=CURRENT_CHAT_CONSENT_VERSION,
    )
    if not status["hasCurrentConsent"]:
        raise ChatConsentRequiredError(
            "chat_processing consent is required to create a chat session"
        )

    record = ChatSession(
        user_id=user.id,
        consent_version_at_creation=CURRENT_CHAT_CONSENT_VERSION,
    )
    session.add(record)
    detached = ChatSession(
        id=record.id,
        user_id=record.user_id,
        created_at=record.created_at,
        last_active_at=record.last_active_at,
        consent_version_at_creation=record.consent_version_at_creation,
    )
    await session.commit()
    return detached
