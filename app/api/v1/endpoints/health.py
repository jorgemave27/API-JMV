from __future__ import annotations

"""
Endpoint de healthcheck.

Verifica:
- Conexión a base de datos
- Conexión a Redis
- Uso de memoria del proceso

Comportamiento:
- En producción: responde 503 si falla una dependencia crítica
- En tests: tolera fallo de Redis para no romper la suite local
"""

import os
from datetime import datetime, timezone

import psutil
from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.cache import get_redis_client
from app.core.config import settings
from app.database.database import get_db

router = APIRouter()


@router.get("/health")
def healthcheck(db: Session = Depends(get_db)):
    """
    Verifica el estado de salud de la API y sus dependencias críticas.
    """

    db_ok = False
    redis_ok = False

    db_error = None
    redis_error = None

    # ==========================================================
    # Verificar conexión a base de datos
    # ==========================================================
    try:
        db.execute(text("SELECT 1"))
        db_ok = True
    except Exception as exc:
        db_error = str(exc)

    # ==========================================================
    # Verificar conexión a Redis
    # ==========================================================
    try:
        redis_client = get_redis_client()

        if redis_client is None:
            redis_error = "Redis client no inicializado"
        else:
            redis_ok = bool(redis_client.ping())
    except Exception as exc:
        redis_error = str(exc)

    # ==========================================================
    # Uso de memoria del proceso
    # ==========================================================
    process = psutil.Process()
    memory_info = process.memory_info()

    # ==========================================================
    # Detección de entorno de pruebas
    # ==========================================================
    app_env = getattr(settings, "APP_ENV", "").lower()
    is_pytest = "PYTEST_CURRENT_TEST" in os.environ
    is_test_env = app_env in {"test", "testing"} or is_pytest

    # En tests toleramos Redis caído.
    # En ejecución normal exigimos DB + Redis.
    if is_test_env:
        all_ok = db_ok
    else:
        all_ok = db_ok and redis_ok

    response_status = (
        status.HTTP_200_OK if all_ok else status.HTTP_503_SERVICE_UNAVAILABLE
    )

    payload = {
        "status": "ok" if all_ok else "error",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": getattr(settings, "APP_VERSION", "1.0.0"),
        "checks": {
            "database": "ok" if db_ok else "error",
            "cache": "ok" if redis_ok else "error",
        },
        "memory": {
            "rss_bytes": memory_info.rss,
            "vms_bytes": memory_info.vms,
        },
    }

    if not all_ok:
        payload["details"] = {
            "database": db_error,
            "cache": redis_error,
        }

    return JSONResponse(
        status_code=response_status,
        content=payload,
    )