from __future__ import annotations

import time

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.config import settings
from app.core.security import get_current_user, require_role
from app.models.usuario import Usuario
from app.resilience.circuit_breaker import get_all_breakers_status
from app.schemas.base import ApiResponse
from app.services.external_services import get_external_data_with_resilience

router = APIRouter(tags=["Admin Resilience"])


@router.get(
    "/circuit-breakers",
    response_model=ApiResponse[dict],
    summary="Obtener estado actual de los circuit breakers",
)
def get_circuit_breakers(
    current_user: Usuario = Depends(get_current_user),
    _: None = Depends(require_role("admin")),
):
    return ApiResponse[dict](
        success=True,
        message="Estados de circuit breakers obtenidos exitosamente",
        data=get_all_breakers_status(),
        metadata={},
    )


@router.get(
    "/resilience/mock-external",
    response_model=ApiResponse[dict],
    summary="Mock de servicio externo para simular fallas o lentitud",
)
def mock_external_service(
    fail: bool = Query(False),
    slow_seconds: int = Query(0, ge=0, le=60),
):
    if slow_seconds > 0:
        time.sleep(slow_seconds)

    if fail:
        raise HTTPException(status_code=503, detail="Falla simulada del servicio externo")

    return ApiResponse[dict](
        success=True,
        message="Respuesta mock externa exitosa",
        data={
            "rate": 17.25,
            "currency": "MXN",
            "provider": "mock-external-service",
            "slow_seconds": slow_seconds,
            "fail": fail,
        },
        metadata={},
    )


@router.get(
    "/resilience/test-tipo-cambio",
    response_model=ApiResponse[dict],
    summary="Probar consumo resiliente con circuit breaker y fallback cacheado",
)
def test_tipo_cambio_resilience(
    fail: bool = Query(False),
    slow_seconds: int = Query(0, ge=0, le=60),
    current_user: Usuario = Depends(get_current_user),
    _: None = Depends(require_role("admin")),
):
    url = (
        f"{settings.RESILIENCE_MOCK_BASE_URL}"
        f"?fail={'true' if fail else 'false'}&slow_seconds={slow_seconds}"
    )

    payload = get_external_data_with_resilience(
        service_name="tipo_cambio",
        breaker_name="tipo_cambio",
        url=url,
        cache_key="latest",
        ttl_seconds=settings.EXTERNAL_CACHE_TTL_SECONDS,
    )

    return ApiResponse[dict](
        success=True,
        message="Prueba de resiliencia ejecutada exitosamente",
        data=payload,
        metadata={},
    )