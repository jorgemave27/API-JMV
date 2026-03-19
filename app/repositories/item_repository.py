from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.item import Item

# CACHE
from app.cache.decorators import cacheable, cache_invalidate
from app.cache.multi_level_cache import add_tag, invalidate_tag


class ItemRepository:
    """
    Repository para operaciones de base de datos del modelo Item.

    Incluye:
    - Cache multinivel (L1 + Redis)
    - Invalidación automática
    - Tag-based invalidation

    IMPORTANTE:
    - Como get_by_id() puede devolver una instancia proveniente del cache L1,
      esa instancia puede venir detached de la Session actual.
    - Por eso en update()/delete() usamos merge() antes de commit/refresh.
    """

    def __init__(self, db: Session):
        self.db = db

    # -------------------------
    # Obtener item por ID (CACHEABLE)
    # -------------------------
    @cacheable(
        ttl=300,
        key_fn=lambda self, item_id: f"item:{item_id}",
    )
    async def get_by_id(self, item_id: int) -> Item | None:
        """
        Read-through cache:
        L1 -> L2 -> DB
        """
        return self.db.get(Item, item_id)

    # -------------------------
    # Obtener todos los items (CACHEABLE)
    # -------------------------
    @cacheable(
        ttl=120,
        key_fn=lambda self: "items:all",
    )
    async def get_all(self):
        """
        Cache para listado simple.
        """
        stmt = select(Item)
        return self.db.execute(stmt).scalars().all()

    # -------------------------
    # Crear item (INVALIDA + TAG)
    # -------------------------
    async def create(self, item: Item) -> Item:
        """
        Crea item y registra tag si aplica.
        También invalida listado general.
        """
        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)

        # TAG por categoría
        if getattr(item, "categoria_id", None):
            await add_tag(f"categoria:{item.categoria_id}", f"item:{item.id}")

        # Invalidar listado general cacheado
        await invalidate_tag("items:all")

        return item

    # -------------------------
    # Actualizar item (INVALIDA + TAG)
    # -------------------------
    @cache_invalidate(
        key_fn=lambda self, item: f"item:{item.id}",
    )
    async def update(self, item: Item) -> Item:
        """
        Actualiza item.

        CLAVE:
        Si item vino del L1 cache, puede venir detached de la Session actual.
        Por eso hacemos merge() antes de commit().
        """
        item = self.db.merge(item)
        self.db.commit()
        self.db.refresh(item)

        # Invalidar tag de categoría si aplica
        if getattr(item, "categoria_id", None):
            await invalidate_tag(f"categoria:{item.categoria_id}")

        # Invalidar listado general
        await invalidate_tag("items:all")

        return item

    # -------------------------
    # Soft delete (INVALIDA)
    # -------------------------
    @cache_invalidate(
        key_fn=lambda self, item: f"item:{item.id}",
    )
    async def delete(self, item: Item) -> Item:
        """
        Soft delete seguro para objetos detached provenientes del cache.
        """
        item = self.db.merge(item)
        item.eliminado = True
        item.eliminado_en = datetime.now()

        self.db.commit()
        self.db.refresh(item)

        # Invalidar categoría si aplica
        if getattr(item, "categoria_id", None):
            await invalidate_tag(f"categoria:{item.categoria_id}")

        # Invalidar listado general
        await invalidate_tag("items:all")

        return item