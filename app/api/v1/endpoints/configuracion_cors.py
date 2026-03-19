from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.responses import error_response
from app.core.security import require_role, verify_api_key
from app.database.database import get_db
from app.models.configuracion_cors import ConfiguracionCors
from app.models.usuario import Usuario
from app.schemas.base import ApiResponse
from app.schemas.configuracion_cors import ConfiguracionCorsCreate, ConfiguracionCorsRead
from app.services.cors_service import cors_cache

router = APIRouter(
    prefix="/configuracion-cors",
    tags=["Configuración CORS"],
)


@router.get(
    "/",
    response_model=ApiResponse[list[ConfiguracionCorsRead]],
    dependencies=[Depends(verify_api_key)],
)
def listar_origins(
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_role("admin")),
):
    stmt = select(ConfiguracionCors).order_by(ConfiguracionCors.id.asc())
    rows = db.execute(stmt).scalars().all()

    return ApiResponse[list[ConfiguracionCorsRead]](
        success=True,
        message="Origins CORS obtenidos exitosamente",
        data=[ConfiguracionCorsRead.model_validate(row) for row in rows],
        metadata={},
    )


@router.post(
    "/",
    response_model=ApiResponse[ConfiguracionCorsRead],
    dependencies=[Depends(verify_api_key)],
)
def agregar_origin(
    payload: ConfiguracionCorsCreate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_role("admin")),
):
    nuevo = ConfiguracionCors(
        origin=payload.origin,
        activo=True,
    )

    try:
        db.add(nuevo)
        db.commit()
        db.refresh(nuevo)
        cors_cache.force_refresh()
    except IntegrityError:
        db.rollback()
        return error_response(
            status_code=400,
            message="Ese origin ya existe",
        )

    return ApiResponse[ConfiguracionCorsRead](
        success=True,
        message="Origin agregado exitosamente",
        data=ConfiguracionCorsRead.model_validate(nuevo),
        metadata={},
    )


@router.delete(
    "/{cors_id}",
    response_model=ApiResponse[dict],
    dependencies=[Depends(verify_api_key)],
)
def eliminar_origin(
    cors_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_role("admin")),
):
    stmt = select(ConfiguracionCors).where(ConfiguracionCors.id == cors_id)
    row = db.execute(stmt).scalars().first()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Origin CORS no encontrado",
        )

    db.delete(row)
    db.commit()
    cors_cache.force_refresh()

    return ApiResponse[dict](
        success=True,
        message="Origin eliminado exitosamente",
        data={"ok": True},
        metadata={},
    )
