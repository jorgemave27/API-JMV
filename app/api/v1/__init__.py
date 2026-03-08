from fastapi import APIRouter

from app.api.v1.endpoints.auth import router as auth_router
from app.api.v1.endpoints.items import router as items_router
from app.api.v1.endpoints.configuracion_cors import router as configuracion_cors_router


api_router_v1 = APIRouter()
api_router_v1.include_router(items_router, prefix="/items", tags=["Items v1"])
api_router_v1.include_router(auth_router, prefix="/auth", tags=["Auth v1"])
api_router_v1.include_router(configuracion_cors_router)