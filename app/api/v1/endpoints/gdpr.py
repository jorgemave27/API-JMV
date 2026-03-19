from __future__ import annotations

"""
Endpoints relacionados con cumplimiento GDPR / LFPDPPP.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.security import verify_api_key
from app.database.database import get_db
from app.services.gdpr_report_service import generar_reporte_gdpr

router = APIRouter()


@router.get(
    "/admin/gdpr/reporte",
    summary="Reporte GDPR de manejo de datos personales",
)
def obtener_reporte_gdpr(
    db: Session = Depends(get_db),
    api_key: str = Depends(verify_api_key),
):
    """
    Genera reporte de actividad de datos personales.
    """

    data = generar_reporte_gdpr(db)

    return {
        "success": True,
        "message": "Reporte GDPR generado correctamente",
        "data": data,
        "metadata": {},
    }
