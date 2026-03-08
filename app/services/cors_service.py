from __future__ import annotations

import time
from threading import Lock

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.database.database import SessionLocal
from app.models.configuracion_cors import ConfiguracionCors


class CorsOriginsCache:
    def __init__(self, ttl_seconds: int = 60):
        self.ttl_seconds = ttl_seconds
        self._origins: list[str] = []
        self._last_load: float = 0.0
        self._lock = Lock()

    def get_origins(self) -> list[str]:
        now = time.time()

        if now - self._last_load < self.ttl_seconds:
            return self._origins

        with self._lock:
            now = time.time()
            if now - self._last_load < self.ttl_seconds:
                return self._origins

            db: Session = SessionLocal()
            try:
                stmt = (
                    select(ConfiguracionCors.origin)
                    .where(ConfiguracionCors.activo == True)  # noqa: E712
                    .order_by(ConfiguracionCors.id.asc())
                )
                rows = db.execute(stmt).scalars().all()

                # Fallback: si no hay origins en BD, usar configuración por entorno
                self._origins = list(rows) if rows else settings.cors_allow_origins_list
                self._last_load = now
            finally:
                db.close()

        return self._origins

    def force_refresh(self) -> list[str]:
        with self._lock:
            db: Session = SessionLocal()
            try:
                stmt = (
                    select(ConfiguracionCors.origin)
                    .where(ConfiguracionCors.activo == True)  # noqa: E712
                    .order_by(ConfiguracionCors.id.asc())
                )
                rows = db.execute(stmt).scalars().all()

                # Fallback: si no hay origins en BD, usar configuración por entorno
                self._origins = list(rows) if rows else settings.cors_allow_origins_list
                self._last_load = time.time()
            finally:
                db.close()

        return self._origins


cors_cache = CorsOriginsCache(ttl_seconds=60)