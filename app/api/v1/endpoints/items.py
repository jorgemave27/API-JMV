from __future__ import annotations

import logging
from datetime import date, datetime, time
from typing import Optional

from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.deps import get_client_ip, log_client_ip
from app.core.exceptions import ItemNoEncontradoError, StockInsuficienteError
from app.core.responses import error_response
from app.core.security import verify_api_key
from app.database.database import get_db
from app.dependencies import get_item_repo
from app.models.categoria import Categoria
from app.models.item import Item
from app.models.movimiento_stock import MovimientoStock
from app.repositories.item_repository import ItemRepository
from app.schemas.base import ApiResponse
from app.schemas.bulk import BulkCreate, BulkDelete, BulkUpdateDisponible
from app.schemas.item import ItemCreate, ItemRead
from app.schemas.movimiento_stock import TransferirStockRequest
from app.schemas.pagination import PaginatedResponse
from app.schemas.cursor_pagination import CursorPaginationResponse

router = APIRouter()

# Logger específico de este módulo
# Sigue la guía del task 14: un logger por archivo usando __name__
logger = logging.getLogger(__name__)


@router.post(
    "/",
    response_model=ApiResponse[ItemRead],
    summary="Crear item",
    dependencies=[Depends(verify_api_key)],
)
def crear_item(
    payload: ItemCreate,
    db: Session = Depends(get_db),
    repo: ItemRepository = Depends(get_item_repo),
):
    """
    Crea un item individual.

    Validaciones:
    - Si se envía categoria_id, debe existir en la base de datos
    - Si no existe, retorna error 400

    Repository pattern aplicado:
    - La persistencia del item se delega al repository

    Logging aplicado:
    - INFO cuando el item se crea exitosamente
    """
    # -------------------------
    # Validación de categoría
    # -------------------------
    if payload.categoria_id is not None:
        categoria = db.execute(
            select(Categoria).where(Categoria.id == payload.categoria_id)
        ).scalars().first()

        if not categoria:
            return error_response(
                status_code=400,
                message=f"La categoría con id={payload.categoria_id} no existe",
            )

    # -------------------------
    # Creación del item
    # -------------------------
    item = Item(
        name=payload.name,
        description=payload.description,
        price=payload.price,
        sku=payload.sku,
        codigo_sku=payload.codigo_sku,
        stock=payload.stock,
        categoria_id=payload.categoria_id,
    )

    item = repo.create(item)

    logger.info(f"Item creado: id={item.id}, nombre={item.name}")

    return ApiResponse[ItemRead](
        success=True,
        message="Item creado exitosamente",
        data=ItemRead.model_validate(item),
        metadata={},
    )


@router.post(
    "/bulk",
    response_model=ApiResponse[list[ItemRead]],
    summary="Crear items en lote (máx 100) (transaccional)",
    dependencies=[Depends(verify_api_key)],
)
def bulk_create_items(
    payload: BulkCreate,
    db: Session = Depends(get_db),
):
    """
    Crea múltiples items en una sola transacción.

    Reglas:
    - Si uno falla, se hace rollback de todos
    - Se usa add_all + un solo commit
    - Máximo 100 items validado desde el schema

    Logging aplicado:
    - ERROR con exc_info=True en fallos
    """
    try:
        objects: list[Item] = []

        for it in payload.items:
            objects.append(
                Item(
                    name=it.name,
                    description=it.description,
                    price=it.price,
                    sku=it.sku,
                    codigo_sku=it.codigo_sku,
                    stock=it.stock,
                )
            )

        db.add_all(objects)
        db.commit()

        for obj in objects:
            db.refresh(obj)

        logger.info(f"Bulk create completado: total_items={len(objects)}")

        return ApiResponse[list[ItemRead]](
            success=True,
            message="Items creados exitosamente (bulk)",
            data=[ItemRead.model_validate(o) for o in objects],
            metadata={},
        )

    except IntegrityError as e:
        db.rollback()
        logger.error(f"Error al procesar bulk create: {str(e)}", exc_info=True)
        return error_response(
            status_code=400,
            message="Error en bulk create: violación de integridad (ej. SKU duplicado). Se hizo rollback.",
        )
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Error al procesar bulk create: {str(e)}", exc_info=True)
        return error_response(
            status_code=500,
            message="Error de base de datos en bulk create. Se hizo rollback.",
            data={"error": str(e)},
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Error al procesar bulk create: {str(e)}", exc_info=True)
        return error_response(
            status_code=500,
            message="Error inesperado en bulk create. Se hizo rollback.",
            data={"error": str(e)},
        )


@router.delete(
    "/bulk",
    response_model=ApiResponse[dict],
    summary="Eliminar items en lote por IDs (soft delete) (máx 100)",
    dependencies=[Depends(verify_api_key)],
)
def bulk_delete_items(
    payload: BulkDelete,
    db: Session = Depends(get_db),
):
    """
    Elimina en lote usando soft delete.

    Reglas:
    - No borra físicamente
    - Marca eliminado=True y eliminado_en=now()
    - Si algún ID no existe, no falla; lo cuenta en not_found

    Logging aplicado:
    - ERROR con exc_info=True en fallos
    """
    try:
        now = datetime.now()

        stmt = select(Item).where(Item.id.in_(payload.ids))
        found = db.execute(stmt).scalars().all()
        found_map = {i.id: i for i in found}

        deleted = 0
        not_found = 0

        for item_id in payload.ids:
            item = found_map.get(item_id)

            if not item:
                not_found += 1
                continue

            if not item.eliminado:
                item.eliminado = True
                item.eliminado_en = now
                deleted += 1

        db.commit()

        logger.info(
            f"Bulk delete procesado: deleted={deleted}, not_found={not_found}"
        )

        return ApiResponse[dict](
            success=True,
            message="Bulk delete procesado",
            data={"deleted": deleted, "not_found": not_found},
            metadata={},
        )

    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Error al procesar bulk delete: {str(e)}", exc_info=True)
        return error_response(
            status_code=500,
            message="Error de base de datos en bulk delete. Se hizo rollback.",
            data={"error": str(e)},
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Error al procesar bulk delete: {str(e)}", exc_info=True)
        return error_response(
            status_code=500,
            message="Error inesperado en bulk delete. Se hizo rollback.",
            data={"error": str(e)},
        )


@router.put(
    "/bulk",
    response_model=ApiResponse[dict],
    summary="Actualizar 'disponible' en lote (interpreta disponible como stock>0)",
    dependencies=[Depends(verify_api_key)],
)
def bulk_update_disponible(
    payload: BulkUpdateDisponible,
    db: Session = Depends(get_db),
):
    """
    Actualiza 'disponible' en lote.

    Como el modelo no tiene columna disponible, se interpreta así:
    - disponible=True  => stock=1
    - disponible=False => stock=0

    Regla del reto task 13:
    - Si se intenta marcar disponible=True y el item tiene stock=0,
      se lanza StockInsuficienteError (HTTP 409 desde el handler global)

    Logging aplicado:
    - ERROR con exc_info=True en fallos
    """
    try:
        stmt = select(Item).where(Item.id.in_(payload.ids))
        found = db.execute(stmt).scalars().all()
        found_map = {i.id: i for i in found}

        updated = 0
        not_found = 0

        for item_id in payload.ids:
            item = found_map.get(item_id)

            if not item:
                not_found += 1
                continue

            if payload.disponible:
                if item.stock == 0:
                    raise StockInsuficienteError(item_id=item.id, stock_actual=item.stock)
            else:
                if item.stock != 0:
                    item.stock = 0
                    updated += 1

        if payload.disponible:
            for item_id in payload.ids:
                item = found_map.get(item_id)
                if not item:
                    continue

                if item.stock != 1:
                    item.stock = 1
                    updated += 1

        db.commit()

        logger.info(
            f"Bulk update disponible procesado: updated={updated}, not_found={not_found}, disponible={payload.disponible}"
        )

        return ApiResponse[dict](
            success=True,
            message="Bulk update disponible procesado",
            data={"updated": updated, "not_found": not_found},
            metadata={},
        )

    except StockInsuficienteError:
        db.rollback()
        logger.error("Error al procesar bulk update disponible: stock insuficiente", exc_info=True)
        raise
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Error al procesar bulk update disponible: {str(e)}", exc_info=True)
        return error_response(
            status_code=500,
            message="Error de base de datos en bulk update disponible. Se hizo rollback.",
            data={"error": str(e)},
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Error al procesar bulk update disponible: {str(e)}", exc_info=True)
        return error_response(
            status_code=500,
            message="Error inesperado en bulk update disponible. Se hizo rollback.",
            data={"error": str(e)},
        )


@router.get(
    "/",
    response_model=ApiResponse[PaginatedResponse[ItemRead]],
    summary="Listar items con filtros, búsqueda, orden y paginación (solo activos)",
    dependencies=[Depends(verify_api_key)],
)
def listar_items(
    page: int = Query(1, ge=1, description="Página (>=1)"),
    page_size: int = Query(10, ge=1, le=100, description="Tamaño de página (1-100)"),
    nombre: Optional[str] = Query(None, description="Filtra por nombre (contiene, case-insensitive)"),
    precio_min: Optional[float] = Query(None, ge=0, description="Precio mínimo (>=0)"),
    precio_max: Optional[float] = Query(None, ge=0, description="Precio máximo (>=0)"),
    disponible: Optional[bool] = Query(None, description="true: stock>0, false: stock<=0"),
    ordenar_por: Optional[str] = Query(
        None,
        description="Orden: precio_asc, precio_desc, nombre_asc, nombre_desc",
        pattern="^(precio_asc|precio_desc|nombre_asc|nombre_desc)?$",
    ),
    creado_desde: Optional[date] = Query(
        None,
        description="Filtra items creados desde esta fecha (YYYY-MM-DD)",
    ),
    db: Session = Depends(get_db),
    _ip: str = Depends(log_client_ip),
):
    """
    Lista items activos con:
    - filtros opcionales
    - búsqueda por nombre
    - ordenamiento
    - paginación

    Nota:
    - disponible se interpreta con base en stock
    """
    stmt = select(Item).where(Item.eliminado == False)  # noqa: E712

    if nombre:
        stmt = stmt.where(Item.name.ilike(f"%{nombre}%"))

    if precio_min is not None:
        stmt = stmt.where(Item.price >= precio_min)

    if precio_max is not None:
        stmt = stmt.where(Item.price <= precio_max)

    if disponible is not None:
        stmt = stmt.where(Item.stock > 0) if disponible else stmt.where(Item.stock <= 0)

    if creado_desde is not None:
        dt = datetime.combine(creado_desde, time.min)
        stmt = stmt.where(Item.created_at >= dt)

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = db.execute(count_stmt).scalar_one()

    order_map = {
        "precio_asc": Item.price.asc(),
        "precio_desc": Item.price.desc(),
        "nombre_asc": Item.name.asc(),
        "nombre_desc": Item.name.desc(),
    }
    stmt = stmt.order_by(order_map[ordenar_por]) if ordenar_por else stmt.order_by(Item.id.asc())

    offset = (page - 1) * page_size
    stmt = stmt.offset(offset).limit(page_size)

    items = db.execute(stmt).scalars().all()

    paginated = PaginatedResponse[ItemRead](
        page=page,
        page_size=page_size,
        total=total,
        items=[ItemRead.model_validate(i) for i in items],
    )

    return ApiResponse[PaginatedResponse[ItemRead]](
        success=True,
        message="Items obtenidos exitosamente",
        data=paginated,
        metadata={},
    )

@router.get(
    "/cursor",
    response_model=ApiResponse[CursorPaginationResponse],
    summary="Listar items con paginación por cursor (keyset pagination)",
    dependencies=[Depends(verify_api_key)],
)
def listar_items_cursor(
    cursor: int = Query(0, ge=0, description="Último ID visto; 0 para iniciar"),
    limite: int = Query(10, ge=1, le=100, description="Cantidad máxima de items por página"),
    db: Session = Depends(get_db),
):
    """
    Lista items activos usando paginación por cursor.

    Reglas:
    - Solo devuelve items con id > cursor
    - Ordena por id ascendente
    - Retorna next_cursor basado en el último item devuelto
    - has_more indica si hay más resultados después de esta página
    """
    stmt = (
        select(Item)
        .where(Item.eliminado == False)  # noqa: E712
        .where(Item.id > cursor)
        .order_by(Item.id.asc())
        .limit(limite + 1)
    )

    results = db.execute(stmt).scalars().all()

    has_more = len(results) > limite
    items = results[:limite]

    next_cursor = items[-1].id if items else None

    data = CursorPaginationResponse(
        items=[ItemRead.model_validate(item) for item in items],
        next_cursor=next_cursor,
        has_more=has_more,
    )

    return ApiResponse[CursorPaginationResponse](
        success=True,
        message="Items obtenidos exitosamente con paginación por cursor",
        data=data,
        metadata={},
    )

@router.get(
    "/eliminados",
    response_model=ApiResponse[PaginatedResponse[ItemRead]],
    summary="Listar items eliminados (soft delete)",
    dependencies=[Depends(verify_api_key)],
)
def listar_eliminados(
    page: int = Query(1, ge=1, description="Página (>=1)"),
    page_size: int = Query(10, ge=1, le=100, description="Tamaño de página (1-100)"),
    db: Session = Depends(get_db),
):
    """
    Lista items eliminados lógicamente (soft delete).
    """
    stmt = select(Item).where(Item.eliminado == True)  # noqa: E712

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = db.execute(count_stmt).scalar_one()

    stmt = stmt.order_by(Item.id.asc())

    offset = (page - 1) * page_size
    stmt = stmt.offset(offset).limit(page_size)

    items = db.execute(stmt).scalars().all()

    paginated = PaginatedResponse[ItemRead](
        page=page,
        page_size=page_size,
        total=total,
        items=[ItemRead.model_validate(i) for i in items],
    )

    return ApiResponse[PaginatedResponse[ItemRead]](
        success=True,
        message="Items eliminados obtenidos exitosamente",
        data=paginated,
        metadata={},
    )


@router.get(
    "/ip",
    response_model=ApiResponse[dict],
    summary="Demo: obtener IP del cliente (dependency)",
    dependencies=[Depends(verify_api_key)],
)
def mi_ip(ip: str = Depends(get_client_ip)):
    """
    Endpoint demo para probar dependency injection de IP del cliente.
    """
    return ApiResponse[dict](
        success=True,
        message="IP obtenida exitosamente",
        data={"ip": ip},
        metadata={},
    )


@router.delete(
    "/{item_id}",
    response_model=ApiResponse[dict],
    summary="Eliminar item por ID (soft delete)",
    dependencies=[Depends(verify_api_key)],
)
def eliminar_item(
    item_id: int,
    repo: ItemRepository = Depends(get_item_repo),
):
    """
    Soft delete de un item individual.

    Reglas:
    - Si no existe => ItemNoEncontradoError
    - Si ya estaba eliminado => warning log y respuesta idempotente

    Repository pattern aplicado:
    - La obtención y eliminación del item se delegan al repository
    """
    item = repo.get_by_id(item_id)

    if not item:
        raise ItemNoEncontradoError(item_id)

    if item.eliminado:
        logger.warning(f"Intento de eliminar un item ya eliminado: id={item.id}")
        return ApiResponse[dict](
            success=True,
            message="Item ya estaba eliminado",
            data={"ok": True},
            metadata={},
        )

    repo.delete(item)

    logger.info(f"Item eliminado (soft delete): id={item.id}")

    return ApiResponse[dict](
        success=True,
        message="Item eliminado (soft delete)",
        data={"ok": True},
        metadata={},
    )


@router.post(
    "/{item_id}/restaurar",
    response_model=ApiResponse[ItemRead],
    summary="Restaurar item eliminado (soft delete)",
    dependencies=[Depends(verify_api_key)],
)
def restaurar_item(
    item_id: int,
    repo: ItemRepository = Depends(get_item_repo),
):
    """
    Restaura un item previamente eliminado.

    Reglas:
    - Si no existe => ItemNoEncontradoError
    - Si no está eliminado => error_response 400

    Repository pattern aplicado:
    - La obtención y actualización del item se delegan al repository
    """
    item = repo.get_by_id(item_id)

    if not item:
        raise ItemNoEncontradoError(item_id)

    if not item.eliminado:
        return error_response(status_code=400, message="El item no está eliminado")

    item.eliminado = False
    item.eliminado_en = None
    item = repo.update(item)

    logger.info(f"Item restaurado: id={item.id}")

    return ApiResponse[ItemRead](
        success=True,
        message="Item restaurado exitosamente",
        data=ItemRead.model_validate(item),
        metadata={},
    )


@router.post("/transferir-stock")
def transferir_stock(
    payload: TransferirStockRequest,
    db: Session = Depends(get_db),
    repo: ItemRepository = Depends(get_item_repo),
):
    """
    Transfiere stock entre dos items de forma atómica.

    La operación valida existencia, stock suficiente y registra auditoría
    en la misma transacción.

    Repository pattern aplicado:
    - La obtención de items se hace mediante el repository
    """
    if payload.item_origen_id == payload.item_destino_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El item origen y destino no pueden ser el mismo",
        )

    item_origen = repo.get_by_id(payload.item_origen_id)
    if item_origen is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Item origen no encontrado",
        )

    item_destino = repo.get_by_id(payload.item_destino_id)
    if item_destino is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Item destino no encontrado",
        )

    if item_origen.eliminado:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El item origen está eliminado",
        )

    if item_destino.eliminado:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El item destino está eliminado",
        )

    if item_origen.stock < payload.cantidad:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Stock insuficiente en el item origen",
        )

    try:
        with db.begin_nested():
            item_origen.stock -= payload.cantidad

            if payload.forzar_error:
                raise RuntimeError("Error forzado para probar rollback")

            item_destino.stock += payload.cantidad

            movimiento = MovimientoStock(
                item_origen_id=item_origen.id,
                item_destino_id=item_destino.id,
                cantidad=payload.cantidad,
                usuario=payload.usuario,
            )
            db.add(movimiento)

        db.commit()

    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al transferir stock: {exc}",
        ) from exc

    db.refresh(item_origen)
    db.refresh(item_destino)

    return {
        "success": True,
        "message": "Transferencia de stock realizada exitosamente",
        "data": {
            "item_origen_id": item_origen.id,
            "item_destino_id": item_destino.id,
            "cantidad_transferida": payload.cantidad,
            "stock_origen": item_origen.stock,
            "stock_destino": item_destino.stock,
            "usuario": payload.usuario,
        },
    }