from __future__ import annotations

from celery import Celery
from celery.schedules import crontab

from app.core.config import settings

celery_app = Celery(
    "api_jmv",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

celery_app.conf.update(
    timezone="America/Mexico_City",
    enable_utc=False,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    imports=("app.workers.tasks",),
    beat_schedule={
        "generar-reporte-stock-bajo-cada-hora": {
            "task": "app.workers.tasks.generar_reporte_stock_bajo",
            "schedule": crontab(minute=0),
        },
    },
)