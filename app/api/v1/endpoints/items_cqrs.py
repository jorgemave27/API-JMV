from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.commands.item_handlers import (
    ActualizarItemHandler,
    CrearItemHandler,
    EliminarItemHandler,
)
from app.commands.items import ActualizarItemCommand, CrearItemCommand, EliminarItemCommand
from app.core.exceptions import ItemNoEncontradoError
from app.core.security import require_role, verify_api_key
from app.database.database import get_db
from app.models.usuario import Usuario
from app.queries.item_handlers import BuscarItemsHandler, ListarItemsHandler, ObtenerItemHandler
from app.queries.items import BuscarItemsQuery, ListarItemsQuery, ObtenerItemQuery
from app.schemas.base import ApiResponse
from app.schemas.item import ItemRead
from app.schemas.pagination import PaginatedResponse
from app.schemas.item import ItemCreate

router = APIRouter()


@router.post(
    "/",
    dependencies=[Depends(verify_api_key), Depends(require_role("admin", "editor"))],
    summary="Crear item con CQRS",
)
def crear_item(
    payload: ItemCreate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_role("admin", "editor")),
):
    handler = CrearItemHandler(
        db=db,
        current_user_id=current_user.id,
        current_user_email=current_user.email,
    )

    result = handler.handle(
        CrearItemCommand(
            name=payload.name,
            description=payload.description,
            price=payload.price,
            sku=payload.sku,
            codigo_sku=payload.codigo_sku,
            stock=payload.stock,
            categoria_id=payload.categoria_id,
        )
    )

    return JSONResponse(
        status_code=status.HTTP_202_ACCEPTED,
        content={
            "success": True,
            "message": "Comando aceptado. Consulta /api/v1/operaciones/{operation_id} para saber cuándo la lectura está lista.",
            "data": {
                "item_id": result.resource_id,
                "operation_id": result.operation_id,
            },
            "metadata": {},
        },
    )


@router.put(
    "/{item_id}",
    dependencies=[Depends(verify_api_key), Depends(require_role("admin", "editor"))],
    summary="Actualizar item con CQRS",
)
def actualizar_item(
    item_id: int,
    payload: ItemCreate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_role("admin", "editor")),
):
    handler = ActualizarItemHandler(
        db=db,
        current_user_id=current_user.id,
        current_user_email=current_user.email,
    )

    result = handler.handle(
        ActualizarItemCommand(
            item_id=item_id,
            name=payload.name,
            description=payload.description,
            price=payload.price,
            sku=payload.sku,
            codigo_sku=payload.codigo_sku,
            stock=payload.stock,
            categoria_id=payload.categoria_id,
        )
    )

    return JSONResponse(
        status_code=status.HTTP_202_ACCEPTED,
        content={
            "success": True,
            "message": "Comando aceptado. Esperando actualización del modelo de lectura.",
            "data": {
                "item_id": result.resource_id,
                "operation_id": result.operation_id,
            },
            "metadata": {},
        },
    )


@router.delete(
    "/{item_id}",
    dependencies=[Depends(verify_api_key), Depends(require_role("admin"))],
    summary="Eliminar item con CQRS",
)
def eliminar_item(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_role("admin")),
):
    handler = EliminarItemHandler(
        db=db,
        current_user_id=current_user.id,
        current_user_email=current_user.email,
    )

    result = handler.handle(EliminarItemCommand(item_id=item_id))

    return JSONResponse(
        status_code=status.HTTP_202_ACCEPTED,
        content={
            "success": True,
            "message": "Comando aceptado. Esperando actualización del modelo de lectura.",
            "data": {
                "item_id": result.resource_id,
                "operation_id": result.operation_id,
            },
            "metadata": {},
        },
    )


@router.get(
    "/",
    response_model=ApiResponse[PaginatedResponse[ItemRead]],
    dependencies=[Depends(verify_api_key)],
    summary="Listar items desde modelo de lectura",
)
def listar_items(
    response: Response,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
):
    handler = ListarItemsHandler(db=db)
    result = handler.handle(ListarItemsQuery(page=page, page_size=page_size))

    response.headers["X-Cache"] = "HIT" if result.cache_hit else "MISS"

    return ApiResponse[PaginatedResponse[ItemRead]](
        success=True,
        message="Items obtenidos exitosamente desde modelo de lectura",
        data=PaginatedResponse[ItemRead](
            page=result.page,
            page_size=result.page_size,
            total=result.total,
            items=[ItemRead(**item) for item in result.items],
        ),
        metadata={},
    )


@router.get(
    "/buscar",
    response_model=ApiResponse[PaginatedResponse[ItemRead]],
    dependencies=[Depends(verify_api_key)],
    summary="Buscar items desde modelo de lectura",
)
def buscar_items(
    response: Response,
    term: str = Query(..., min_length=1),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
):
    handler = BuscarItemsHandler(db=db)
    result = handler.handle(BuscarItemsQuery(term=term, page=page, page_size=page_size))

    response.headers["X-Cache"] = "HIT" if result.cache_hit else "MISS"

    return ApiResponse[PaginatedResponse[ItemRead]](
        success=True,
        message="Búsqueda ejecutada exitosamente desde modelo de lectura",
        data=PaginatedResponse[ItemRead](
            page=result.page,
            page_size=result.page_size,
            total=result.total,
            items=[ItemRead(**item) for item in result.items],
        ),
        metadata={},
    )


@router.get(
    "/{item_id}",
    response_model=ApiResponse[ItemRead],
    dependencies=[Depends(verify_api_key)],
    summary="Obtener item por ID desde modelo de lectura",
)
def obtener_item_por_id(
    item_id: int,
    response: Response,
    db: Session = Depends(get_db),
):
    handler = ObtenerItemHandler(db=db)
    result = handler.handle(ObtenerItemQuery(item_id=item_id))

    response.headers["X-Cache"] = "HIT" if result.cache_hit else "MISS"

    if result.item is None:
        raise ItemNoEncontradoError(item_id)

    return ApiResponse[ItemRead](
        success=True,
        message="Item obtenido exitosamente desde modelo de lectura",
        data=ItemRead(**result.item),
        metadata={},
    )