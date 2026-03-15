from __future__ import annotations

import os
from functools import lru_cache

from fastapi import Request
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.vault import vault_client


APP_ENV = os.getenv("APP_ENV", "development")


# -----------------------------------------------------
# Cargar secretos desde Vault ANTES de construir settings
# -----------------------------------------------------
try:
    if vault_client.enabled():
        secrets_data = vault_client.read_secret("secret/mi-api")

        if "API_KEY" in secrets_data:
            os.environ["API_KEY"] = secrets_data["API_KEY"]

        if "DB_PASSWORD" in secrets_data:
            os.environ["DB_PASSWORD"] = secrets_data["DB_PASSWORD"]

except Exception:
    # Vault no debe romper el arranque
    pass


# =====================================================
# Rate limiting
# =====================================================

def rate_limit_key_func(request: Request) -> str:

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
            return f"ip:{get_remote_address(request)}"

    return f"ip:{get_remote_address(request)}"


def dynamic_rate_limit(key: str) -> str:

    if key.startswith("user:"):
        return "1000/minute"

    return "50/minute"


limiter = Limiter(key_func=rate_limit_key_func)


# =====================================================
# Settings
# =====================================================

class Settings(BaseSettings):

    DATABASE_URL: str
    API_KEY: str
    APP_VERSION: str = "1.0.0"

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

    # Celery
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/1"
    CELERY_ENABLED: bool = False

    # Kafka
    KAFKA_ENABLED: bool = True
    KAFKA_BOOTSTRAP_SERVERS: str = "localhost:9092"
    KAFKA_CLIENT_ID: str = "api-jmv"
    KAFKA_EVENTS_TOPIC: str = "jmv.domain-events"

    # Consul
    CONSUL_ENABLED: bool = False
    CONSUL_HOST: str = "localhost"
    CONSUL_PORT: int = 8500

    SERVICE_NAME: str = "api-jmv"
    SERVICE_HOST: str = "localhost"
    SERVICE_PORT: int = 8000
    SERVICE_TAGS: str = "api,fastapi,jmv"

    # Resilience
    EXTERNAL_HTTP_TIMEOUT_SECONDS: float = 3.0
    EXTERNAL_CACHE_TTL_SECONDS: int = 300
    RESILIENCE_MOCK_BASE_URL: str = "http://127.0.0.1:8000/api/v1/admin/resilience/mock-external"

    model_config = SettingsConfigDict(
        env_file=f".env.{APP_ENV}",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # -------------------------------------------------
    # Helpers
    # -------------------------------------------------

    @property
    def cors_allow_origins_list(self) -> list[str]:
        return [
            origin.strip()
            for origin in self.CORS_ALLOW_ORIGINS.split(",")
            if origin.strip()
        ]

    @property
    def service_tags_list(self) -> list[str]:
        return [
            tag.strip()
            for tag in self.SERVICE_TAGS.split(",")
            if tag.strip()
        ]

    # -------------------------------------------------
    # Validaciones
    # -------------------------------------------------

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


# =====================================================
# Singleton settings
# =====================================================

@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
