from __future__ import annotations

from pydantic import BaseModel, Field


class TransferirStockRequest(BaseModel):
    """
    Request para transferir stock entre dos items.
    """

    item_origen_id: int = Field(..., gt=0)
    item_destino_id: int = Field(..., gt=0)
    cantidad: int = Field(..., gt=0)
    usuario: str = Field(default="system", min_length=1, max_length=100)

    # Solo para pruebas de rollback 
    forzar_error: bool = False