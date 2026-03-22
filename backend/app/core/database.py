from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession as SQLModelAsyncSession

from app.core.config import settings

engine = create_async_engine(settings.DATABASE_URL, echo=False)


async def init_db() -> None:
    """Initialize the database engine.

    Schema creation is managed by Alembic migrations (alembic upgrade head).
    """


async def get_session() -> AsyncGenerator[SQLModelAsyncSession, None]:
    async with SQLModelAsyncSession(engine) as session:
        yield session
