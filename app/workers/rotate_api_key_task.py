"""
Tarea programada para rotar automáticamente la API key.

Flujo:
- genera una nueva key
- actualiza Redis
- actualiza Vault
- mantiene key anterior por una ventana corta
"""

from __future__ import annotations

from app.core.api_key_manager import api_key_manager
from app.workers.celery_app import celery_app


@celery_app.task(name="app.workers.rotate_api_key_task.rotate_api_key_task")
def rotate_api_key_task() -> dict:
    """
    Ejecuta la rotación automática de API key.
    """
    new_key = api_key_manager.rotate_api_key()

    return {
        "status": "ok",
        "message": "API key rotada exitosamente",
        "new_key_preview": f"{new_key[:6]}...",
    }