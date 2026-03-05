from __future__ import annotations

from datetime import date, datetime, time
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.deps import get_client_ip, log_client_ip
from app.core.responses import error_response
from app.core.security import verify_api_key
from app.database.database import get_db
from app.models.item import Item
from app.schemas.base import ApiResponse
from app.schemas.bulk import BulkCreate, BulkDelete, BulkUpdateDisponible
from app.schemas.item import ItemCreate, ItemRead
from app.schemas.pagination import PaginatedResponse

router = APIRouter(prefix="/items", tags=["items"])


@router.post(
    "/",
    response_model=ApiResponse[ItemRead],
    summary="Crear item",
    dependencies=[Depends(verify_api_key)],
)
def crear_item(
    payload: ItemCreate,
    db: Session = Depends(get_db),
):
    item = Item(
        name=payload.name,
        description=payload.description,
        price=payload.price,
        sku=payload.sku,
        codigo_sku=payload.codigo_sku,
        stock=payload.stock,
    )
    db.add(item)
    db.commit()
    db.refresh(item)

    return ApiResponse[ItemRead](
        success=True,
        message="Item creado exitosamente",
        data=ItemRead.model_validate(item),
        metadata={},
    )


# ------------------------
# TAREA 12: BULK OPERATIONS
# ------------------------

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

        return ApiResponse[list[ItemRead]](
            success=True,
            message="Items creados exitosamente (bulk)",
            data=[ItemRead.model_validate(o) for o in objects],
            metadata={},
        )

    except IntegrityError:
        db.rollback()
        return error_response(
            status_code=400,
            message="Error en bulk create: violación de integridad (ej. SKU duplicado). Se hizo rollback.",
        )
    except SQLAlchemyError as e:
        db.rollback()
        return error_response(
            status_code=500,
            message="Error de base de datos en bulk create. Se hizo rollback.",
            data={"error": str(e)},
        )
    except Exception as e:
        db.rollback()
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

        return ApiResponse[dict](
            success=True,
            message="Bulk delete procesado",
            data={"deleted": deleted, "not_found": not_found},
            metadata={},
        )

    except SQLAlchemyError as e:
        db.rollback()
        return error_response(
            status_code=500,
            message="Error de base de datos en bulk delete. Se hizo rollback.",
            data={"error": str(e)},
        )
    except Exception as e:
        db.rollback()
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
    Como el modelo no tiene columna 'disponible', lo interpretamos así:
      - disponible=True  => stock=1 (si estaba 0)
      - disponible=False => stock=0

    Retorna conteo updated vs not_found (no falla si algún id no existe).
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

            new_stock = 1 if payload.disponible else 0
            if item.stock != new_stock:
                item.stock = new_stock
                updated += 1

        db.commit()

        return ApiResponse[dict](
            success=True,
            message="Bulk update disponible procesado",
            data={"updated": updated, "not_found": not_found},
            metadata={},
        )

    except SQLAlchemyError as e:
        db.rollback()
        return error_response(
            status_code=500,
            message="Error de base de datos en bulk update disponible. Se hizo rollback.",
            data={"error": str(e)},
        )
    except Exception as e:
        db.rollback()
        return error_response(
            status_code=500,
            message="Error inesperado en bulk update disponible. Se hizo rollback.",
            data={"error": str(e)},
        )


# ------------------------
# LISTADOS (TAREA 10)
# ------------------------

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
    db: Session = Depends(get_db),
):
    item = db.execute(select(Item).where(Item.id == item_id)).scalars().first()
    if not item:
        return error_response(status_code=404, message="Item no encontrado")

    if item.eliminado:
        return ApiResponse[dict](
            success=True,
            message="Item ya estaba eliminado",
            data={"ok": True},
            metadata={},
        )

    item.eliminado = True
    item.eliminado_en = datetime.now()
    db.add(item)
    db.commit()

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
    db: Session = Depends(get_db),
):
    item = db.execute(select(Item).where(Item.id == item_id)).scalars().first()
    if not item:
        return error_response(status_code=404, message="Item no encontrado")

    if not item.eliminado:
        return error_response(status_code=400, message="El item no está eliminado")

    item.eliminado = False
    item.eliminado_en = None
    db.add(item)
    db.commit()
    db.refresh(item)

    return ApiResponse[ItemRead](
        success=True,
        message="Item restaurado exitosamente",
        data=ItemRead.model_validate(item),
        metadata={},
    )
