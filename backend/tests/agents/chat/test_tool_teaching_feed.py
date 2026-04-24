"""Tests for the ``get_teaching_feed`` tool handler (Story 10.4c AC #4 + #12)."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta

import pytest
import pytest_asyncio
from sqlmodel.ext.asyncio.session import AsyncSession as SQLModelAsyncSession

from app.agents.chat.tools.teaching_feed_tool import (
    GetTeachingFeedOutput,
    get_teaching_feed_handler,
)
from app.models.feedback import CardFeedback
from app.models.insight import Insight


@pytest_asyncio.fixture
async def seeded(fk_engine, make_user):
    user = await make_user()
    async with SQLModelAsyncSession(fk_engine, expire_on_commit=False) as db:
        # 25 insights, oldest first so newest-DESC ordering is deterministic.
        insight_ids: list[uuid.UUID] = []
        for i in range(25):
            ins = Insight(
                user_id=user.id,
                headline=f"Insight #{i}",
                key_metric="spending",
                why_it_matters="longform body text NEVER returned to chat",
                deep_dive="even more longform text NEVER returned to chat",
                severity="info",
                category="spending",
                card_type="spending_spike" if i % 2 == 0 else "milestone",
                created_at=datetime(2026, 3, 1) + timedelta(days=i),
            )
            db.add(ins)
            await db.flush()
            insight_ids.append(ins.id)
        # 5 thumbs-up, 3 thumbs-down on the first 8 insights.
        for i in range(5):
            db.add(
                CardFeedback(
                    user_id=user.id,
                    card_id=insight_ids[i],
                    card_type="spending_spike",
                    vote="up",
                    feedback_source="card_vote",
                )
            )
        for i in range(5, 8):
            db.add(
                CardFeedback(
                    user_id=user.id,
                    card_id=insight_ids[i],
                    card_type="milestone",
                    vote="down",
                    feedback_source="card_vote",
                )
            )
        await db.commit()
    return user


@pytest.mark.asyncio
async def test_default_limit_returns_20_rows_most_recent_first(fk_engine, seeded):
    async with SQLModelAsyncSession(fk_engine) as db:
        out = await get_teaching_feed_handler(user_id=seeded.id, db=db)
    assert out.row_count == 20
    assert out.truncated is True
    # Most recent is the 25th (zero-indexed 24).
    assert out.rows[0].title == "Insight #24"


@pytest.mark.asyncio
async def test_only_thumbs_up_filters(fk_engine, seeded):
    async with SQLModelAsyncSession(fk_engine) as db:
        out = await get_teaching_feed_handler(
            user_id=seeded.id, db=db, only_thumbs_up=True
        )
    assert out.row_count == 5
    for row in out.rows:
        assert row.user_feedback == "up"


@pytest.mark.asyncio
async def test_body_is_not_returned(fk_engine, seeded):
    async with SQLModelAsyncSession(fk_engine) as db:
        out = await get_teaching_feed_handler(user_id=seeded.id, db=db, limit=5)
    # Row model has only insight_id, card_type, title, delivered_at, user_feedback —
    # no ``why_it_matters`` / ``deep_dive`` leak.
    assert out.rows
    for row in out.rows:
        fields = row.model_dump().keys()
        assert "why_it_matters" not in fields
        assert "deep_dive" not in fields
        assert "key_metric" not in fields


@pytest.mark.asyncio
async def test_output_schema_round_trip(fk_engine, seeded):
    async with SQLModelAsyncSession(fk_engine) as db:
        out = await get_teaching_feed_handler(user_id=seeded.id, db=db, limit=50)
    GetTeachingFeedOutput.model_validate(out.model_dump())
