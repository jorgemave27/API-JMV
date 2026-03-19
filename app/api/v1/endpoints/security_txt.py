from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

# Router independiente
router = APIRouter()


@router.get("/.well-known/security.txt", response_class=PlainTextResponse, include_in_schema=False)
def security_txt():
    """
    security.txt es un estándar que permite a investigadores
    de seguridad saber cómo reportar vulnerabilidades.

    Es requerido por muchas auditorías de seguridad.
    """

    return """Contact: mailto:security@empresa.com
Expires: 2027-01-01T00:00:00.000Z
Preferred-Languages: es, en
Canonical: https://api.empresa.com/.well-known/security.txt
Policy: https://empresa.com/security-policy
"""
