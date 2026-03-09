from fastapi import APIRouter

# Routers de endpoints
from app.api.v1.endpoints.auth import router as auth_router
from app.api.v1.endpoints.items import router as items_router
from app.api.v1.endpoints.configuracion_cors import router as configuracion_cors_router
from app.api.v1.endpoints.usuarios import router as usuarios_router
from app.api.v1.endpoints.admin_cache import router as admin_cache_router


# Router principal de la versión v1 de la API
api_router_v1 = APIRouter()


# ==============================
# Endpoints de Items
# ==============================
api_router_v1.include_router(
    items_router,
    prefix="/items",
    tags=["Items v1"],
)


# ==============================
# Autenticación
# ==============================
api_router_v1.include_router(
    auth_router,
    prefix="/auth",
    tags=["Auth v1"],
)


# ==============================
# Configuración dinámica de CORS
# ==============================
api_router_v1.include_router(
    configuracion_cors_router
)


# ==============================
# Usuarios
# ==============================
api_router_v1.include_router(
    usuarios_router,
    prefix="/usuarios",
    tags=["Usuarios"],
)


# ==============================
# Administración de caché (Redis)
# ==============================
api_router_v1.include_router(
    admin_cache_router,
    prefix="/admin/cache",
    tags=["Admin Cache"],
)