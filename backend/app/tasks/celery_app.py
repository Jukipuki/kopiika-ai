from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "kopiika",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=120,
    task_soft_time_limit=90,
    # Worker concurrency: default prefork pool, concurrency=2 for dev
)

celery_app.autodiscover_tasks(["app.tasks"])
