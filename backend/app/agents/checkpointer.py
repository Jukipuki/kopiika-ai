"""PostgreSQL checkpointer for LangGraph pipeline.

Uses langgraph-checkpoint-postgres with psycopg3 for Celery worker context.
"""

from langgraph.checkpoint.postgres import PostgresSaver

from app.core.config import settings


def _get_psycopg_conn_string() -> str:
    """Convert the SQLAlchemy SYNC_DATABASE_URL to a plain postgresql:// URI for psycopg3."""
    url = settings.SYNC_DATABASE_URL
    for prefix in ("postgresql+psycopg2://", "postgresql+psycopg://", "postgresql+asyncpg://"):
        if url.startswith(prefix):
            return "postgresql://" + url[len(prefix):]
    return url


def get_checkpointer() -> PostgresSaver:
    """Create a PostgresSaver connected to the project database.

    The caller is responsible for using it as a context manager:
        with get_checkpointer() as checkpointer:
            graph = build_pipeline(checkpointer=checkpointer)
            graph.invoke(state, config)
    """
    return PostgresSaver.from_conn_string(_get_psycopg_conn_string())
