"""
Endpoints versión v2 para items.

Esta versión mantiene el mismo comportamiento que v1 para listado de items,
pero agrega un campo calculado en tiempo real: `precio_con_iva`.

Motivo del versionado:
- Las APIs empresariales evolucionan
- Cambios incompatibles se introducen en nuevas versiones
- Los clientes existentes pueden seguir usando v1 sin romperse

Diferencias clave con v1:
- Se agrega `precio_con_iva`
- Se calcula dinámicamente (price * 1.16)

Endpoints incluidos:
- GET /api/v2/items  -> listar items con IVA calculado

Seguridad:
- Requiere API Key (verify_api_key)

Notas:
- Los filtros, búsqueda, ordenamiento y paginación son idénticos a v1
- Solo se modifica el esquema de salida
"""

from __future__ import annotations

from datetime import date, datetime, time
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.deps import log_client_ip
from app.core.security import verify_api_key
from app.database.database import get_db
from app.models.item import Item
from app.schemas.base import ApiResponse
from app.schemas.item import ItemReadV2
from app.schemas.pagination import PaginatedResponse

# Router de la versión 2
router = APIRouter()


@router.get(
    "/",
    response_model=ApiResponse[PaginatedResponse[ItemReadV2]],
    summary="Listar items (v2) con precio con IVA",
    dependencies=[Depends(verify_api_key)],
)
def listar_items_v2(
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
    Lista items activos con filtros, ordenamiento y paginación (v2).

    Diferencia con v1:
    - Se agrega el campo `precio_con_iva`

    Fórmula aplicada:
        precio_con_iva = price * 1.16

    El resto del comportamiento permanece igual para mantener
    consistencia entre versiones.
    """

    # Query base: solo items no eliminados (soft delete)
    stmt = select(Item).where(Item.eliminado == False)  # noqa: E712

    # ----- FILTROS -----

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

    # ----- TOTAL DE RESULTADOS (antes de paginar) -----

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = db.execute(count_stmt).scalar_one()

    # ----- ORDENAMIENTO -----

    order_map = {
        "precio_asc": Item.price.asc(),
        "precio_desc": Item.price.desc(),
        "nombre_asc": Item.name.asc(),
        "nombre_desc": Item.name.desc(),
    }

    stmt = stmt.order_by(order_map[ordenar_por]) if ordenar_por else stmt.order_by(Item.id.asc())

    # ----- PAGINACIÓN -----

    offset = (page - 1) * page_size
    stmt = stmt.offset(offset).limit(page_size)

    items = db.execute(stmt).scalars().all()

    # ----- CONSTRUCCIÓN DE RESPUESTA V2 -----
    # Aquí agregamos el campo calculado

    items_v2 = [
        ItemReadV2(
            id=i.id,
            name=i.name,
            description=i.description,
            price=i.price,
            sku=i.sku,
            codigo_sku=i.codigo_sku,
            stock=i.stock,
            eliminado=i.eliminado,
            eliminado_en=i.eliminado_en,
            precio_con_iva=round(i.price * 1.16, 2),
        )
        for i in items
    ]

    # ----- ESTRUCTURA PAGINADA -----

    paginated = PaginatedResponse[ItemReadV2](
        page=page,
        page_size=page_size,
        total=total,
        items=items_v2,
    )

    # ----- RESPUESTA ESTÁNDAR DE LA API -----

    return ApiResponse[PaginatedResponse[ItemReadV2]](
        success=True,
        message="Items obtenidos exitosamente (v2)",
        data=paginated,
        metadata={},
    )