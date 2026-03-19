# ==========================================================
# WELL-KNOWN ENDPOINTS
# Endpoints estándar que NO deben estar bajo /api/v1
# ==========================================================

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

# Router sin prefijo
router = APIRouter()


# ==========================================================
# SECURITY.TXT
# ==========================================================


@router.get(
    "/.well-known/security.txt",
    response_class=PlainTextResponse,
    include_in_schema=False,
)
def security_txt():
    """
    Endpoint estándar para reportar vulnerabilidades.
    """

    return """Contact: mailto:security@empresa.com
Expires: 2027-01-01T00:00:00.000Z
Preferred-Languages: es, en
Canonical: https://api.empresa.com/.well-known/security.txt
Policy: https://empresa.com/security-policy
"""


# ==========================================================
# OPENID DISCOVERY
# ==========================================================


@router.get(
    "/.well-known/openid-configuration",
    include_in_schema=False,
)
def openid_configuration():
    """
    Endpoint estándar de OpenID discovery.
    """

    return {
        "issuer": "http://localhost:8000",
        "authorization_endpoint": "http://localhost:8000/oauth/authorize",
        "token_endpoint": "http://localhost:8000/oauth/token",
        "userinfo_endpoint": "http://localhost:8000/oauth/userinfo",
        "response_types_supported": ["code"],
        "subject_types_supported": ["public"],
        "id_token_signing_alg_values_supported": ["RS256"],
    }
