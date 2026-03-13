"""
Router agregador de items.

FASE SEGURA:
- Se mantiene el router legacy como API pública principal
- Se agrega router CQRS bajo prefijo /cqrs para no romper tests existentes
- Así podemos avanzar en la tarea 56 sin destruir compatibilidad
"""

from fastapi import APIRouter

from app.api.v1.endpoints.items_legacy import router as legacy_router
from app.api.v1.endpoints.items_cqrs import router as cqrs_router

router = APIRouter()

# API pública existente (tests actuales dependen de esto)
router.include_router(legacy_router)

# Nueva API CQRS sin romper compatibilidad
router.include_router(cqrs_router, prefix="/cqrs")