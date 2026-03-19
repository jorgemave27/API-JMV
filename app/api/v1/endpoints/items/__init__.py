"""
Paquete de endpoints de items.

Este __init__ exporta el router principal para que el import existente
siga funcionando sin romper nada:

from app.api.v1.endpoints.items import router as items_router
"""

from .router import router

__all__ = ["router"]
