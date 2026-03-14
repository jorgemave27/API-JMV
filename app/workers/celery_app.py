"""
Configuración central de Celery para la API JMV.

Este módulo:
- Inicializa la app de Celery
- Permite usar Redis en ejecución normal
- Permite usar modo eager + backend en memoria durante tests/build de Docker
- Agenda la rotación automática de API key cada 24 horas
"""

from __future__ import annotations

import os

from celery import Celery

from app.core.config import settings


def _env_bool(name: str, default: str = "false") -> bool:
    """
    Convierte variables de entorno tipo texto a bool.
    """
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


broker_url = os.getenv("CELERY_BROKER_URL", settings.REDIS_URL)
result_backend = os.getenv("CELERY_RESULT_BACKEND", settings.REDIS_URL)

task_always_eager = _env_bool("CELERY_TASK_ALWAYS_EAGER", "false")
task_eager_propagates = _env_bool("CELERY_TASK_EAGER_PROPAGATES", "true")
task_store_eager_result = _env_bool("CELERY_TASK_STORE_EAGER_RESULT", "false")

celery_app = Celery(
    "api_jmv",
    broker=broker_url,
    backend=result_backend,
    include=[
        "app.workers.tasks",
        "app.workers.rotate_api_key_task",
    ],
)

celery_app.conf.update(
    broker_url=broker_url,
    result_backend=result_backend,
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_always_eager=task_always_eager,
    task_eager_propagates=task_eager_propagates,
    task_store_eager_result=task_store_eager_result,
    beat_schedule={
        "rotate-api-key-every-24-hours": {
            "task": "app.workers.rotate_api_key_task.rotate_api_key_task",
            "schedule": 86400.0,
        },
    },
)

celery = celery_app