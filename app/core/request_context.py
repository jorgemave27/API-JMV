from __future__ import annotations

from contextvars import ContextVar, Token
from typing import Optional

# -------------------------------------------------------------------
# ContextVars para auditoría por request
# -------------------------------------------------------------------
# Estas variables permiten guardar información contextual del request
# actual sin pasarla manualmente por todos los métodos.
#
# Caso de uso:
# - guardar user_id autenticado
# - guardar IP del cliente
#
# Luego, los eventos de SQLAlchemy pueden leer estos valores y usarlos
# para escribir auditoría automáticamente.
# -------------------------------------------------------------------

_current_user_id: ContextVar[Optional[int]] = ContextVar(
    "current_user_id",
    default=None,
)

_current_client_ip: ContextVar[Optional[str]] = ContextVar(
    "current_client_ip",
    default=None,
)


# -------------------------------------------------------------------
# Helpers para user_id
# -------------------------------------------------------------------


def set_current_user_id(user_id: Optional[int]) -> Token:
    """
    Guarda el user_id actual en el contexto del request.

    Returns:
        Token: token necesario para hacer reset seguro después.
    """
    return _current_user_id.set(user_id)


def get_current_user_id() -> Optional[int]:
    """
    Obtiene el user_id actual del contexto.
    """
    return _current_user_id.get()


def reset_current_user_id(token: Token) -> None:
    """
    Restaura el valor anterior del user_id en el contexto.
    """
    _current_user_id.reset(token)


# -------------------------------------------------------------------
# Helpers para client_ip
# -------------------------------------------------------------------


def set_current_client_ip(client_ip: Optional[str]) -> Token:
    """
    Guarda la IP del cliente actual en el contexto del request.

    Returns:
        Token: token necesario para hacer reset seguro después.
    """
    return _current_client_ip.set(client_ip)


def get_current_client_ip() -> Optional[str]:
    """
    Obtiene la IP del cliente actual desde el contexto.
    """
    return _current_client_ip.get()


def reset_current_client_ip(token: Token) -> None:
    """
    Restaura el valor anterior de client_ip en el contexto.
    """
    _current_client_ip.reset(token)
