"""Shared fixtures for Story 10.4c tool-handler + session-handler tests."""

from __future__ import annotations

import os
import tempfile
import uuid

import pytest_asyncio
from sqlalchemy import event
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession as SQLModelAsyncSession

from app.models.user import User


@pytest_asyncio.fixture
async def fk_engine():
    """In-memory SQLite with foreign keys ON, full SQLModel.metadata schema."""
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")

    @event.listens_for(engine.sync_engine, "connect")
    def _set_pragma(dbapi_conn, _):  # pragma: no cover — trivial sqlite pragma
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys = ON")
        cur.close()

    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)
    await engine.dispose()
    os.unlink(db_path)


@pytest_asyncio.fixture
async def make_user(fk_engine):
    """Factory returning freshly-created Users bound to the shared engine."""

    created: list[User] = []

    async def _make() -> User:
        async with SQLModelAsyncSession(fk_engine, expire_on_commit=False) as session:
            user = User(
                cognito_sub=f"tool-{uuid.uuid4()}",
                email=f"tool-{uuid.uuid4()}@example.com",
                is_verified=True,
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)
            created.append(user)
            return user

    yield _make
