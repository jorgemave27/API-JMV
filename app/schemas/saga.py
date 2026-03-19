from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field


class PedidoSagaCreate(BaseModel):
    """
    Payload para iniciar la saga de pedido.
    """

    usuario_id: int = Field(..., ge=1)
    item_id: int = Field(..., ge=1)
    cantidad: int = Field(..., ge=1)
    monto_total: float = Field(..., gt=0)
    email_cliente: EmailStr

    # Flags para simular fallas y validar compensaciones
    force_stock_fail: bool = False
    force_payment_fail: bool = False
    force_notification_fail: bool = False


class PedidoSagaResponse(BaseModel):
    """
    Respuesta resumida al iniciar la saga.
    """

    saga_id: str
    status: str