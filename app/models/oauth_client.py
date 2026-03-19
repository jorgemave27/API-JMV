"""
Modelo OAuth Client.

Representa aplicaciones externas que pueden usar
tu API mediante OAuth2 Authorization Code Flow.
"""

from sqlalchemy import JSON, Column, Integer, String

from app.database.database import Base


class OAuthClient(Base):
    """
    Aplicación externa registrada para OAuth.
    """

    __tablename__ = "oauth_clients"

    id = Column(Integer, primary_key=True)

    # identificador público del cliente
    client_id = Column(String(255), unique=True, index=True, nullable=False)

    # secret del cliente (debería guardarse hasheado)
    client_secret = Column(String(255), nullable=False)

    # nombre de la aplicación
    name = Column(String(255), nullable=False)

    # URIs permitidos para redirección
    redirect_uris = Column(JSON, nullable=False)

    # scopes permitidos
    scopes = Column(JSON, nullable=False)
