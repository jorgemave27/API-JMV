from __future__ import annotations

"""
CELERY CONFIGURATION - API JMV

Este módulo configura:

✔ Celery Worker (procesamiento async)
✔ Celery Beat (jobs programados)
✔ Redis como broker/backend
✔ Registro explícito de tareas

Arquitectura:

FastAPI
   │
   ├── Celery Worker
   │       └── tareas async (SFTP, notificaciones, etc)
   │
   ├── Celery Beat
   │       └── jobs programados (cron)
   │
   └── Redis
           ├── cache
           ├── sesiones
           └── broker Celery
"""

# ==========================================================
# IMPORTS
# ==========================================================

from celery import Celery
from celery.schedules import crontab

from app.core.config import settings

# ==========================================================
# IMPORTACIÓN DE TAREAS (CRÍTICO)
# ==========================================================
"""
IMPORTANTE:
Celery SOLO registra tareas si son importadas.

Si olvidas importar una tarea:
❌ No aparece en worker
❌ No se ejecuta en beat
"""

from app.tasks.data_retention import ejecutar_retencion_datos
from app.tasks.sftp_integration_task import procesar_archivos_sftp


# ==========================================================
# CREACIÓN DE APP CELERY
# ==========================================================

celery_app = Celery(
    "api_jmv",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)


# ==========================================================
# CONFIGURACIÓN GLOBAL
# ==========================================================

celery_app.conf.update(

    # ------------------------------------------------------
    # SERIALIZACIÓN SEGURA
    # ------------------------------------------------------
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],

    # ------------------------------------------------------
    # TIMEZONE
    # ------------------------------------------------------
    timezone="UTC",
    enable_utc=True,

    # ------------------------------------------------------
    # CONFIABILIDAD
    # ------------------------------------------------------
    task_acks_late=True,          # Evita pérdida de tareas si worker cae
    worker_prefetch_multiplier=1, # Evita duplicados

    # ======================================================
    # CELERY BEAT (CRON JOBS)
    # ======================================================
    beat_schedule={

        # --------------------------------------------------
        # GDPR DATA RETENTION
        # --------------------------------------------------
        "gdpr-data-retention-job": {
            "task": "app.tasks.data_retention.ejecutar_retencion_datos",
            "schedule": crontab(hour=3, minute=0),
        },

        # --------------------------------------------------
        # SFTP LEGACY INTEGRATION
        # --------------------------------------------------
        """
        Este job:

        1. Se conecta al SFTP
        2. Descarga archivos EDI
        3. Los parsea (CSV)
        4. Inserta datos en el sistema
        5. Genera respuesta
        6. Mueve archivos:
           - /procesados
           - /cuarentena (errores)
        """

        "sftp-sync-job": {
            "task": "app.tasks.sftp.process_files",
            "schedule": crontab(minute=0),  # cada hora
        },
    },
)


# ==========================================================
# WRAPPERS DE TAREAS (OPCIONAL PERO BUENA PRÁCTICA)
# ==========================================================

@celery_app.task(name="app.tasks.data_retention.ejecutar_retencion_datos")
def celery_retention_job():
    """
    Wrapper para job de retención de datos.

    Se ejecuta vía Celery Beat diariamente.
    """
    ejecutar_retencion_datos()


@celery_app.task(name="app.tasks.sftp.process_files")
def celery_sftp_job():
    """
    Wrapper para integración SFTP.

    IMPORTANTE:
    - Este wrapper permite ejecutar la tarea desde Celery Beat
    - Internamente delega a la lógica principal
    """
    procesar_archivos_sftp()