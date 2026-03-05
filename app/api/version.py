from __future__ import annotations

import os

from fastapi import APIRouter

router = APIRouter()


@router.get("/version", tags=["API Version"])
def get_api_version():
    """
    Devuelve información básica de versión de la API.

    Campos:
    - current_version: versión actual recomendada
    - supported_versions: versiones soportadas
    - build_date: fecha de build/despliegue
    - environment: ambiente actual
    """
    return {
        "current_version": "v2",
        "supported_versions": ["v1", "v2"],
        "build_date": os.getenv("BUILD_DATE", "2026-03-05"),
        "environment": os.getenv("APP_ENV", "development"),
    }