from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from app.core.security import require_role, verify_api_key
from app.schemas.base import ApiResponse
from app.schemas.saga import PedidoSagaCreate, PedidoSagaResponse
from app.services.saga_pedido_service import iniciar_saga_pedido

router = APIRouter(prefix="/sagas", tags=["Sagas"])


@router.post(
    "/pedidos",
    response_model=ApiResponse[PedidoSagaResponse],
    summary="Iniciar saga de pedido distribuido",
    dependencies=[Depends(verify_api_key), Depends(require_role("admin", "editor"))],
)
async def crear_pedido_con_saga(
    request: Request,
    payload: PedidoSagaCreate,
):
    """
    Inicia la saga de pedido.

    Flujo esperado:
    1. CREATE_PEDIDO
    2. RESERVAR_STOCK
    3. COBRAR_PAGO
    4. NOTIFICAR_CLIENTE
    5. CONFIRMAR_PEDIDO

    Compensaciones:
    - si falla cobro: COMPENSAR_STOCK -> CANCELAR_PEDIDO
    - si falla reserva de stock: CANCELAR_PEDIDO
    """
    saga_id = await iniciar_saga_pedido(payload.model_dump())

    return ApiResponse[PedidoSagaResponse](
        success=True,
        message="Saga iniciada correctamente",
        data=PedidoSagaResponse(
            saga_id=saga_id,
            status="PENDING",
        ),
        metadata={},
    )