from collections.abc import AsyncGenerator, Generator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool
from sqlmodel import Session
from sqlmodel.ext.asyncio.session import AsyncSession as SQLModelAsyncSession

from app.core.config import settings

engine = create_async_engine(settings.DATABASE_URL, echo=False)

sync_engine = create_engine(settings.SYNC_DATABASE_URL, poolclass=NullPool)


async def init_db() -> None:
    """Initialize the database engine.

    Schema creation is managed by Alembic migrations (alembic upgrade head).
    """


async def get_session() -> AsyncGenerator[SQLModelAsyncSession, None]:
    # expire_on_commit=False is the standard FastAPI + SQLAlchemy-async
    # recommendation: the default (True) expires every ORM-bound attribute
    # on every commit, and any subsequent attribute access then triggers a
    # synchronous lazy-load — which under asyncpg surfaces as
    # `MissingGreenlet: greenlet_spawn has not been called`. Endpoints that
    # genuinely need fresh server-side values (trigger-defaulted columns,
    # ON UPDATE timestamps) must call `await session.refresh(obj)` explicitly;
    # the codebase already follows this pattern in services that need it
    # (auth, review_queue, upload, profile, health_score).
    async with SQLModelAsyncSession(
        engine, expire_on_commit=False
    ) as session:
        yield session


@contextmanager
def get_sync_session() -> Generator[Session, None, None]:
    """Create a synchronous session for Celery worker context."""
    session = Session(sync_engine)
    try:
        yield session
    finally:
        session.close()
