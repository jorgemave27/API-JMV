from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import require_role, verify_api_key
from app.database.database import get_db
from app.models.reporte_stock import ReporteStock
from app.models.usuario import Usuario
from app.schemas.base import ApiResponse

router = APIRouter()


@router.get(
    "/stock-bajo",
    response_model=ApiResponse[list[dict]],
    summary="Listar reportes de stock bajo",
    dependencies=[Depends(verify_api_key)],
)
def listar_reportes_stock_bajo(
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_role("admin", "editor")),
):
    reportes = (
        db.execute(
            select(ReporteStock)
            .where(ReporteStock.tipo == "stock_bajo")
            .order_by(ReporteStock.creado_en.desc(), ReporteStock.id.desc())
        )
        .scalars()
        .all()
    )

    data = [
        {
            "id": reporte.id,
            "tipo": reporte.tipo,
            "total_items": reporte.total_items,
            "umbral": reporte.umbral,
            "contenido": reporte.contenido,
            "creado_en": reporte.creado_en.isoformat() if reporte.creado_en else None,
        }
        for reporte in reportes
    ]

    return ApiResponse[list[dict]](
        success=True,
        message="Reportes de stock bajo obtenidos exitosamente",
        data=data,
        metadata={},
    )
