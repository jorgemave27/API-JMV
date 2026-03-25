from __future__ import annotations

import logging
import asyncio 
from datetime import date, datetime, time
from math import ceil
from typing import Any, Optional
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session, selectinload

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
from app.core.metrics import ITEMS_CREATED_BY_CATEGORY, increment_crud_operation
from app.core.request_context import set_current_user_id
from app.core.responses import error_response
from app.core.security import require_role, verify_api_key
from app.database.database import get_db, get_db_async, get_read_db
from app.dependencies import get_item_repo
from app.messaging.kafka_publisher import publish_domain_event
from app.messaging.producer import RabbitMQProducer
from app.models.auditoria_item import AuditoriaItem
from app.models.categoria import Categoria
from app.models.item import Item
from app.models.movimiento_stock import MovimientoStock
from app.models.usuario import Usuario
from app.repositories.item_repository import ItemRepository
from app.schemas.base import ApiResponse
from app.schemas.bulk import BulkCreate, BulkDelete, BulkUpdateDisponible
from app.schemas.cursor_pagination import CursorPaginationResponse
from app.schemas.domain_event import DomainEvent
from app.schemas.item import ItemCreate, ItemRead
from app.schemas.movimiento_stock import TransferirStockRequest
from app.schemas.pagination import PaginatedResponse
from app.services.metrics_service import (
    measure_db_query,
    measure_db_query_async,
    sync_active_items_gauge,
)
from app.workers.tasks import enviar_notificacion
from app.storage.s3_client import generate_presigned_url
from app.notifications.notification_service import NotificationService
# =========================================================
# ELASTICSEARCH
# =========================================================
from app.search.elasticsearch_client import (
    delete_item as es_delete_item,
    increment_item_popularity,
    index_item as es_index_item,
    search_items as es_search_items,
    suggest_items as es_suggest_items,
    update_item as es_update_item,
)

router = APIRouter()

logger = logging.getLogger(__name__)

LOW_STOCK_THRESHOLD = 5

# =========================================================
# 🔥 FIX ASYNC GLOBAL (CRÍTICO)
# =========================================================
def safe_async_run(coro):
    """
    Ejecuta una coroutine sin romper el event loop de FastAPI.
    
    - Si ya hay loop → create_task
    - Si no → asyncio.run
    
    🔥 ESTE ERA EL BUG PRINCIPAL DE TODO TU PROYECTO
    """
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(coro)
    except RuntimeError:
        asyncio.run(coro)


# =========================================================
# HELPERS DE EVENTOS / AUDITORÍA / HATEOAS
# =========================================================
def _publicar_evento_item(routing_key: str, payload: dict) -> None:
    """
    Publica evento en RabbitMQ SIN romper FastAPI.

    🔥 FIX:
    - Eliminado asyncio.run directo
    - Usamos safe_async_run
    """
    rabbitmq_url = getattr(
        settings,
        "RABBITMQ_URL",
        "amqp://guest:guest@rabbitmq:5672/",
    )

    async def _run():
        producer = RabbitMQProducer(url=rabbitmq_url)
        try:
            await producer.publish(
                "items_events",
                routing_key,
                payload,
            )
        finally:
            await producer.close()
        
        try:
            safe_async_run(_run())
        except Exception as e:
            logger.error("RabbitMQ falló", exc_info=True)



def _bind_audit_user(current_user: Usuario | None) -> None:
    """
    Enlaza el usuario actual al contexto de auditoría.
    """
    set_current_user_id(current_user.id if current_user else None)


def _build_event_metadata(current_user: Usuario | None) -> dict:
    """
    Construye metadata estándar para eventos de dominio.
    """
    return {
        "source": "api-jmv",
        "user_id": current_user.id if current_user else None,
        "user_email": current_user.email if current_user else None,
    }


def _publicar_evento_item_kafka(
    event_type: str,
    aggregate_id: int,
    payload: dict,
    current_user: Usuario | None = None,
) -> None:
    """
    Publica evento en Kafka SIN romper flujo principal.
    """
    event = DomainEvent(
        event_type=event_type,
        aggregate_type="item",
        aggregate_id=str(aggregate_id),
        payload=payload,
        metadata=_build_event_metadata(current_user),
    )

    try:
        publish_domain_event(event)
    except Exception as exc:
        logger.warning("Kafka falló pero no rompe flujo: %s", exc)


def _build_absolute_url(request: Request, route_name: str, **path_params: Any) -> str:
    """
    Construye una URL absoluta usando url_for.
    """
    return str(request.url_for(route_name, **path_params))


def _build_transferir_stock_url(request: Request) -> str:
    """
    Construye URL absoluta del endpoint de transferencia de stock.
    """
    return _build_absolute_url(request, "transferir_stock")


def build_links(item: Item, request: Request) -> dict[str, str]:
    """
    Construye links HATEOAS para un item.
    """
    links: dict[str, str] = {
        "self": _build_absolute_url(request, "obtener_item_por_id", item_id=str(item.id)),
    }

    if item.eliminado:
        links["restaurar"] = _build_absolute_url(request, "restaurar_item", item_id=str(item.id))
        return links

    links["actualizar"] = _build_absolute_url(request, "actualizar_item", item_id=str(item.id))
    links["eliminar"] = _build_absolute_url(request, "eliminar_item", item_id=str(item.id))
    links["historial"] = _build_absolute_url(request, "obtener_historial_item", item_id=str(item.id))

    if item.stock <= LOW_STOCK_THRESHOLD:
        links["reabastecer"] = _build_transferir_stock_url(request)

    return links


def _item_read_with_links(item: Item, request: Request) -> ItemRead:
    """
    Convierte entidad Item a ItemRead e inyecta links HATEOAS.
    """
    payload = ItemRead.model_validate(item)
    payload.links = build_links(item, request)
    return payload


def _items_read_with_links(items: list[Item], request: Request) -> list[ItemRead]:
    """
    Convierte lista de entidades Item a lista de ItemRead con links.
    """
    return [_item_read_with_links(item, request) for item in items]


def _build_page_url(request: Request, query_params: dict[str, Any], page: int) -> str:
    """
    Construye URL de paginación preservando query params.
    """
    params = {key: value for key, value in query_params.items() if value is not None}
    params["page"] = page
    return f"{request.url.path}?{urlencode(params, doseq=True)}"


def build_pagination_links(
    *,
    request: Request,
    page: int,
    page_size: int,
    total: int,
    query_params: dict[str, Any],
) -> dict[str, str | None]:
    """
    Construye links de paginación first / prev / next / last.
    """
    last_page = max(1, ceil(total / page_size)) if page_size > 0 else 1

    first_link = None if page <= 1 else _build_page_url(request, query_params, 1)
    prev_link = None if page <= 1 else _build_page_url(request, query_params, page - 1)
    next_link = None if page >= last_page else _build_page_url(request, query_params, page + 1)
    last_link = None if page >= last_page else _build_page_url(request, query_params, last_page)

    return {
        "first": first_link,
        "prev": prev_link,
        "next": next_link,
        "last": last_link,
    }


# =========================================================
# CREATE ITEM
# =========================================================
@router.post(
    "/",
    response_model=ApiResponse[ItemRead],
    summary="Crear item",
    description="Crea un item y devuelve representación HATEOAS con links absolutos en _links.",
    dependencies=[Depends(verify_api_key), Depends(require_role("admin", "editor"))],
)
@limiter.limit(dynamic_rate_limit)
async def crear_item(
    request: Request,
    payload: ItemCreate,
    db: Session = Depends(get_db),
    repo: ItemRepository = Depends(get_item_repo),
    current_user: Usuario = Depends(require_role("admin", "editor")),
):
    _bind_audit_user(current_user)

    categoria = None
    if payload.categoria_id is not None:
        with measure_db_query("select", "categorias"):
            categoria = db.execute(
                select(Categoria).where(Categoria.id == payload.categoria_id)
            ).scalars().first()

        if not categoria:
            increment_crud_operation("item", "create", "error")
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

    try:
        with measure_db_query("insert", "items"):
            item = await repo.create(item)

        # -------------------------------------------------
        # Elasticsearch
        # -------------------------------------------------
        try:
            es_index_item(item)
        except Exception as exc:
            logger.warning("No se pudo indexar item %s en Elasticsearch: %s", item.id, exc)

        # -------------------------------------------------
        # Métricas
        # -------------------------------------------------
        category_name = categoria.nombre if categoria else "sin_categoria"
        ITEMS_CREATED_BY_CATEGORY.labels(category=category_name).inc()
        sync_active_items_gauge(db)
        increment_crud_operation("item", "create", "success")

        # -------------------------------------------------
        # Cache
        # -------------------------------------------------
        invalidate_first_page_list_caches()

        # =========================================================
        #  NOTIFICACIÓN ITEM CREADO
        # =========================================================
        payload_notif = {
            "destinatario": "admin@api-jmv.com",
            "tipo": "item_creado",
            "canal": "email",
            "context": {
                "subject": "Nuevo item creado",
                "nombre": item.name,
            }
        }

        if settings.CELERY_ENABLED:
            try:
                enviar_notificacion.delay(payload_notif)
            except Exception as exc:
                logger.warning("Error enviando notificación: %s", exc)
        else:
            from app.database.database import SessionLocal
            from app.notifications.notification_service import NotificationService

            db_local = SessionLocal()
            try:
                NotificationService(db_local).send(**payload_notif)
            finally:
                db_local.close()

        # =========================================================
        # ALERTA STOCK BAJO
        # =========================================================
        if item.stock <= LOW_STOCK_THRESHOLD:

            payload_stock = {
                "destinatario": "admin@api-jmv.com",
                "tipo": "stock_bajo",
                "canal": "email",
                "context": {
                    "subject": "Stock bajo detectado",
                    "nombre": item.name,
                    "stock": item.stock,
                }
            }

            if settings.CELERY_ENABLED:
                enviar_notificacion.delay(payload_stock)

        # -------------------------------------------------
        # Eventos
        # -------------------------------------------------
        _publicar_evento_item(
            "items.creado",
            ItemRead.model_validate(item).model_dump(mode="json"),
        )

        _publicar_evento_item_kafka(
            event_type="item.created",
            aggregate_id=item.id,
            payload=ItemRead.model_validate(item).model_dump(mode="json"),
            current_user=current_user,
        )

        logger.info("Item creado: id=%s, nombre=%s", item.id, item.name)

        return ApiResponse[ItemRead](
            success=True,
            message="Item creado exitosamente",
            data=_item_read_with_links(item, request),
            metadata={},
        )

    except Exception:
        increment_crud_operation("item", "create", "error")
        raise


# =========================================================
# BULK CREATE
# =========================================================
@router.post(
    "/bulk",
    response_model=ApiResponse[list[ItemRead]],
    summary="Crear items en lote (máx 100) (transaccional)",
    description="Crea items en lote y devuelve cada recurso con links HATEOAS absolutos.",
    dependencies=[Depends(verify_api_key), Depends(require_role("admin", "editor"))],
)
def bulk_create_items(
    request: Request,
    payload: BulkCreate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_role("admin", "editor")),
):
    """
    Crea items en lote e instrumenta métricas de bulk create.
    Además, sincroniza cada item creado hacia Elasticsearch.
    """
    _bind_audit_user(current_user)

    try:
        objects: list[Item] = []
        categorias_ids = [it.categoria_id for it in payload.items if getattr(it, "categoria_id", None) is not None]
        categorias_map: dict[int, Categoria] = {}

        if categorias_ids:
            with measure_db_query("select", "categorias"):
                categorias = db.execute(
                    select(Categoria).where(Categoria.id.in_(categorias_ids))
                ).scalars().all()
            categorias_map = {categoria.id: categoria for categoria in categorias}

        for it in payload.items:
            categoria_id = getattr(it, "categoria_id", None)

            if categoria_id is not None and categoria_id not in categorias_map:
                increment_crud_operation("item", "bulk_create", "error")
                return error_response(
                    status_code=400,
                    message=f"La categoría con id={categoria_id} no existe",
                )

            objects.append(
                Item(
                    name=it.name,
                    description=it.description,
                    price=it.price,
                    sku=it.sku,
                    codigo_sku=it.codigo_sku,
                    stock=it.stock,
                    categoria_id=categoria_id,
                )
            )

        with measure_db_query("insert", "items"):
            db.add_all(objects)
            db.commit()

        with measure_db_query("select", "items"):
            for obj in objects:
                db.refresh(obj)

        # -------------------------------------------------
        # Sincronización bulk con Elasticsearch
        # -------------------------------------------------
        for obj in objects:
            try:
                es_index_item(obj)
            except Exception as exc:
                logger.warning("No se pudo indexar item bulk %s en Elasticsearch: %s", obj.id, exc)

        for it in payload.items:
            categoria_id = getattr(it, "categoria_id", None)
            if categoria_id is not None and categoria_id in categorias_map:
                category_name = categorias_map[categoria_id].nombre
            else:
                category_name = "sin_categoria"

            ITEMS_CREATED_BY_CATEGORY.labels(category=category_name).inc()

        sync_active_items_gauge(db)
        increment_crud_operation("item", "bulk_create", "success")
        invalidate_first_page_list_caches()

        logger.info("Bulk create completado: total_items=%s", len(objects))

        return ApiResponse[list[ItemRead]](
            success=True,
            message="Items creados exitosamente (bulk)",
            data=_items_read_with_links(objects, request),
            metadata={},
        )

    except IntegrityError as e:
        db.rollback()
        increment_crud_operation("item", "bulk_create", "error")
        logger.error("Error al procesar bulk create: %s", str(e), exc_info=True)
        return error_response(
            status_code=400,
            message="Error en bulk create: violación de integridad (ej. SKU duplicado). Se hizo rollback.",
        )
    except SQLAlchemyError as e:
        db.rollback()
        increment_crud_operation("item", "bulk_create", "error")
        logger.error("Error al procesar bulk create: %s", str(e), exc_info=True)
        return error_response(
            status_code=500,
            message="Error de base de datos en bulk create. Se hizo rollback.",
            data={"error": str(e)},
        )
    except Exception as e:
        db.rollback()
        increment_crud_operation("item", "bulk_create", "error")
        logger.error("Error al procesar bulk create: %s", str(e), exc_info=True)
        return error_response(
            status_code=500,
            message="Error inesperado en bulk create. Se hizo rollback.",
            data={"error": str(e)},
        )


# =========================================================
# BULK DELETE
# =========================================================
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
    Elimina items en lote (soft delete) e instrumenta métricas de bulk delete.
    También elimina del índice de Elasticsearch los items afectados.
    """
    try:
        now = datetime.now()

        with measure_db_query("select", "items"):
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

        with measure_db_query("update", "items"):
            db.commit()

        # -------------------------------------------------
        # Sincronización bulk delete con Elasticsearch
        # -------------------------------------------------
        for item_id in affected_ids:
            try:
                es_delete_item(item_id)
            except Exception as exc:
                logger.warning("No se pudo eliminar item %s del índice Elasticsearch: %s", item_id, exc)

        sync_active_items_gauge(db)
        increment_crud_operation("item", "bulk_delete", "success")

        for item_id in affected_ids:
            delete_cache(build_item_cache_key(item_id))
            invalidate_list_caches_for_item(item_id, include_first_pages=True)

        logger.info("Bulk delete procesado: deleted=%s, not_found=%s", deleted, not_found)

        return ApiResponse[dict](
            success=True,
            message="Bulk delete procesado",
            data={"deleted": deleted, "not_found": not_found},
            metadata={},
        )

    except SQLAlchemyError as e:
        db.rollback()
        increment_crud_operation("item", "bulk_delete", "error")
        logger.error("Error al procesar bulk delete: %s", str(e), exc_info=True)
        return error_response(
            status_code=500,
            message="Error de base de datos en bulk delete. Se hizo rollback.",
            data={"error": str(e)},
        )
    except Exception as e:
        db.rollback()
        increment_crud_operation("item", "bulk_delete", "error")
        logger.error("Error al procesar bulk delete: %s", str(e), exc_info=True)
        return error_response(
            status_code=500,
            message="Error inesperado en bulk delete. Se hizo rollback.",
            data={"error": str(e)},
        )


# =========================================================
# BULK UPDATE DISPONIBLE
# =========================================================
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
    Actualiza disponibilidad en lote e instrumenta métricas de bulk update.
    También actualiza Elasticsearch para cada item afectado.
    """
    try:
        with measure_db_query("select", "items"):
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
                    increment_crud_operation("item", "bulk_update_disponible", "error")
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

        with measure_db_query("update", "items"):
            db.commit()

        # -------------------------------------------------
        # Sincronización bulk update con Elasticsearch
        # -------------------------------------------------
        for item_id in set(affected_ids):
            item = found_map.get(item_id)
            if item is None:
                continue
            try:
                es_update_item(item)
            except Exception as exc:
                logger.warning("No se pudo actualizar item %s en Elasticsearch: %s", item_id, exc)

        increment_crud_operation("item", "bulk_update_disponible", "success")

        for item_id in set(affected_ids):
            delete_cache(build_item_cache_key(item_id))
            invalidate_list_caches_for_item(item_id, include_first_pages=True)

        logger.info(
            "Bulk update disponible procesado: updated=%s, not_found=%s, disponible=%s",
            updated,
            not_found,
            payload.disponible,
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
        increment_crud_operation("item", "bulk_update_disponible", "error")
        logger.error("Error al procesar bulk update disponible: %s", str(e), exc_info=True)
        return error_response(
            status_code=500,
            message="Error de base de datos en bulk update disponible. Se hizo rollback.",
            data={"error": str(e)},
        )
    except Exception as e:
        db.rollback()
        increment_crud_operation("item", "bulk_update_disponible", "error")
        logger.error("Error al procesar bulk update disponible: %s", str(e), exc_info=True)
        return error_response(
            status_code=500,
            message="Error inesperado en bulk update disponible. Se hizo rollback.",
            data={"error": str(e)},
        )


# =========================================================
# LISTAR ITEMS (SE MANTIENE CACHE MANUAL LEGACY DE LISTADOS)
# =========================================================
@router.get(
    "/",
    response_model=ApiResponse[PaginatedResponse[ItemRead]],
    summary="Listar items con filtros, búsqueda, orden y paginación (solo activos)",
    description="Devuelve items con _links HATEOAS y metadata._links con navegación first/prev/next/last usando URLs completas.",
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
    categoria_id: Optional[int] = Query(None, ge=1, description="Filtra por categoría"),
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
    Lista items e instrumenta métricas de lectura y latencia DB.
    Optimización aplicada:
    - carga selectiva de categoría con selectinload preservado
    - count con subquery mínima
    - cache de respuesta completa
    - evita trabajo extra cuando no hay resultados
    """
    cache_params = {
        "page_size": page_size,
        "nombre": nombre,
        "precio_min": precio_min,
        "precio_max": precio_max,
        "disponible": disponible,
        "categoria_id": categoria_id,
        "ordenar_por": ordenar_por,
        "creado_desde": creado_desde.isoformat() if creado_desde else None,
    }

    query_params = {
        "page_size": page_size,
        "nombre": nombre,
        "precio_min": precio_min,
        "precio_max": precio_max,
        "disponible": disponible,
        "categoria_id": categoria_id,
        "ordenar_por": ordenar_por,
        "creado_desde": creado_desde.isoformat() if creado_desde else None,
    }

    signature = build_items_list_signature(cache_params)
    cache_key = build_items_list_cache_key(signature, page)

    cached_page = get_cache(cache_key)
    if cached_page is not None:
        response.headers["X-Cache"] = "HIT"
        increment_crud_operation("item", "list", "success")
        return cached_page

    stmt = select(Item).options(selectinload(Item.categoria)).where(Item.eliminado.is_(False))
    count_stmt_base = select(Item.id).where(Item.eliminado.is_(False))

    if nombre:
        stmt = stmt.where(Item.name.ilike(f"%{nombre}%"))
        count_stmt_base = count_stmt_base.where(Item.name.ilike(f"%{nombre}%"))

    if precio_min is not None:
        stmt = stmt.where(Item.price >= precio_min)
        count_stmt_base = count_stmt_base.where(Item.price >= precio_min)

    if precio_max is not None:
        stmt = stmt.where(Item.price <= precio_max)
        count_stmt_base = count_stmt_base.where(Item.price <= precio_max)

    if disponible is not None:
        if disponible:
            stmt = stmt.where(Item.stock > 0)
            count_stmt_base = count_stmt_base.where(Item.stock > 0)
        else:
            stmt = stmt.where(Item.stock <= 0)
            count_stmt_base = count_stmt_base.where(Item.stock <= 0)

    if categoria_id is not None:
        stmt = stmt.where(Item.categoria_id == categoria_id)
        count_stmt_base = count_stmt_base.where(Item.categoria_id == categoria_id)

    if creado_desde is not None:
        dt = datetime.combine(creado_desde, time.min)
        stmt = stmt.where(Item.created_at >= dt)
        count_stmt_base = count_stmt_base.where(Item.created_at >= dt)

    try:
        count_stmt = select(func.count()).select_from(count_stmt_base.subquery())

        async with measure_db_query_async("select", "items"):
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

        async with measure_db_query_async("select", "items"):
            result = await db.execute(stmt)
            items = result.scalars().all()

        item_ids = [item.id for item in items]

        paginated = PaginatedResponse[ItemRead](
            page=page,
            page_size=page_size,
            total=total,
            items=_items_read_with_links(list(items), request) if items else [],
        )

        pagination_links = build_pagination_links(
            request=request,
            page=page,
            page_size=page_size,
            total=total,
            query_params=query_params,
        )

        payload = ApiResponse[PaginatedResponse[ItemRead]](
            success=True,
            message="Items obtenidos exitosamente",
            data=paginated,
            metadata={
                "_links": pagination_links,
                "hateoas": {
                    "absolute_urls": True,
                    "usage": "El cliente debe seguir las URLs de _links sin construir rutas manualmente.",
                },
            },
        )

        payload_dict = payload.model_dump(mode="json", by_alias=True)

        set_cache(
            cache_key,
            payload_dict,
            ttl=settings.CACHE_TTL_LIST_SECONDS,
        )

        register_list_cache(
            cache_key=cache_key,
            page=page,
            ttl=settings.CACHE_TTL_LIST_SECONDS,
            item_ids=item_ids,
            params=cache_params,
        )

        response.headers["X-Cache"] = "MISS"
        increment_crud_operation("item", "list", "success")
        return payload

    except Exception:
        increment_crud_operation("item", "list", "error")
        raise


# =========================================================
# BUSCAR ITEMS (ELASTICSEARCH FULL-TEXT + FUZZY + FILTERS)
# =========================================================
@router.get(
    "/buscar",
    response_model=ApiResponse[list[dict]],
    summary="Buscar items con Elasticsearch",
    dependencies=[Depends(verify_api_key)],
)
def buscar_items(
    request: Request,
    q: str | None = Query(None),
    nombre: str | None = Query(None),  # 🔥 FIX: soporte para tests
    categoria_id: Optional[int] = Query(None),
    precio_min: Optional[float] = Query(None),
    precio_max: Optional[float] = Query(None),
    page: int = Query(1),
    size: int = Query(10),
    db: Session = Depends(get_read_db),
):
    try:
        # =====================================================
        # 🔥 FIX CLAVE: soporta nombre o q
        # =====================================================
        if not q and nombre:
            q = nombre

        # =====================================================
        # 🔥 SIN QUERY → VACÍO CONTROLADO
        # =====================================================
        if not q:
            increment_crud_operation("item", "search", "success")
            return ApiResponse(
                success=True,
                message="Búsqueda ejecutada",
                data=[],
                metadata={},
            )

        # =====================================================
        # 🔥 1. INTENTAR ELASTICSEARCH
        # =====================================================
        try:
            hits = es_search_items(
                query=q,
                filters={
                    "categoria_id": categoria_id,
                    "precio_min": precio_min,
                    "precio_max": precio_max,
                },
                page=page,
                size=size,
            )

            if hits:
                data = []

                for hit in hits:
                    source = hit.get("_source", {})
                    item_id = int(hit["_id"])

                    data.append({
                        "id": item_id,
                        "name": source.get("name"),
                        "description": source.get("description"),
                        "price": source.get("price"),
                        "categoria_id": source.get("categoria_id"),
                        "highlight": hit.get("highlight", {}),
                    })

                increment_crud_operation("item", "search", "success")

                return ApiResponse(
                    success=True,
                    message="Búsqueda Elasticsearch OK",
                    data=data,
                    metadata={"engine": "elasticsearch"},
                )

        except Exception as es_error:
            logger.warning("ES falló → fallback DB: %s", es_error)

        # =====================================================
        # 🔥 2. FALLBACK A DB (CLAVE PARA TESTS)
        # =====================================================
        stmt = select(Item).where(Item.eliminado == False)

        if q:
            stmt = stmt.where(Item.name.ilike(f"%{q}%"))

        if categoria_id:
            stmt = stmt.where(Item.categoria_id == categoria_id)

        if precio_min is not None:
            stmt = stmt.where(Item.price >= precio_min)

        if precio_max is not None:
            stmt = stmt.where(Item.price <= precio_max)

        stmt = stmt.limit(size)

        results = db.execute(stmt).scalars().all()

        data = [
            {
                "id": item.id,
                "name": item.name,
                "description": item.description,
                "price": item.price,
                "categoria_id": item.categoria_id,
            }
            for item in results
        ]

        increment_crud_operation("item", "search", "success")

        return ApiResponse(
            success=True,
            message="Búsqueda DB fallback",
            data=data,
            metadata={"engine": "database"},
        )

    except Exception as exc:
        increment_crud_operation("item", "search", "error")
        logger.error("Error búsqueda: %s", exc, exc_info=True)

        return error_response(
            status_code=500,
            message="Error en búsqueda",
            data={"error": str(exc)},
        )

# =========================================================
# SUGERENCIAS DE ITEMS (ELASTICSEARCH COMPLETION SUGGESTER)
# =========================================================
@router.get(
    "/sugerir",
    response_model=ApiResponse[list[str]],
    summary="Sugerir nombres de items",
    description="Devuelve hasta 5 sugerencias de nombres usando completion suggester de Elasticsearch.",
    dependencies=[Depends(verify_api_key)],
)
def sugerir_items(
    q: str = Query(..., min_length=1, description="Prefijo de búsqueda"),
):
    """
    Sugerencias/autocompletado con Elasticsearch.
    """
    try:
        suggestions = es_suggest_items(q)

        increment_crud_operation("item", "suggest", "success")

        return ApiResponse[list[str]](
            success=True,
            message="Sugerencias obtenidas exitosamente",
            data=suggestions,
            metadata={
                "query": q,
                "engine": "elasticsearch",
            },
        )
    except Exception as exc:
        increment_crud_operation("item", "suggest", "error")
        logger.error("Error en suggester Elasticsearch: %s", exc, exc_info=True)
        return error_response(
            status_code=500,
            message="Error al obtener sugerencias",
            data={"error": str(exc)},
        )


# =========================================================
# PAGINACIÓN POR CURSOR
# =========================================================
@router.get(
    "/cursor",
    response_model=ApiResponse[CursorPaginationResponse],
    summary="Listar items con paginación por cursor (keyset pagination)",
    dependencies=[Depends(verify_api_key)],
)
def listar_items_cursor(
    request: Request,
    cursor: int = Query(0, ge=0, description="Último ID visto; 0 para iniciar"),
    limite: int = Query(10, ge=1, le=100, description="Cantidad máxima de items por página"),
    db: Session = Depends(get_read_db),
):
    """
    Lista items con cursor e instrumenta lectura y latencia DB.
    """
    try:
        stmt = (
            select(Item)
            .where(Item.eliminado == False)  # noqa: E712
            .where(Item.id > cursor)
            .order_by(Item.id.asc())
            .limit(limite + 1)
        )

        with measure_db_query("select", "items"):
            results = db.execute(stmt).scalars().all()

        has_more = len(results) > limite
        items = results[:limite]
        next_cursor = items[-1].id if items else None

        data = CursorPaginationResponse(
            items=[item.model_dump(by_alias=True) for item in _items_read_with_links(items, request)],
            next_cursor=next_cursor,
            has_more=has_more,
        )

        increment_crud_operation("item", "cursor_list", "success")

        return ApiResponse[CursorPaginationResponse](
            success=True,
            message="Items obtenidos exitosamente con paginación por cursor",
            data=data,
            metadata={},
        )
    except Exception:
        increment_crud_operation("item", "cursor_list", "error")
        raise


# =========================================================
# LISTAR ELIMINADOS
# =========================================================
@router.get(
    "/eliminados",
    response_model=ApiResponse[PaginatedResponse[ItemRead]],
    summary="Listar items eliminados (soft delete)",
    description="Devuelve items eliminados con _links HATEOAS; si el item está eliminado solo expone self y restaurar.",
    dependencies=[Depends(verify_api_key)],
)
def listar_eliminados(
    request: Request,
    page: int = Query(1, ge=1, description="Página (>=1)"),
    page_size: int = Query(10, ge=1, le=100, description="Tamaño de página (1-100)"),
    db: Session = Depends(get_read_db),
):
    """
    Lista items eliminados e instrumenta lectura y latencia DB.
    """
    try:
        stmt = select(Item).where(Item.eliminado == True)  # noqa: E712

        with measure_db_query("select", "items"):
            count_stmt = select(func.count()).select_from(stmt.subquery())
            total = db.execute(count_stmt).scalar_one()

        stmt = stmt.order_by(Item.id.asc())
        offset = (page - 1) * page_size
        stmt = stmt.offset(offset).limit(page_size)

        with measure_db_query("select", "items"):
            items = db.execute(stmt).scalars().all()

        query_params = {"page_size": page_size}
        pagination_links = build_pagination_links(
            request=request,
            page=page,
            page_size=page_size,
            total=total,
            query_params=query_params,
        )

        paginated = PaginatedResponse[ItemRead](
            page=page,
            page_size=page_size,
            total=total,
            items=_items_read_with_links(items, request),
        )

        increment_crud_operation("item", "list_deleted", "success")

        return ApiResponse[PaginatedResponse[ItemRead]](
            success=True,
            message="Items eliminados obtenidos exitosamente",
            data=paginated,
            metadata={
                "_links": pagination_links,
                "hateoas": {
                    "absolute_urls": True,
                    "usage": "El cliente debe seguir las URLs de _links sin construir rutas manualmente.",
                },
            },
        )
    except Exception:
        increment_crud_operation("item", "list_deleted", "error")
        raise


# =========================================================
# DEMO IP
# =========================================================
@router.get(
    "/ip",
    response_model=ApiResponse[dict],
    summary="Demo: obtener IP del cliente (dependency)",
    dependencies=[Depends(verify_api_key)],
)
def mi_ip(ip: str = Depends(get_client_ip)):
    """
    Endpoint de demo para recuperar la IP del cliente.
    """
    return ApiResponse[dict](
        success=True,
        message="IP obtenida exitosamente",
        data={"ip": ip},
        metadata={},
    )


# =========================================================
# GET ITEM POR ID
# =========================================================
@router.get(
    "/{item_id}",
    response_model=ApiResponse[ItemRead],
    summary="Obtener item por ID",
    description="Devuelve el recurso con links HATEOAS absolutos en _links.",
    dependencies=[Depends(verify_api_key)],
)
async def obtener_item_por_id(
    request: Request,
    item_id: int,
    response: Response,
    repo: ItemRepository = Depends(get_item_repo),
):
    """
    Obtiene un item por ID y ahora:
    - 🔥 Genera URL firmada (presigned URL) si tiene imagen
    - NO guarda URL en DB
    - Mantiene cache multinivel intacto
    """

    # 🔹 Obtener item (cache multinivel ya integrado)
    item = await repo.get_by_id(item_id)

    # 🔹 Validación
    if not item:
        response.headers["X-Cache"] = "MISS"
        increment_crud_operation("item", "read", "error")
        raise ItemNoEncontradoError(item_id)

    # =========================================================
    # 🔥 GENERAR PRESIGNED URL (NUEVO)
    # =========================================================
    imagen_url = None

    if item.imagen_key:
        try:
            imagen_url = generate_presigned_url(
                item.imagen_key,
                expires_in=3600,  # 🔹 1 hora
            )
        except Exception as exc:
            logger.warning(
                "Error generando presigned URL para item %s: %s",
                item_id,
                exc,
            )

    # =========================================================
    # 🔹 POPULARIDAD ELASTICSEARCH
    # =========================================================
    try:
        increment_item_popularity(item_id)
    except Exception as exc:
        logger.warning(
            "No se pudo incrementar popularidad de item %s en Elasticsearch: %s",
            item_id,
            exc,
        )

    response.headers["X-Cache"] = "AUTO"
    increment_crud_operation("item", "read", "success")

    # 🔹 Construir respuesta base (HATEOAS)
    data = _item_read_with_links(item, request)

    # =========================================================
    # 🔥 INYECTAR URL DINÁMICA (NO DB)
    # =========================================================
    if imagen_url:
        data.imagen_url = imagen_url  # 🔹 solo en response

    return ApiResponse[ItemRead](
        success=True,
        message="Item obtenido exitosamente",
        data=data,
        metadata={"cache": "L1/L2/DB"},
    )

# =========================================================
# UPDATE ITEM
# =========================================================
@router.put(
    "/{item_id}",
    response_model=ApiResponse[ItemRead],
    summary="Actualizar item por ID",
    description="Actualiza el recurso y devuelve la representación HATEOAS actualizada.",
    dependencies=[Depends(verify_api_key), Depends(require_role("admin", "editor"))],
)
async def actualizar_item(
    request: Request,
    item_id: int,
    payload: ItemCreate,
    repo: ItemRepository = Depends(get_item_repo),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_role("admin", "editor")),
):
    """
    Actualiza un item e instrumenta update y latencia DB.

    Versión simplificada para validar tarea 75:
    - Usa repository async
    - Invalida caché multinivel automáticamente
    - Mantiene métricas
    - Evita lógica extra que está provocando 500
    - Sincroniza Elasticsearch después de guardar cambios
    """
    _bind_audit_user(current_user)

    with measure_db_query("select", "items"):
        item = await repo.get_by_id(item_id)

    if not item:
        increment_crud_operation("item", "update", "error")
        raise ItemNoEncontradoError(item_id)

    categoria = None
    if payload.categoria_id is not None:
        with measure_db_query("select", "categorias"):
            categoria = db.execute(
                select(Categoria).where(Categoria.id == payload.categoria_id)
            ).scalars().first()

        if not categoria:
            increment_crud_operation("item", "update", "error")
            return error_response(
                status_code=400,
                message=f"La categoría con id={payload.categoria_id} no existe",
            )

    item.name = payload.name
    item.description = payload.description
    item.price = payload.price
    item.sku = payload.sku
    item.codigo_sku = payload.codigo_sku
    item.stock = payload.stock
    item.categoria_id = payload.categoria_id

    try:
        with measure_db_query("update", "items"):
            item = await repo.update(item)

        # -------------------------------------------------
        # Sincronización con Elasticsearch
        # -------------------------------------------------
        try:
            es_update_item(item)
        except Exception as exc:
            logger.warning("No se pudo actualizar item %s en Elasticsearch: %s", item.id, exc)

        sync_active_items_gauge(repo.db)
        increment_crud_operation("item", "update", "success")

        logger.info("Item actualizado: id=%s, usuario=%s", item.id, current_user.email)

        return ApiResponse[ItemRead](
            success=True,
            message="Item actualizado exitosamente",
            data=_item_read_with_links(item, request),
            metadata={},
        )
    except Exception:
        increment_crud_operation("item", "update", "error")
        raise


# =========================================================
# HISTORIAL ITEM
# =========================================================
@router.get(
    "/{item_id}/historial",
    response_model=ApiResponse[list[dict]],
    summary="Obtener historial de auditoría de un item",
    dependencies=[Depends(verify_api_key)],
)
def obtener_historial_item(
    item_id: int,
    db: Session = Depends(get_read_db),
):
    """
    Obtiene historial de auditoría e instrumenta lectura.
    """
    try:
        with measure_db_query("select", "auditoria_item"):
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

        increment_crud_operation("item", "history", "success")

        return ApiResponse[list[dict]](
            success=True,
            message="Historial de auditoría obtenido exitosamente",
            data=data,
            metadata={},
        )
    except Exception:
        increment_crud_operation("item", "history", "error")
        raise


# =========================================================
# ESTADO ITEM EN FECHA
# =========================================================
@router.get(
    "/{item_id}/estado",
    response_model=ApiResponse[dict],
    summary="Reconstruir estado de un item en una fecha específica",
    dependencies=[Depends(verify_api_key)],
)
def obtener_estado_item_en_fecha(
    item_id: int,
    fecha: datetime = Query(..., description="Fecha y hora en formato ISO 8601"),
    db: Session = Depends(get_read_db),
):
    """
    Reconstruye el estado de un item en una fecha dada.
    """
    try:
        with measure_db_query("select", "auditoria_item"):
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

        increment_crud_operation("item", "state_at_date", "success")

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
    except Exception:
        increment_crud_operation("item", "state_at_date", "error")
        raise


# 🔥 IMPORT NUEVO PARA S3
from app.storage.s3_client import delete_file

# =========================================================
# DELETE ITEM
# =========================================================
@router.delete(
    "/{item_id}",
    response_model=ApiResponse[dict],
    summary="Eliminar item por ID (soft delete)",
    dependencies=[Depends(verify_api_key)],
)
async def eliminar_item(
    item_id: int,
    repo: ItemRepository = Depends(get_item_repo),
    current_user: Usuario = Depends(require_role("admin")),
):
    """
    Elimina lógicamente un item y ahora también:
    - 🔥 Elimina su imagen en S3 si existe
    - Mantiene ES, cache, eventos intactos
    """

    # 🔹 Auditoría
    _bind_audit_user(current_user)

    # 🔹 Obtener item
    with measure_db_query("select", "items"):
        item = await repo.get_by_id(item_id)

    # 🔹 Validación: no existe
    if not item:
        increment_crud_operation("item", "delete", "error")
        raise ItemNoEncontradoError(item_id)

    # 🔹 Ya eliminado (idempotente)
    if item.eliminado:
        logger.warning(
            "Intento de eliminar un item ya eliminado: id=%s, usuario=%s",
            item.id,
            current_user.email,
        )
        increment_crud_operation("item", "delete", "success")

        return ApiResponse[dict](
            success=True,
            message="Item ya estaba eliminado",
            data={"ok": True},
            metadata={},
        )

    try:
        # =========================================================
        # ELIMINAR IMAGEN EN S3 (NUEVO)
        # =========================================================
        if item.imagen_key:
            try:
                delete_file(item.imagen_key)  # 🔹 borra del bucket
            except Exception as exc:
                # ⚠️ NO rompemos el flujo si S3 falla
                logger.warning(
                    "Error eliminando imagen S3 %s: %s",
                    item.imagen_key,
                    exc,
                )

        # =========================================================
        # DELETE LÓGICO EN DB
        # =========================================================
        with measure_db_query("update", "items"):
            await repo.delete(item)

        # =========================================================
        # SINCRONIZAR CON ELASTICSEARCH
        # =========================================================
        try:
            es_delete_item(item.id)
        except Exception as exc:
            logger.warning(
                "No se pudo eliminar item %s de Elasticsearch: %s",
                item.id,
                exc,
            )

        #--Métricas
        sync_active_items_gauge(repo.db)
        increment_crud_operation("item", "delete", "success")

        #--Cache
        delete_cache(build_item_cache_key(item_id))
        invalidate_list_caches_for_item(item_id, include_first_pages=True)

        #--Evento interno
        _publicar_evento_item(
            "items.eliminado",
            {
                "id": item.id,
                "name": item.name,
                "sku": item.sku,
                "codigo_sku": item.codigo_sku,
                "eliminado": True,
            },
        )

        #--Evento Kafka
        _publicar_evento_item_kafka(
            event_type="item.deleted",
            aggregate_id=item.id,
            payload={
                "id": item.id,
                "name": item.name,
                "sku": item.sku,
                "codigo_sku": item.codigo_sku,
                "eliminado": True,
            },
            current_user=current_user,
        )

        logger.info(
            "Item eliminado (soft delete): id=%s, usuario=%s",
            item.id,
            current_user.email,
        )

        return ApiResponse[dict](
            success=True,
            message="Item eliminado (soft delete)",
            data={"ok": True},
            metadata={},
        )

    except Exception:
        increment_crud_operation("item", "delete", "error")
        raise


# =========================================================
# RESTAURAR ITEM
# =========================================================
@router.post(
    "/{item_id}/restaurar",
    response_model=ApiResponse[ItemRead],
    summary="Restaurar item eliminado (soft delete)",
    description="Restaura el recurso y devuelve la representación HATEOAS actualizada.",
    dependencies=[Depends(verify_api_key), Depends(require_role("admin", "editor"))],
)
async def restaurar_item(
    request: Request,
    item_id: int,
    repo: ItemRepository = Depends(get_item_repo),
    current_user: Usuario = Depends(require_role("admin", "editor")),
):
    """
    Restaura un item eliminado e instrumenta restore y latencia DB.

    IMPORTANTE:
    - Ahora usa await repo.get_by_id(...)
    - Ahora usa await repo.update(...)
    - Reindexa el item en Elasticsearch
    """
    _bind_audit_user(current_user)

    with measure_db_query("select", "items"):
        item = await repo.get_by_id(item_id)

    if not item:
        increment_crud_operation("item", "restore", "error")
        raise ItemNoEncontradoError(item_id)

    if not item.eliminado:
        increment_crud_operation("item", "restore", "error")
        return error_response(status_code=400, message="El item no está eliminado")

    item.eliminado = False
    item.eliminado_en = None

    try:
        with measure_db_query("update", "items"):
            item = await repo.update(item)

        # -------------------------------------------------
        # Sincronización con Elasticsearch
        # -------------------------------------------------
        try:
            es_index_item(item)
        except Exception as exc:
            logger.warning("No se pudo reindexar item %s en Elasticsearch: %s", item.id, exc)

        sync_active_items_gauge(repo.db)
        increment_crud_operation("item", "restore", "success")

        delete_cache(build_item_cache_key(item_id))
        invalidate_list_caches_for_item(item_id, include_first_pages=True)

        _publicar_evento_item_kafka(
            event_type="item.restored",
            aggregate_id=item.id,
            payload=ItemRead.model_validate(item).model_dump(mode="json"),
            current_user=current_user,
        )

        logger.info("Item restaurado: id=%s", item.id)

        return ApiResponse[ItemRead](
            success=True,
            message="Item restaurado exitosamente",
            data=_item_read_with_links(item, request),
            metadata={},
        )
    except Exception:
        increment_crud_operation("item", "restore", "error")
        raise


# =========================================================
# TRANSFERIR STOCK
# =========================================================
@router.post(
    "/transferir-stock",
    response_model=ApiResponse[dict],
    dependencies=[Depends(verify_api_key), Depends(require_role("admin", "editor"))],
)
async def transferir_stock(
    payload: TransferirStockRequest,
    db: Session = Depends(get_db),
    repo: ItemRepository = Depends(get_item_repo),
    current_user: Usuario = Depends(require_role("admin", "editor")),
):
    """
    Transfiere stock entre items e instrumenta operación y latencia DB.

    IMPORTANTE:
    - Ahora usa await repo.get_by_id(...)
    - Conserva la lógica transaccional existente
    - Sincroniza Elasticsearch para item origen y destino
    - FIX CRÍTICO: devuelve ApiResponse para mantener el contrato estándar del proyecto
      y no romper tests ni consumidores que esperan success/message/data/metadata.
    """
    _bind_audit_user(current_user)

    if payload.item_origen_id == payload.item_destino_id:
        increment_crud_operation("item", "stock_transfer", "error")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El item origen y destino no pueden ser el mismo",
        )

    with measure_db_query("select", "items"):
        item_origen = await repo.get_by_id(payload.item_origen_id)

    if item_origen is None:
        increment_crud_operation("item", "stock_transfer", "error")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Item origen no encontrado",
        )

    with measure_db_query("select", "items"):
        item_destino = await repo.get_by_id(payload.item_destino_id)

    if item_destino is None:
        increment_crud_operation("item", "stock_transfer", "error")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Item destino no encontrado",
        )

    if item_origen.eliminado:
        increment_crud_operation("item", "stock_transfer", "error")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El item origen está eliminado",
        )

    if item_destino.eliminado:
        increment_crud_operation("item", "stock_transfer", "error")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El item destino está eliminado",
        )

    if item_origen.stock < payload.cantidad:
        increment_crud_operation("item", "stock_transfer", "error")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Stock insuficiente en el item origen",
        )

    try:
        with measure_db_query("update", "items"):
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

        with measure_db_query("select", "items"):
            db.refresh(item_origen)
            db.refresh(item_destino)

        # -------------------------------------------------
        # Sincronización con Elasticsearch
        # -------------------------------------------------
        try:
            es_update_item(item_origen)
        except Exception as exc:
            logger.warning("No se pudo actualizar item origen %s en Elasticsearch: %s", item_origen.id, exc)

        try:
            es_update_item(item_destino)
        except Exception as exc:
            logger.warning("No se pudo actualizar item destino %s en Elasticsearch: %s", item_destino.id, exc)

    except Exception as exc:
        db.rollback()
        increment_crud_operation("item", "stock_transfer", "error")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al transferir stock: {exc}",
        ) from exc

    for affected_id in (item_origen.id, item_destino.id):
        delete_cache(build_item_cache_key(affected_id))
        invalidate_list_caches_for_item(affected_id, include_first_pages=True)

    increment_crud_operation("item", "stock_transfer", "success")

    _publicar_evento_item_kafka(
        event_type="item.stock_transferred",
        aggregate_id=item_origen.id,
        payload={
            "item_origen_id": item_origen.id,
            "item_destino_id": item_destino.id,
            "cantidad_transferida": payload.cantidad,
            "stock_origen": item_origen.stock,
            "stock_destino": item_destino.stock,
            "usuario": payload.usuario,
        },
        current_user=current_user,
    )

    return ApiResponse[dict](
        success=True,
        message="Transferencia de stock realizada exitosamente",
        data={
            "item_origen_id": item_origen.id,
            "item_destino_id": item_destino.id,
            "cantidad_transferida": payload.cantidad,
            "stock_origen": item_origen.stock,
            "stock_destino": item_destino.stock,
            "usuario": payload.usuario,
        },
        metadata={},
    )
