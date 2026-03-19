from fastapi import APIRouter

from app.api.v2.endpoints.items import router as items_router

api_router_v2 = APIRouter()
api_router_v2.include_router(items_router, prefix="/items", tags=["Items v2"])
