from __future__ import annotations

import os

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


APP_ENV = os.getenv("APP_ENV", "development")


class Settings(BaseSettings):
    """
    Configuración centralizada de la aplicación usando variables de entorno.

    Se cargan automáticamente desde:
    - Variables del sistema
    - Archivo .env.<entorno> en la raíz del proyecto

    Ejemplo:
    - APP_ENV=development -> .env.development
    - APP_ENV=production -> .env.production

    Beneficios:
    - Evita hardcodear secretos
    - Permite diferentes configuraciones por entorno
    - Validación automática de tipos
    """

    # Base de datos
    DATABASE_URL: str

    # Seguridad
    API_KEY: str

    # Logging
    LOG_LEVEL: str = "INFO"

    # Información de la app
    APP_NAME: str = "API JMV"
    APP_ENV: str = APP_ENV

    # Paginación
    MAX_ITEMS_PER_PAGE: int = 100

    # Configuración de pydantic-settings
    model_config = SettingsConfigDict(
        env_file=f".env.{APP_ENV}",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    @field_validator("API_KEY")
    @classmethod
    def validate_api_key_length(cls, value: str) -> str:
        """
        Valida que la API key tenga al menos 16 caracteres.
        """
        if len(value) < 16:
            raise ValueError("API_KEY debe tener al menos 16 caracteres")
        return value

    @field_validator("LOG_LEVEL")
    @classmethod
    def validate_log_level(cls, value: str) -> str:
        """
        Valida que el nivel de logging sea válido.
        """
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        value = value.upper()

        if value not in allowed:
            raise ValueError(f"LOG_LEVEL debe ser uno de: {allowed}")

        return value


# Instancia global de configuración
settings = Settings()