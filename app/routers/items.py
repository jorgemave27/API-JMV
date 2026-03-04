from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.core.security import verify_api_key
from app.core.deps import get_client_ip
from app.database.database import get_db
from app.models.item import Item
from app.schemas.item import ItemCreate, ItemRead

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
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


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
):
    offset = (page - 1) * page_size
    stmt = select(Item).offset(offset).limit(page_size)
    items = db.execute(stmt).scalars().all()
    return items


@router.get(
    "/buscar",
    response_model=list[ItemRead],
    summary="Buscar items por nombre (LIKE)",
    dependencies=[Depends(verify_api_key)],
)
def buscar_items(
    q: str = Query(..., min_length=1, description="Texto a buscar"),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
):
    offset = (page - 1) * page_size
    stmt = (
        select(Item)
        .where(Item.name.ilike(f"%{q}%"))
        .offset(offset)
        .limit(page_size)
    )
    items = db.execute(stmt).scalars().all()
    return items


@router.get(
    "/ip",
    summary="Demo: obtener IP del cliente (dependency)",
    dependencies=[Depends(verify_api_key)],
)
def mi_ip(ip: str = Depends(get_client_ip)):
    return {"ip": ip}


