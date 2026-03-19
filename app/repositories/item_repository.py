from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.item import Item


class ItemRepository:
    """
    Repository para operaciones de base de datos del modelo Item.

    Este patrón separa la lógica de acceso a datos de los endpoints
    de la API, facilitando:
    - mantenimiento
    - testing
    - reutilización de lógica
    """

    def __init__(self, db: Session):
        self.db = db

    # -------------------------
    # Obtener item por ID
    # -------------------------

    def get_by_id(self, item_id: int) -> Item | None:
        return self.db.get(Item, item_id)

    # -------------------------
    # Obtener todos los items
    # -------------------------

    def get_all(self):
        stmt = select(Item)
        return self.db.execute(stmt).scalars().all()

    # -------------------------
    # Crear item
    # -------------------------

    def create(self, item: Item) -> Item:
        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)
        return item

    # -------------------------
    # Actualizar item
    # -------------------------

    def update(self, item: Item) -> Item:
        self.db.commit()
        self.db.refresh(item)
        return item

    # -------------------------
    # Soft delete
    # -------------------------

    def delete(self, item: Item) -> Item:
        item.eliminado = True
        item.eliminado_en = datetime.now()
        self.db.commit()
        self.db.refresh(item)
        return item
