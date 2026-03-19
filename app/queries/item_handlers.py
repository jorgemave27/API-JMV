from __future__ import annotations

import json
import logging
from dataclasses import dataclass

import redis
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.item_lectura import ItemLectura
from app.queries.base import QueryHandler
from app.queries.items import BuscarItemsQuery, ListarItemsQuery, ObtenerItemQuery
from app.schemas.item import ItemRead

logger = logging.getLogger(__name__)


@dataclass
class QueryItemResult:
    item: dict | None
    cache_hit: bool


@dataclass
class QueryListResult:
    items: list[dict]
    total: int
    page: int
    page_size: int
    cache_hit: bool


class BaseQueryHandler:
    def __init__(self, db: Session):
        self.db = db
        self.redis_client = None
        try:
            self.redis_client = redis.Redis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                socket_connect_timeout=1,
                socket_timeout=1,
            )
            self.redis_client.ping()
        except Exception as exc:
            logger.warning("Redis no disponible para QueryHandler: %s", exc)
            self.redis_client = None

    def _get_cache(self, key: str):
        if not self.redis_client:
            return None
        try:
            return self.redis_client.get(key)
        except Exception:
            return None

    def _set_cache(self, key: str, value: dict, ttl: int):
        if not self.redis_client:
            return
        try:
            self.redis_client.setex(key, ttl, json.dumps(value))
        except Exception:
            return

    def _serialize_item(self, item: ItemLectura) -> dict:
        return ItemRead(
            id=item.id,
            name=item.name,
            description=item.description,
            price=item.price,
            sku=item.sku,
            codigo_sku=item.codigo_sku,
            stock=item.stock,
            categoria_id=item.categoria_id,
            categoria=None,
            eliminado=item.eliminado,
            eliminado_en=item.eliminado_en,
        ).model_dump(mode="json")


class ObtenerItemHandler(BaseQueryHandler, QueryHandler[ObtenerItemQuery, QueryItemResult]):
    def handle(self, query: ObtenerItemQuery) -> QueryItemResult:
        cache_key = f"cqrs:item:{query.item_id}"

        cached = self._get_cache(cache_key)
        if cached:
            return QueryItemResult(item=json.loads(cached), cache_hit=True)

        item = self.db.get(ItemLectura, query.item_id)
        if not item:
            return QueryItemResult(item=None, cache_hit=False)

        payload = self._serialize_item(item)
        self._set_cache(cache_key, payload, settings.CACHE_TTL_ITEM_SECONDS)
        return QueryItemResult(item=payload, cache_hit=False)


class ListarItemsHandler(BaseQueryHandler, QueryHandler[ListarItemsQuery, QueryListResult]):
    def handle(self, query: ListarItemsQuery) -> QueryListResult:
        cache_key = f"cqrs:items:list:{query.page}:{query.page_size}"

        cached = self._get_cache(cache_key)
        if cached:
            return QueryListResult(**json.loads(cached), cache_hit=True)

        base_stmt = select(ItemLectura).where(ItemLectura.eliminado.is_(False))
        count_stmt = select(func.count()).select_from(
            select(ItemLectura.id).where(ItemLectura.eliminado.is_(False)).subquery()
        )

        total = self.db.execute(count_stmt).scalar_one()
        offset = (query.page - 1) * query.page_size

        rows = (
            self.db.execute(base_stmt.order_by(ItemLectura.id.asc()).offset(offset).limit(query.page_size))
            .scalars()
            .all()
        )

        payload = {
            "items": [self._serialize_item(row) for row in rows],
            "total": total,
            "page": query.page,
            "page_size": query.page_size,
        }

        self._set_cache(cache_key, payload, settings.CACHE_TTL_LIST_SECONDS)
        return QueryListResult(**payload, cache_hit=False)


class BuscarItemsHandler(BaseQueryHandler, QueryHandler[BuscarItemsQuery, QueryListResult]):
    def handle(self, query: BuscarItemsQuery) -> QueryListResult:
        safe_term = query.term.strip().lower()
        cache_key = f"cqrs:items:search:{safe_term}:{query.page}:{query.page_size}"

        cached = self._get_cache(cache_key)
        if cached:
            return QueryListResult(**json.loads(cached), cache_hit=True)

        base_filter = [
            ItemLectura.eliminado.is_(False),
            ItemLectura.name.ilike(f"%{safe_term}%"),
        ]

        count_stmt = select(func.count()).select_from(select(ItemLectura.id).where(*base_filter).subquery())
        total = self.db.execute(count_stmt).scalar_one()

        offset = (query.page - 1) * query.page_size
        rows = (
            self.db.execute(
                select(ItemLectura)
                .where(*base_filter)
                .order_by(ItemLectura.id.asc())
                .offset(offset)
                .limit(query.page_size)
            )
            .scalars()
            .all()
        )

        payload = {
            "items": [self._serialize_item(row) for row in rows],
            "total": total,
            "page": query.page,
            "page_size": query.page_size,
        }

        self._set_cache(cache_key, payload, settings.CACHE_TTL_LIST_SECONDS)
        return QueryListResult(**payload, cache_hit=False)
