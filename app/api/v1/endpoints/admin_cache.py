from fastapi import APIRouter, Depends

from app.core.cache import get_cache_stats
from app.core.security import get_current_user, require_role
from app.models.usuario import Usuario
from app.schemas.base import ApiResponse

router = APIRouter(tags=["Admin Cache"])


@router.get(
    "/stats",
    response_model=ApiResponse[dict],
    summary="Obtener estadísticas de Redis",
)
def cache_stats(
    current_user: Usuario = Depends(get_current_user),
    _: None = Depends(require_role("admin")),
):
    return ApiResponse[dict](
        success=True,
        message="Estadísticas de caché obtenidas exitosamente",
        data=get_cache_stats(),
        metadata={},
    )
