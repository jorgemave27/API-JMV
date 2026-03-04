from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health", summary="Healthcheck")
def health():
    return {"status": "ok", "service": "API JMV"}


