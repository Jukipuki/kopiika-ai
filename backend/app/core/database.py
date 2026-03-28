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
    async with SQLModelAsyncSession(engine) as session:
        yield session


@contextmanager
def get_sync_session() -> Generator[Session, None, None]:
    """Create a synchronous session for Celery worker context."""
    session = Session(sync_engine)
    try:
        yield session
    finally:
        session.close()
