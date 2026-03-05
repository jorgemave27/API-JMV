from fastapi import APIRouter

from app.api.v1.endpoints.items import router as items_router

api_router_v1 = APIRouter()
api_router_v1.include_router(items_router, prefix="/items", tags=["Items v1"])