from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException

from app.core.security import verify_api_key
from app.schemas.base import ApiResponse
from app.schemas.operation import OperationStatusResponse
from app.services.operation_service import OperationService

router = APIRouter(prefix="/operaciones", tags=["Operaciones CQRS"])


@router.get(
    "/{operation_id}",
    response_model=ApiResponse[OperationStatusResponse],
    dependencies=[Depends(verify_api_key)],
    summary="Consultar estado de una operación CQRS",
)
def obtener_operacion(operation_id: str):
    """
    Devuelve el estado de una operación asíncrona de CQRS.
    """
    service = OperationService()
    operation = service.get_operation(operation_id)

    if not operation:
        raise HTTPException(status_code=404, detail="Operación no encontrada")

    data = OperationStatusResponse(
        operation_id=operation["operation_id"],
        status=operation["status"],
        resource_type=operation["resource_type"],
        resource_id=operation.get("resource_id"),
        event_type=operation["event_type"],
        message=operation["message"],
        created_at=datetime.fromisoformat(operation["created_at"]),
        completed_at=datetime.fromisoformat(operation["completed_at"]) if operation.get("completed_at") else None,
    )

    return ApiResponse[OperationStatusResponse](
        success=True,
        message="Operación obtenida exitosamente",
        data=data,
        metadata={},
    )
