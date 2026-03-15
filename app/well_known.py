"""
Endpoints estándar de seguridad y discovery.

Incluye:

- security.txt (RFC 9116)
- OpenID discovery endpoint
"""

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

router = APIRouter()


# =====================================================
# security.txt
# RFC 9116
# =====================================================

@router.get("/.well-known/security.txt", include_in_schema=False)
async def security_txt():

    content = """
Contact: mailto:security@empresa.com
Expires: 2030-12-31T23:59:59.000Z
Preferred-Languages: es, en
Policy: https://empresa.com/security-policy
"""

    return PlainTextResponse(content.strip())


# =====================================================
# OPENID DISCOVERY
# =====================================================

@router.get("/.well-known/openid-configuration", include_in_schema=False)
async def openid_configuration():

    return {
        "issuer": "http://localhost:8000",
        "authorization_endpoint": "http://localhost:8000/oauth/authorize",
        "token_endpoint": "http://localhost:8000/oauth/token",
        "userinfo_endpoint": "http://localhost:8000/oauth/userinfo",
        "jwks_uri": "http://localhost:8000/.well-known/jwks.json",
        "response_types_supported": ["code"],
        "subject_types_supported": ["public"],
        "id_token_signing_alg_values_supported": ["HS256"]
    }