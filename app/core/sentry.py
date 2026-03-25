from __future__ import annotations

import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.redis import RedisIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

from app.core.config import get_settings


# =====================================================
# 🔐 SCRUB DE DATOS SENSIBLES
# =====================================================
def scrub_sensitive_data(event, hint):
    sensitive_keys = {"password", "token", "authorization", "api_key", "secret"}

    def _scrub(value):
        if isinstance(value, dict):
            cleaned = {}
            for k, v in value.items():
                if any(sk in k.lower() for sk in sensitive_keys):
                    cleaned[k] = "[FILTERED]"
                else:
                    cleaned[k] = _scrub(v)
            return cleaned
        if isinstance(value, list):
            return [_scrub(v) for v in value]
        return value

    try:
        if "request" in event:
            request_data = event["request"]

            if "data" in request_data:
                request_data["data"] = _scrub(request_data["data"])

            if "headers" in request_data:
                request_data["headers"] = _scrub(request_data["headers"])

            if "cookies" in request_data:
                request_data["cookies"] = _scrub(request_data["cookies"])

        if "extra" in event:
            event["extra"] = _scrub(event["extra"])

        if "user" in event and "email" in event["user"]:
            event["user"]["email"] = "[FILTERED]"

    except Exception:
        # 🔥 nunca romper request por scrub
        pass

    return event


# =====================================================
# 🔥 INIT SENTRY (SAFE MODE)
# =====================================================
def init_sentry():
    try:
        settings = get_settings()

        # 🔥 CLAVE: no DSN = no sentry = no rompe nada
        if not getattr(settings, "SENTRY_DSN", None):
            print("⚠️ Sentry desactivado (sin DSN)")
            return

        sentry_sdk.init(
            dsn=settings.SENTRY_DSN,
            environment=getattr(settings, "APP_ENV", "development"),
            integrations=[
                FastApiIntegration(),
                SqlalchemyIntegration(),
                RedisIntegration(),
            ],
            traces_sample_rate=0.1,
            before_send=scrub_sensitive_data,
            send_default_pii=False,
        )

        sentry_sdk.set_tag("release", getattr(settings, "VERSION", "unknown"))

        print("✅ Sentry inicializado correctamente")

    except Exception as e:
        # 🔥 ULTRA IMPORTANTE: nunca romper la app por Sentry
        print(f"❌ Sentry desactivado por error: {e}")