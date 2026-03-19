from fastapi import APIRouter

router = APIRouter()


@router.get("/.well-known/openid-configuration", include_in_schema=False)
def openid_discovery():
    """
    Endpoint estándar de OpenID Connect.

    Permite que clientes descubran automáticamente
    cómo autenticar contra la API.
    """

    return {
        "issuer": "https://api.empresa.com",
        "authorization_endpoint": "https://api.empresa.com/oauth/authorize",
        "token_endpoint": "https://api.empresa.com/oauth/token",
        "userinfo_endpoint": "https://api.empresa.com/oauth/userinfo",
        "response_types_supported": ["code"],
        "subject_types_supported": ["public"],
        "id_token_signing_alg_values_supported": ["RS256"],
    }
