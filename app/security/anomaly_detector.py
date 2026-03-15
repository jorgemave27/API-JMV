from __future__ import annotations

# =====================================================
# DETECTOR DE ANOMALÍAS
# =====================================================
# - Usa Redis para registrar patrones sospechosos
# - Si Redis falla, NO rompe la app
# - En tests puede coexistir sin bloquear todo
# =====================================================

import logging

from app.core.config import settings

try:
    import redis
    from redis.exceptions import RedisError
except Exception:  # pragma: no cover
    redis = None
    RedisError = Exception


# Logger local del módulo
logger = logging.getLogger(__name__)


class AnomalyDetector:
    """
    Detector de anomalías con Redis.

    Reglas:
    - demasiados 401 -> posible fuerza bruta
    - demasiados requests/min -> posible abuso
    - demasiados 404 distintos -> posible escaneo
    """

    def __init__(self) -> None:
        self.enabled = True

        # Umbrales del reto
        self.max_401_attempts = 10
        self.max_requests_per_minute = 500
        self.max_distinct_404 = 20
        self.block_seconds = 3600  # 1 hora

        self.redis_client = None

        try:
            if redis is not None:
                self.redis_client = redis.from_url(
                    settings.REDIS_URL,
                    decode_responses=True,
                )
        except Exception:
            self.redis_client = None

    # =================================================
    # KEYS
    # =================================================

    def _key_401(self, ip: str) -> str:
        return f"security:401:{ip}"

    def _key_req(self, ip: str) -> str:
        return f"security:req:{ip}"

    def _key_404(self, ip: str) -> str:
        return f"security:404:{ip}"

    def _key_blocked(self, ip: str) -> str:
        return f"security:blocked:{ip}"

    # =================================================
    # BLOQUEO
    # =================================================

    def is_ip_blocked(self, ip: str) -> bool:
        """
        Verifica si la IP está bloqueada.
        """

        if not self.redis_client:
            return False

        try:
            return bool(self.redis_client.exists(self._key_blocked(ip)))
        except RedisError:
            return False
        except Exception:
            return False

    def block_ip(self, ip: str, reason: str) -> None:
        """
        Bloquea temporalmente una IP.
        """

        if not self.redis_client:
            return

        try:
            self.redis_client.setex(
                self._key_blocked(ip),
                self.block_seconds,
                reason,
            )
            logger.warning("IP bloqueada por anomalía: ip=%s reason=%s", ip, reason)
        except RedisError:
            pass
        except Exception:
            pass

    # =================================================
    # EVENTOS 401
    # =================================================

    def record_401(self, ip: str) -> None:
        """
        Registra un 401 para una IP.
        Si supera el umbral, se bloquea.
        """

        if not self.redis_client:
            return

        try:
            key = self._key_401(ip)
            current = self.redis_client.incr(key)

            if current == 1:
                self.redis_client.expire(key, 300)  # 5 min

            if current > self.max_401_attempts:
                self.block_ip(ip, "too_many_401")
        except RedisError:
            pass
        except Exception:
            pass

    # =================================================
    # EVENTOS REQUEST RATE
    # =================================================

    def record_request(self, ip: str) -> None:
        """
        Registra volumen de requests por minuto.
        """

        if not self.redis_client:
            return

        try:
            key = self._key_req(ip)
            current = self.redis_client.incr(key)

            if current == 1:
                self.redis_client.expire(key, 60)  # 1 minuto

            if current > self.max_requests_per_minute:
                self.block_ip(ip, "too_many_requests")
        except RedisError:
            pass
        except Exception:
            pass

    # =================================================
    # EVENTOS 404 DISTINTOS
    # =================================================

    def record_404(self, ip: str, path: str) -> None:
        """
        Registra endpoints 404 distintos.
        Si supera el umbral, se marca como scanner.
        """

        if not self.redis_client:
            return

        try:
            key = self._key_404(ip)

            self.redis_client.sadd(key, path)
            self.redis_client.expire(key, 300)  # 5 min

            distinct_count = self.redis_client.scard(key)

            if distinct_count > self.max_distinct_404:
                self.block_ip(ip, "scanner_detected")
        except RedisError:
            pass
        except Exception:
            pass


# =====================================================
# SINGLETON
# =====================================================

anomaly_detector = AnomalyDetector()