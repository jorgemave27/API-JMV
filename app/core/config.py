from __future__ import annotations

import os
from functools import lru_cache

from fastapi import Request
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.vault import vault_client


# =====================================================
# ENV
# =====================================================
APP_ENV = os.getenv("APP_ENV", "development")
TESTING = os.getenv("TESTING", "false").lower() == "true"


# -----------------------------------------------------
# Vault (NO en tests)
# -----------------------------------------------------
try:
    if APP_ENV != "test" and not TESTING and vault_client.enabled():
        secrets_data = vault_client.read_secret("secret/mi-api")

        for key in [
            "API_KEY",
            "DB_PASSWORD",
            "ENCRYPTION_KEY",
            "LOCAL_KMS_MASTER_KEY",
            "AWS_KMS_KEY_ID",
            "AWS_REGION",
            "KMS_PROVIDER",
        ]:
            if key in secrets_data and not os.getenv(key):
                os.environ[key] = secrets_data[key]

except Exception:
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
# SETTINGS
# =====================================================
class Settings(BaseSettings):

    # -------------------------------------------------
    # FLAGS CRÍTICOS
    # -------------------------------------------------
    TESTING: bool = TESTING
    ELASTIC_ENABLED: bool = not TESTING
    CHAOS_ENABLED: bool = not TESTING

    # -------------------------------------------------
    # Core (OBLIGATORIOS)
    # -------------------------------------------------
    DATABASE_URL: str
    API_KEY: str
    JWT_SECRET_KEY: str

    APP_NAME: str = "API JMV"
    APP_ENV: str = APP_ENV
    VERSION: str = "1.0.0"

    # 👉 SENTRY
    SENTRY_DSN: str | None = None

    # -------------------------------------------------
    # JWT
    # -------------------------------------------------
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # -------------------------------------------------
    # App config
    # -------------------------------------------------
    CORS_ALLOW_ORIGINS: str = "http://localhost:3000,https://mi-app.com"
    LOG_LEVEL: str = "INFO"
    MAX_ITEMS_PER_PAGE: int = 100

    # -------------------------------------------------
    # Redis / Cache
    # -------------------------------------------------
    REDIS_URL: str = "redis://localhost:6379/0"
    CACHE_ENABLED: bool = not TESTING

    CACHE_TTL_ITEM_SECONDS: int = 300
    CACHE_TTL_LIST_SECONDS: int = 300

    # -------------------------------------------------
    # Celery
    # -------------------------------------------------
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/1"
    CELERY_ENABLED: bool = False if TESTING else False

    # -------------------------------------------------
    # Kafka
    # -------------------------------------------------
    KAFKA_ENABLED: bool = False if TESTING else True
    KAFKA_BOOTSTRAP_SERVERS: str = "localhost:9092"
    KAFKA_CLIENT_ID: str = "api-jmv"
    KAFKA_EVENTS_TOPIC: str = "jmv.domain-events"

    # =====================================================
    # S3 / MINIO CONFIG
    # =====================================================
    S3_ENDPOINT: str = "http://minio:9000"
    S3_ACCESS_KEY: str = "minioadmin"
    S3_SECRET_KEY: str = "minioadmin"
    S3_BUCKET: str = "api-jmv"
    S3_REGION: str = "us-east-1"

    # -------------------------------------------------
    # Consul
    # -------------------------------------------------
    CONSUL_ENABLED: bool = False
    CONSUL_HOST: str = "localhost"
    CONSUL_PORT: int = 8500

    SERVICE_NAME: str = "api-jmv"
    SERVICE_HOST: str = "localhost"
    SERVICE_PORT: int = 8000
    SERVICE_TAGS: str = "api,fastapi,jmv"

    # -------------------------------------------------
    # Resilience
    # -------------------------------------------------
    EXTERNAL_HTTP_TIMEOUT_SECONDS: float = 3.0
    EXTERNAL_CACHE_TTL_SECONDS: int = 300
    RESILIENCE_MOCK_BASE_URL: str = "http://127.0.0.1:8000/api/v1/admin/resilience/mock-external"

    # -------------------------------------------------
    # Seguridad / cifrado
    # -------------------------------------------------
    ENCRYPTION_KEY: str | None = None

    # -------------------------------------------------
    # KMS
    # -------------------------------------------------
    KMS_PROVIDER: str = "local"
    LOCAL_KMS_MASTER_KEY: str | None = None
    AWS_KMS_KEY_ID: str | None = None
    AWS_REGION: str | None = None

    # -------------------------------------------------
    # Profiling
    # -------------------------------------------------
    PROFILING_ENABLED: bool = not TESTING
    PROFILING_SLOW_REQUEST_THRESHOLD_MS: float = 500.0
    PROFILING_CONSECUTIVE_SLOW_REQUESTS: int = 3
    PROFILING_OUTPUT_DIR: str = "profiles"

    # =====================================================
    # SENDGRID CONFIG 
    # =====================================================
    SENDGRID_API_KEY: str = "dummy"
    EMAIL_FROM: str = "noreply@api-jmv.com"

    # =====================================================
    # OpenAI / LLMs
    # =====================================================

    OPENAI_API_KEY: str | None = None

    # -------------------------------------------------
    # DB
    # -------------------------------------------------
    DATABASE_READ_URL: str | None = None
    DATABASE_SHARD_1: str | None = None
    DATABASE_SHARD_2: str | None = None

    # -------------------------------------------------
    # Pydantic config
    # -------------------------------------------------
    model_config = SettingsConfigDict(
        env_file=f".env.{APP_ENV}",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )
    # =====================================================
    # STRIPE
    # =====================================================
    STRIPE_SECRET_KEY: str = "sk_test_xxx"
    STRIPE_WEBHOOK_SECRET: str = "whsec_xxx"

    # =====================================================
    # OIDC / SSO (GOOGLE)
    # =====================================================
    GOOGLE_CLIENT_ID: str = "tu-client-id"
    GOOGLE_CLIENT_SECRET: str = "tu-client-secret"
    GOOGLE_DISCOVERY_URL: str = "https://accounts.google.com/.well-known/openid-configuration"

    # Redirect URI (debe coincidir con Google Console)
    GOOGLE_REDIRECT_URI: str = "http://localhost:8000/auth/google/callback"

    # Group Sync Mapping (correo → rol)
    SSO_GROUP_ROLE_MAPPING: dict[str, str] = {
        "engineering@empresa.com": "editor",
        "admin@empresa.com": "admin",
    }

    # -------------------------------------------------
    # Helpers
    # -------------------------------------------------
    @property
    def cors_allow_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ALLOW_ORIGINS.split(",") if o.strip()]

    @property
    def service_tags_list(self) -> list[str]:
        return [t.strip() for t in self.SERVICE_TAGS.split(",") if t.strip()]

    # -------------------------------------------------
    # Validaciones
    # -------------------------------------------------
    @field_validator("API_KEY")
    @classmethod
    def validate_api_key_length(cls, v: str) -> str:
        if len(v) < 16:
            raise ValueError("API_KEY debe tener al menos 16 caracteres")
        return v

    @field_validator("JWT_SECRET_KEY")
    @classmethod
    def validate_jwt_secret_key_length(cls, v: str) -> str:
        if len(v) < 16:
            raise ValueError("JWT_SECRET_KEY debe tener al menos 16 caracteres")
        return v

    @field_validator("KMS_PROVIDER")
    @classmethod
    def validate_kms_provider(cls, v: str) -> str:
        v = v.lower().strip()
        if v not in {"local", "aws"}:
            raise ValueError("KMS_PROVIDER debe ser 'local' o 'aws'")
        return v


# =====================================================
# Singleton
# =====================================================
@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()