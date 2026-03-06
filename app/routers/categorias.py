from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.responses import error_response
from app.core.security import verify_api_key
from app.database.database import get_db
from app.models.categoria import Categoria
from app.schemas.base import ApiResponse
from app.schemas.categoria import CategoriaCreate, CategoriaResponse, CategoriaUpdate

router = APIRouter(prefix="/categorias", tags=["categorias"])


@router.post(
    "/",
    response_model=ApiResponse[CategoriaResponse],
    summary="Crear categoría",
    dependencies=[Depends(verify_api_key)],
)
def crear_categoria(
    payload: CategoriaCreate,
    db: Session = Depends(get_db),
):
    """
    Crea una nueva categoría.

    Reglas:
    - nombre debe ser único
    """
    try:
        categoria = Categoria(
            nombre=payload.nombre,
            descripcion=payload.descripcion,
        )
        db.add(categoria)
        db.commit()
        db.refresh(categoria)

        return ApiResponse[CategoriaResponse](
            success=True,
            message="Categoría creada exitosamente",
            data=CategoriaResponse.model_validate(categoria),
            metadata={},
        )

    except IntegrityError:
        db.rollback()
        return error_response(
            status_code=400,
            message="Ya existe una categoría con ese nombre",
        )
    except SQLAlchemyError as e:
        db.rollback()
        return error_response(
            status_code=500,
            message="Error de base de datos al crear categoría",
            data={"error": str(e)},
        )


@router.get(
    "/",
    response_model=ApiResponse[list[CategoriaResponse]],
    summary="Listar categorías",
    dependencies=[Depends(verify_api_key)],
)
def listar_categorias(
    db: Session = Depends(get_db),
):
    """
    Lista todas las categorías.
    """
    categorias = db.execute(select(Categoria).order_by(Categoria.id.asc())).scalars().all()

    return ApiResponse[list[CategoriaResponse]](
        success=True,
        message="Categorías obtenidas exitosamente",
        data=[CategoriaResponse.model_validate(c) for c in categorias],
        metadata={},
    )


@router.get(
    "/{categoria_id}",
    response_model=ApiResponse[CategoriaResponse],
    summary="Obtener categoría por ID",
    dependencies=[Depends(verify_api_key)],
)
def obtener_categoria(
    categoria_id: int,
    db: Session = Depends(get_db),
):
    """
    Obtiene una categoría por su ID.
    """
    categoria = db.execute(
        select(Categoria).where(Categoria.id == categoria_id)
    ).scalars().first()

    if not categoria:
        return error_response(
            status_code=404,
            message=f"Categoría no encontrada con id={categoria_id}",
        )

    return ApiResponse[CategoriaResponse](
        success=True,
        message="Categoría obtenida exitosamente",
        data=CategoriaResponse.model_validate(categoria),
        metadata={},
    )


@router.put(
    "/{categoria_id}",
    response_model=ApiResponse[CategoriaResponse],
    summary="Actualizar categoría",
    dependencies=[Depends(verify_api_key)],
)
def actualizar_categoria(
    categoria_id: int,
    payload: CategoriaUpdate,
    db: Session = Depends(get_db),
):
    """
    Actualiza una categoría existente.
    """
    try:
        categoria = db.execute(
            select(Categoria).where(Categoria.id == categoria_id)
        ).scalars().first()

        if not categoria:
            return error_response(
                status_code=404,
                message=f"Categoría no encontrada con id={categoria_id}",
            )

        if payload.nombre is not None:
            categoria.nombre = payload.nombre

        if payload.descripcion is not None:
            categoria.descripcion = payload.descripcion

        db.add(categoria)
        db.commit()
        db.refresh(categoria)

        return ApiResponse[CategoriaResponse](
            success=True,
            message="Categoría actualizada exitosamente",
            data=CategoriaResponse.model_validate(categoria),
            metadata={},
        )

    except IntegrityError:
        db.rollback()
        return error_response(
            status_code=400,
            message="Ya existe una categoría con ese nombre",
        )
    except SQLAlchemyError as e:
        db.rollback()
        return error_response(
            status_code=500,
            message="Error de base de datos al actualizar categoría",
            data={"error": str(e)},
        )


@router.delete(
    "/{categoria_id}",
    response_model=ApiResponse[dict],
    summary="Eliminar categoría",
    dependencies=[Depends(verify_api_key)],
)
def eliminar_categoria(
    categoria_id: int,
    db: Session = Depends(get_db),
):
    """
    Elimina una categoría por ID.

    Nota:
    - Esta eliminación es física.
    """
    try:
        categoria = db.execute(
            select(Categoria).where(Categoria.id == categoria_id)
        ).scalars().first()

        if not categoria:
            return error_response(
                status_code=404,
                message=f"Categoría no encontrada con id={categoria_id}",
            )

        db.delete(categoria)
        db.commit()

        return ApiResponse[dict](
            success=True,
            message="Categoría eliminada exitosamente",
            data={"ok": True},
            metadata={},
        )

    except SQLAlchemyError as e:
        db.rollback()
        return error_response(
            status_code=500,
            message="Error de base de datos al eliminar categoría",
            data={"error": str(e)},
        )