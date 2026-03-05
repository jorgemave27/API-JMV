from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException , Query 
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.core.deps import get_client_ip, log_client_ip
from app.core.security import verify_api_key
from app.database.database import get_db
from app.models.item import Item
from app.schemas.item import ItemCreate, ItemRead
from app.dependencies import verificar_api_key


router = APIRouter(prefix="/items", tags=["items"])


@router.post(
    "/",
    response_model=ItemRead,
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
    return ItemRead.model_validate(item)


@router.get(
    "/",
    response_model=list[ItemRead],
    summary="Listar items con paginación",
    dependencies=[Depends(verify_api_key)],
)
def listar_items(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
    _ip: str = Depends(log_client_ip),
):
    offset = (page - 1) * page_size
    stmt = select(Item).offset(offset).limit(page_size)
    items = db.execute(stmt).scalars().all()
    return [ItemRead.model_validate(i) for i in items]


@router.get(
    "/buscar",
    response_model=list[ItemRead],
    summary="Buscar items por nombre (LIKE)",
    dependencies=[Depends(verify_api_key)],
)
def buscar_items(
    nombre: str = Query(..., min_length=1, description="Texto a buscar (parcial)"),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
):
    offset = (page - 1) * page_size

    stmt = (
        select(Item)
        .where(Item.name.ilike(f"%{nombre}%"))
        .offset(offset)
        .limit(page_size)
    )
    items = db.execute(stmt).scalars().all()
    return items

@router.get(
    "/buscar/summary",
    summary="Resumen de búsqueda: total y primer match",
    dependencies=[Depends(verify_api_key)],
)
def buscar_summary(
    nombre: str = Query(..., min_length=1),
    db: Session = Depends(get_db),
):
    # total (count)
    total = db.query(Item).filter(Item.name.ilike(f"%{nombre}%")).count()

    # first match
    first_match = (
        db.query(Item)
        .filter(Item.name.ilike(f"%{nombre}%"))
        .first()
    )

    return {
        "total": total,
        "first_match": ItemRead.model_validate(first_match).model_dump() if first_match else None,
    }

@router.get(
    "/ip",
    summary="Demo: obtener IP del cliente (dependency)",
    dependencies=[Depends(verify_api_key)],
)
def mi_ip(ip: str = Depends(get_client_ip)):
    return {"ip": ip}


@router.delete(
    "/{item_id}",
    summary="Eliminar item por ID",
    dependencies=[Depends(verificar_api_key)],
)
def eliminar_item(
    item_id: int,
    db: Session = Depends(get_db),
):
    item = db.get(Item, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item no encontrado")

    db.delete(item)
    db.commit()
    return {"deleted": True, "id": item_id}

