from fastapi import APIRouter

# GDPR
from app.api.v1.endpoints import gdpr

# =====================================================
# IMPORTACIÓN DE ROUTERS DE ENDPOINTS
# =====================================================
# Administración de caché Redis
from app.api.v1.endpoints.admin_cache import router as admin_cache_router

# Circuit breakers / resiliencia de servicios externos
from app.api.v1.endpoints.admin_circuit_breakers import router as admin_circuit_breakers_router

# Profiling / rendimiento
from app.api.v1.endpoints.admin_profile import router as admin_profile_router

# Eventos de seguridad registrados por el sistema
from app.api.v1.endpoints.admin_security import router as admin_security_router

# Autenticación JWT / OAuth
from app.api.v1.endpoints.auth import router as auth_router

# Configuración dinámica de CORS
from app.api.v1.endpoints.configuracion_cors import router as configuracion_cors_router

# Healthcheck del sistema
from app.api.v1.endpoints.health import router as health_router

# CRUD de items
from app.api.v1.endpoints.items import router as items_router

# OpenID discovery (descubrimiento automático de endpoints OAuth)
from app.api.v1.endpoints.openid_discovery import router as openid_router

# Endpoints de reportes
from app.api.v1.endpoints.reportes import router as reportes_router

# =====================================================
# ENDPOINTS DE HARDENING
# =====================================================
# security.txt (estándar para reporte de vulnerabilidades)
from app.api.v1.endpoints.security_txt import router as security_txt_router

# Gestión de usuarios
from app.api.v1.endpoints.usuarios import router as usuarios_router

from app.api.v1.endpoints.items_imagen import router as items_imagen_router

from app.api.v1.endpoints.notificaciones import router as notif_router

# =====================================================
# ROUTER PRINCIPAL DE LA API V1
# =====================================================

api_router_v1 = APIRouter()


# =====================================================
# ITEMS
# =====================================================

api_router_v1.include_router(
    items_router,
    prefix="/items",
    tags=["Items"],
)


# =====================================================
# AUTENTICACIÓN
# =====================================================

api_router_v1.include_router(
    auth_router,
    prefix="/auth",
    tags=["Auth"],
)


# =====================================================
# CONFIGURACIÓN DINÁMICA DE CORS
# =====================================================

api_router_v1.include_router(
    configuracion_cors_router,
    tags=["CORS Admin"],
)


# =====================================================
# HEALTHCHECK
# =====================================================

api_router_v1.include_router(
    health_router,
    tags=["Health"],
)


# =====================================================
# USUARIOS
# =====================================================

api_router_v1.include_router(
    usuarios_router,
    prefix="/usuarios",
    tags=["Usuarios"],
)


# =====================================================
# ADMINISTRACIÓN DE CACHÉ
# =====================================================

api_router_v1.include_router(
    admin_cache_router,
    prefix="/admin/cache",
    tags=["Admin Cache"],
)


# =====================================================
# CIRCUIT BREAKERS / RESILIENCE
# =====================================================

api_router_v1.include_router(
    admin_circuit_breakers_router,
    prefix="/admin",
    tags=["Admin Resilience"],
)


# =====================================================
# EVENTOS DE SEGURIDAD
# =====================================================

api_router_v1.include_router(
    admin_security_router,
    tags=["Admin Security"],
)


# =====================================================
# PROFILING
# =====================================================

api_router_v1.include_router(
    admin_profile_router,
    prefix="/admin",
    tags=["Admin Profiling"],
)


# =====================================================
# REPORTES
# =====================================================

api_router_v1.include_router(
    reportes_router,
    prefix="/reportes",
    tags=["Reportes"],
)


# =====================================================
# HARDENING ENDPOINTS
# =====================================================

# security.txt
api_router_v1.include_router(security_txt_router)

# openid discovery
api_router_v1.include_router(openid_router)

# GDPR
api_router_v1.include_router(
    gdpr.router,
    tags=["GDPR"],
)


api_router_v1.include_router(
    items_imagen_router,
    tags=["Items Imagen"],
)

api_router_v1.include_router(notif_router)