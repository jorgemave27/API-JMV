from __future__ import annotations

import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()  # Carga variables desde .env (en dev)


@dataclass(frozen=True)
class Settings:
    app_name: str = os.getenv("APP_NAME", "API JMV")
    app_env: str = os.getenv("APP_ENV", "local")
    api_key: str = os.getenv("API_KEY", "dev-secret-key-change-me")
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./database.db")


settings = Settings()


