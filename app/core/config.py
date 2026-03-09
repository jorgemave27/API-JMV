from __future__ import annotations

import os

from fastapi import Request
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from slowapi import Limiter
from slowapi.util import get_remote_address


APP_ENV = os.getenv("APP_ENV", "development")


def rate_limit_key_func(request: Request) -> str:
    """
    Genera la clave para rate limiting.

    Reglas:
    - Si existe un JWT válido, usa el user_id (claim 'sub')
    - Si no existe o no es válido, usa la IP del cliente
    """
    auth_header = request.headers.get("Authorization")

    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.replace("Bearer ", "").strip()

        try:
            from app.core.security import decode_token

            payload = decode_token(token)
            user_id = payload.get("sub")

            if user_id:
                return f"user:{user_id}"
        except Exception:
            pass

    return f"ip:{get_remote_address(request)}"


def dynamic_rate_limit(key: str) -> str:
    """
    Define el límite dinámico según la clave calculada por key_func.

    Reglas:
    - user:<id> => 1000/minute
    - ip:<ip>   => 50/minute
    """
    if key.startswith("user:"):
        return "1000/minute"

    return "50/minute"


limiter = Limiter(key_func=rate_limit_key_func)


class Settings(BaseSettings):
    DATABASE_URL: str
    API_KEY: str

    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    CORS_ALLOW_ORIGINS: str = "http://localhost:3000,https://mi-app.com"
    LOG_LEVEL: str = "INFO"

    APP_NAME: str = "API JMV"
    APP_ENV: str = APP_ENV

    MAX_ITEMS_PER_PAGE: int = 100

    # Redis / Cache
    REDIS_URL: str = "redis://localhost:6379/0"
    CACHE_ENABLED: bool = True
    CACHE_TTL_ITEM_SECONDS: int = 300
    CACHE_TTL_LIST_SECONDS: int = 300

    model_config = SettingsConfigDict(
        env_file=f".env.{APP_ENV}",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )
    @property
    def cors_allow_origins_list(self) -> list[str]:
        return [
            origin.strip()
            for origin in self.CORS_ALLOW_ORIGINS.split(",")
            if origin.strip()
        ]

    @field_validator("API_KEY")
    @classmethod
    def validate_api_key_length(cls, value: str) -> str:
        if len(value) < 16:
            raise ValueError("API_KEY debe tener al menos 16 caracteres")
        return value

    @field_validator("JWT_SECRET_KEY")
    @classmethod
    def validate_jwt_secret_key_length(cls, value: str) -> str:
        if len(value) < 16:
            raise ValueError("JWT_SECRET_KEY debe tener al menos 16 caracteres")
        return value

    @field_validator("LOG_LEVEL")
    @classmethod
    def validate_log_level(cls, value: str) -> str:
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        value = value.upper()

        if value not in allowed:
            raise ValueError(f"LOG_LEVEL debe ser uno de: {allowed}")

        return value

    @field_validator("JWT_ALGORITHM")
    @classmethod
    def validate_jwt_algorithm(cls, value: str) -> str:
        allowed = {"HS256"}
        value = value.upper()

        if value not in allowed:
            raise ValueError(f"JWT_ALGORITHM debe ser uno de: {allowed}")

        return value

    @field_validator("ACCESS_TOKEN_EXPIRE_MINUTES")
    @classmethod
    def validate_access_token_expire_minutes(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("ACCESS_TOKEN_EXPIRE_MINUTES debe ser mayor que 0")
        return value

    @field_validator("REFRESH_TOKEN_EXPIRE_DAYS")
    @classmethod
    def validate_refresh_token_expire_days(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("REFRESH_TOKEN_EXPIRE_DAYS debe ser mayor que 0")
        return value


settings = Settings()