from __future__ import annotations

"""
Celery configuration for API-JMV.

Este módulo configura:
- Celery worker
- Celery Beat scheduler
- Redis como broker y backend
- Registro de tareas background

Arquitectura actual del proyecto:

FastAPI
   │
   ├── Celery Worker
   │       └── tareas async
   │
   ├── Celery Beat
   │       └── tareas programadas
   │
   └── Redis
           ├── cache
           ├── sessions
           └── celery broker
"""

# ==========================================================
# IMPORTS
# ==========================================================

from celery import Celery
from celery.schedules import crontab

from app.core.config import settings

# ----------------------------------------------------------
# IMPORTAR TAREAS
# ----------------------------------------------------------

# IMPORTANTE:
# Celery necesita importar las tareas para registrarlas.

from app.tasks.data_retention import ejecutar_retencion_datos

# ==========================================================
# CREACIÓN DE APP CELERY
# ==========================================================

celery_app = Celery(
    "api_jmv",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

# ==========================================================
# CONFIGURACIÓN GENERAL
# ==========================================================

celery_app.conf.update(

    # Serialización segura
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],

    # Zona horaria
    timezone="UTC",
    enable_utc=True,

    # Reintentos automáticos
    task_acks_late=True,

    # Evita duplicados si el worker cae
    worker_prefetch_multiplier=1,

    # ======================================================
    # CELERY BEAT (TAREAS PROGRAMADAS)
    # ======================================================

    beat_schedule={

        # --------------------------------------------------
        # TAREA 103
        # Retención automática de datos personales
        # GDPR / LFPDPPP
        # --------------------------------------------------

        "gdpr-data-retention-job": {
            "task": "app.tasks.data_retention.ejecutar_retencion_datos",
            "schedule": crontab(hour=3, minute=0),
        },

    },

)

# ==========================================================
# REGISTRO MANUAL DE TAREAS
# ==========================================================


@celery_app.task(name="app.tasks.data_retention.ejecutar_retencion_datos")
def celery_retention_job():
    """
    Wrapper Celery para ejecutar el job de retención.
    """

    ejecutar_retencion_datos()