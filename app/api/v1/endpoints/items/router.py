"""
Router agregador de items.

FASE SEGURA:
- Por ahora reutilizamos el router legacy completo.
- Así NO cambian rutas, NO cambian tests y NO cambia la API pública.
- Después podremos mover endpoints por módulos sin romper imports.
"""

from fastapi import APIRouter

# Importamos el router original renombrado
from app.api.v1.endpoints.items_legacy import router as legacy_router

router = APIRouter()

# Incluye todas las rutas legacy exactamente como estaban
router.include_router(legacy_router)