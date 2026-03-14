"""
Refresh Tokens OAuth2.

Permiten obtener nuevos access tokens
sin pedir login nuevamente.
"""

from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime, Boolean
from app.database.database import Base


class OAuthRefreshToken(Base):

    __tablename__ = "oauth_refresh_tokens"

    id = Column(Integer, primary_key=True)

    # token generado
    token = Column(String(255), unique=True, index=True)

    # email del usuario (porque tu JWT usa email como subject)
    user_email = Column(String(255), index=True)

    # cliente OAuth que lo solicitó
    client_id = Column(String(255))

    # revocado o no
    revoked = Column(Boolean, default=False)

    # expiración
    expires_at = Column(DateTime)

    created_at = Column(DateTime, default=datetime.utcnow)