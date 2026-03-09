from __future__ import annotations

import logging
from datetime import date, datetime, time
from typing import Optional

from fastapi import APIRouter, Depends, Query, HTTPException, Request, Response, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.core.cache import (
    build_item_cache_key,
    build_items_list_cache_key,
    build_items_list_signature,
    delete_cache,
    get_cache,
    invalidate_first_page_list_caches,
    invalidate_list_caches_for_item,
    register_list_cache,
    set_cache,
)
from app.core.config import dynamic_rate_limit, limiter, settings
from app.core.deps import get_client_ip, log_client_ip
from app.core.exceptions import ItemNoEncontradoError, StockInsuficienteError
from app.core.request_context import set_current_user_id
from app.core.responses import error_response
from app.core.security import verify_api_key, require_role
from app.database.database import get_db, get_db_async
from app.dependencies import get_item_repo
from app.models.auditoria_item import AuditoriaItem
from app.models.categoria import Categoria
from app.models.item import Item
from app.models.movimiento_stock import MovimientoStock
from app.models.usuario import Usuario
from app.repositories.item_repository import ItemRepository
from app.schemas.base import ApiResponse
from app.schemas.bulk import BulkCreate, BulkDelete, BulkUpdateDisponible
from app.schemas.cursor_pagination import CursorPaginationResponse
from app.schemas.item import ItemCreate, ItemRead
from app.schemas.movimiento_stock import TransferirStockRequest
from app.schemas.pagination import PaginatedResponse
from app.workers.tasks import enviar_notificacion


router = APIRouter()

# Logger específico del módulo
logger = logging.getLogger(__name__)


def _bind_audit_user(current_user: Usuario | None) -> None:
    """
    Guarda el user_id actual en el contexto de auditoría.

    Esto permite que los eventos de SQLAlchemy registren automáticamente
    quién hizo el cambio, sin pasar user_id manualmente hasta el modelo.
    """
    set_current_user_id(current_user.id if current_user else None)


@router.post(
    "/",
    response_model=ApiResponse[ItemRead],
    summary="Crear item",
    dependencies=[Depends(verify_api_key), Depends(require_role("admin", "editor"))],
)
@limiter.limit(dynamic_rate_limit)
def crear_item(
    request: Request,
    payload: ItemCreate,
    db: Session = Depends(get_db),
    repo: ItemRepository = Depends(get_item_repo),
    current_user: Usuario = Depends(require_role("admin", "editor")),
):
    """
    Crea un item individual.

    Caché:
    - Al crear un item nuevo, invalidamos primeras páginas del listado,
      porque son las que más probablemente cambien.
    """
    _bind_audit_user(current_user)

    if payload.categoria_id is not None:
        categoria = db.execute(
            select(Categoria).where(Categoria.id == payload.categoria_id)
        ).scalars().first()

        if not categoria:
            return error_response(
                status_code=400,
                message=f"La categoría con id={payload.categoria_id} no existe",
            )

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

    # Invalidación inteligente: no vaciamos toda la caché, solo primeras páginas
    invalidate_first_page_list_caches()

    # Disparo de tarea en background con Celery
    enviar_notificacion.delay(item.id, "admin@empresa.com")

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
    dependencies=[Depends(verify_api_key), Depends(require_role("admin", "editor"))],
)
def bulk_create_items(
    payload: BulkCreate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_role("admin", "editor")),
):
    """
    Crea múltiples items en una sola transacción.

    Caché:
    - Al insertar muchos items, invalidamos primeras páginas de listados.
    """
    _bind_audit_user(current_user)

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

        invalidate_first_page_list_caches()

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

    Caché:
    - Invalida caché individual y páginas relacionadas de cada item afectado.
    """
    try:
        now = datetime.now()

        stmt = select(Item).where(Item.id.in_(payload.ids))
        found = db.execute(stmt).scalars().all()
        found_map = {i.id: i for i in found}

        deleted = 0
        not_found = 0
        affected_ids: list[int] = []

        for item_id in payload.ids:
            item = found_map.get(item_id)

            if not item:
                not_found += 1
                continue

            if not item.eliminado:
                item.eliminado = True
                item.eliminado_en = now
                deleted += 1
                affected_ids.append(item.id)

        db.commit()

        # Invalidación de caché después del commit
        for item_id in affected_ids:
            delete_cache(build_item_cache_key(item_id))
            invalidate_list_caches_for_item(item_id, include_first_pages=True)

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

    Caché:
    - Si cambia stock, invalidamos caché individual y páginas relacionadas.
    """
    try:
        stmt = select(Item).where(Item.id.in_(payload.ids))
        found = db.execute(stmt).scalars().all()
        found_map = {i.id: i for i in found}

        updated = 0
        not_found = 0
        affected_ids: list[int] = []

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
                    affected_ids.append(item.id)

        if payload.disponible:
            for item_id in payload.ids:
                item = found_map.get(item_id)
                if not item:
                    continue

                if item.stock != 1:
                    item.stock = 1
                    updated += 1
                    affected_ids.append(item.id)

        db.commit()

        # Invalidación de caché después del commit
        for item_id in set(affected_ids):
            delete_cache(build_item_cache_key(item_id))
            invalidate_list_caches_for_item(item_id, include_first_pages=True)

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
@limiter.limit(dynamic_rate_limit)
async def listar_items(
    request: Request,
    response: Response,
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
    db: AsyncSession = Depends(get_db_async),
    _ip: str = Depends(log_client_ip),
):
    """
    Lista items activos con filtros, orden y paginación usando AsyncSession.

    Caché:
    - Usa cache key basada en filtros + page.
    - Si existe en Redis => X-Cache: HIT
    - Si no existe => consulta BD async, guarda en Redis => X-Cache: MISS
    """
    cache_params = {
        "page_size": page_size,
        "nombre": nombre,
        "precio_min": precio_min,
        "precio_max": precio_max,
        "disponible": disponible,
        "ordenar_por": ordenar_por,
        "creado_desde": creado_desde.isoformat() if creado_desde else None,
    }

    signature = build_items_list_signature(cache_params)
    cache_key = build_items_list_cache_key(signature, page)

    cached_page = get_cache(cache_key)
    if cached_page is not None:
        response.headers["X-Cache"] = "HIT"
        return cached_page

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
    total_result = await db.execute(count_stmt)
    total = total_result.scalar_one()

    order_map = {
        "precio_asc": Item.price.asc(),
        "precio_desc": Item.price.desc(),
        "nombre_asc": Item.name.asc(),
        "nombre_desc": Item.name.desc(),
    }
    stmt = stmt.order_by(order_map[ordenar_por]) if ordenar_por else stmt.order_by(Item.id.asc())

    offset = (page - 1) * page_size
    stmt = stmt.offset(offset).limit(page_size)

    result = await db.execute(stmt)
    items = result.scalars().all()

    paginated = PaginatedResponse[ItemRead](
        page=page,
        page_size=page_size,
        total=total,
        items=[ItemRead.model_validate(i) for i in items],
    )

    payload = ApiResponse[PaginatedResponse[ItemRead]](
        success=True,
        message="Items obtenidos exitosamente",
        data=paginated,
        metadata={},
    )

    payload_dict = payload.model_dump(mode="json")

    set_cache(
        cache_key,
        payload_dict,
        ttl=settings.CACHE_TTL_LIST_SECONDS,
    )

    register_list_cache(
        cache_key=cache_key,
        page=page,
        ttl=settings.CACHE_TTL_LIST_SECONDS,
        item_ids=[item.id for item in items],
        params=cache_params,
    )

    response.headers["X-Cache"] = "MISS"
    return payload


@router.get(
    "/buscar",
    response_model=ApiResponse[list[ItemRead]],
    summary="Buscar items por nombre exacto de forma segura",
    dependencies=[Depends(verify_api_key)],
)
def buscar_items(
    nombre: str = Query(..., min_length=1, description="Nombre exacto del item"),
    db: Session = Depends(get_db),
):
    """
    Búsqueda segura por nombre exacto usando ORM.
    """
    items = (
        db.query(Item)
        .filter(Item.name == nombre, Item.eliminado.is_(False))
        .order_by(Item.id.asc())
        .all()
    )

    return ApiResponse[list[ItemRead]](
        success=True,
        message="Búsqueda segura ejecutada",
        data=[ItemRead.model_validate(item) for item in items],
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
    Lista items eliminados lógicamente.
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
    Endpoint demo para probar dependency injection de IP.
    """
    return ApiResponse[dict](
        success=True,
        message="IP obtenida exitosamente",
        data={"ip": ip},
        metadata={},
    )


@router.get(
    "/{item_id}",
    response_model=ApiResponse[ItemRead],
    summary="Obtener item por ID",
    dependencies=[Depends(verify_api_key)],
)
def obtener_item_por_id(
    item_id: int,
    response: Response,
    repo: ItemRepository = Depends(get_item_repo),
):
    """
    Obtiene un item por ID usando patrón cache-aside.

    Flujo:
    1. Busca en Redis.
    2. Si existe: X-Cache=HIT
    3. Si no existe: consulta BD, guarda en Redis, X-Cache=MISS
    """
    cache_key = build_item_cache_key(item_id)

    cached_item = get_cache(cache_key)
    if cached_item is not None:
        response.headers["X-Cache"] = "HIT"
        return cached_item

    item = repo.get_by_id(item_id)

    if not item:
        response.headers["X-Cache"] = "MISS"
        raise ItemNoEncontradoError(item_id)

    payload = ApiResponse[ItemRead](
        success=True,
        message="Item obtenido exitosamente",
        data=ItemRead.model_validate(item),
        metadata={},
    )

    set_cache(
        cache_key,
        payload.model_dump(mode="json"),
        ttl=settings.CACHE_TTL_ITEM_SECONDS,
    )

    response.headers["X-Cache"] = "MISS"
    return payload


@router.get(
    "/{item_id}/historial",
    response_model=ApiResponse[list[dict]],
    summary="Obtener historial de auditoría de un item",
    dependencies=[Depends(verify_api_key)],
)
def obtener_historial_item(
    item_id: int,
    db: Session = Depends(get_db),
):
    """
    Obtiene todos los registros de auditoría de un item específico,
    ordenados cronológicamente.
    """
    auditorias = (
        db.execute(
            select(AuditoriaItem)
            .where(AuditoriaItem.item_id == item_id)
            .order_by(AuditoriaItem.timestamp.asc(), AuditoriaItem.id.asc())
        )
        .scalars()
        .all()
    )

    data = [
        {
            "id": audit.id,
            "item_id": audit.item_id,
            "accion": audit.accion,
            "datos_anteriores": audit.datos_anteriores,
            "datos_nuevos": audit.datos_nuevos,
            "usuario_id": audit.usuario_id,
            "timestamp": audit.timestamp.isoformat() if audit.timestamp else None,
            "ip_cliente": audit.ip_cliente,
        }
        for audit in auditorias
    ]

    return ApiResponse[list[dict]](
        success=True,
        message="Historial de auditoría obtenido exitosamente",
        data=data,
        metadata={},
    )


@router.get(
    "/{item_id}/estado",
    response_model=ApiResponse[dict],
    summary="Reconstruir estado de un item en una fecha específica",
    dependencies=[Depends(verify_api_key)],
)
def obtener_estado_item_en_fecha(
    item_id: int,
    fecha: datetime = Query(..., description="Fecha y hora en formato ISO 8601"),
    db: Session = Depends(get_db),
):
    """
    Reconstruye el estado de un item en una fecha específica
    usando los registros de auditoría hasta ese momento.
    """
    auditorias = (
        db.execute(
            select(AuditoriaItem)
            .where(AuditoriaItem.item_id == item_id)
            .where(AuditoriaItem.timestamp <= fecha)
            .order_by(AuditoriaItem.timestamp.asc(), AuditoriaItem.id.asc())
        )
        .scalars()
        .all()
    )

    estado: dict | None = None

    for audit in auditorias:
        if audit.accion == "CREATE":
            estado = audit.datos_nuevos.copy() if audit.datos_nuevos else None
        elif audit.accion == "UPDATE":
            estado = audit.datos_nuevos.copy() if audit.datos_nuevos else estado
        elif audit.accion == "DELETE":
            if audit.datos_nuevos is None:
                estado = None
            else:
                estado = audit.datos_nuevos.copy()

    return ApiResponse[dict](
        success=True,
        message="Estado reconstruido exitosamente",
        data={
            "item_id": item_id,
            "fecha_consulta": fecha.isoformat(),
            "exists_at_that_time": estado is not None,
            "estado": estado,
        },
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
    current_user: Usuario = Depends(require_role("admin")),
):
    """
    Soft delete de un item individual.

    Caché:
    - Borra caché individual del item
    - Invalida páginas de listados relacionadas
    """
    _bind_audit_user(current_user)

    item = repo.get_by_id(item_id)

    if not item:
        raise ItemNoEncontradoError(item_id)

    if item.eliminado:
        logger.warning(
            f"Intento de eliminar un item ya eliminado: id={item.id}, usuario={current_user.email}"
        )
        return ApiResponse[dict](
            success=True,
            message="Item ya estaba eliminado",
            data={"ok": True},
            metadata={},
        )

    repo.delete(item)

    # Invalidación de caché después del delete
    delete_cache(build_item_cache_key(item_id))
    invalidate_list_caches_for_item(item_id, include_first_pages=True)

    logger.info(
        f"Item eliminado (soft delete): id={item.id}, usuario={current_user.email}"
    )

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
    dependencies=[Depends(verify_api_key), Depends(require_role("admin", "editor"))],
)
def restaurar_item(
    item_id: int,
    repo: ItemRepository = Depends(get_item_repo),
    current_user: Usuario = Depends(require_role("admin", "editor")),
):
    """
    Restaura un item previamente eliminado.

    Caché:
    - Borra caché individual del item
    - Invalida páginas relacionadas para que reaparezca donde corresponda
    """
    _bind_audit_user(current_user)

    item = repo.get_by_id(item_id)

    if not item:
        raise ItemNoEncontradoError(item_id)

    if not item.eliminado:
        return error_response(status_code=400, message="El item no está eliminado")

    item.eliminado = False
    item.eliminado_en = None
    item = repo.update(item)

    delete_cache(build_item_cache_key(item_id))
    invalidate_list_caches_for_item(item_id, include_first_pages=True)

    logger.info(f"Item restaurado: id={item.id}")

    return ApiResponse[ItemRead](
        success=True,
        message="Item restaurado exitosamente",
        data=ItemRead.model_validate(item),
        metadata={},
    )


@router.post(
    "/transferir-stock",
    dependencies=[Depends(verify_api_key), Depends(require_role("admin", "editor"))],
)
def transferir_stock(
    payload: TransferirStockRequest,
    db: Session = Depends(get_db),
    repo: ItemRepository = Depends(get_item_repo),
    current_user: Usuario = Depends(require_role("admin", "editor")),
):
    """
    Transfiere stock entre dos items de forma atómica.

    Caché:
    - Invalida caché de item origen y destino
    - Invalida páginas relacionadas porque cambió stock
    """
    _bind_audit_user(current_user)

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

    # Invalidación de caché de ambos items
    for affected_id in (item_origen.id, item_destino.id):
        delete_cache(build_item_cache_key(affected_id))
        invalidate_list_caches_for_item(affected_id, include_first_pages=True)

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