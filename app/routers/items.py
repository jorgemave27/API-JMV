from __future__ import annotations

from datetime import date, datetime, time
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.deps import get_client_ip, log_client_ip
from app.core.responses import error_response
from app.core.security import verify_api_key
from app.database.database import get_db
from app.models.item import Item
from app.schemas.base import ApiResponse
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
        metadata={},  # el middleware meterá request_id aquí
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
        metadata={},  # middleware inyecta request_id
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