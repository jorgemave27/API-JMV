from __future__ import annotations

# =====================================================
# DETECTOR DE ANOMALÍAS
# =====================================================
# - Usa Redis para registrar patrones sospechosos
# - Si Redis falla, NO rompe la app
# - Incluye detección de token theft
# =====================================================
import logging

from app.core.config import settings

try:
    import redis
    from redis.exceptions import RedisError
except Exception:  # pragma: no cover
    redis = None
    RedisError = Exception


logger = logging.getLogger(__name__)


class AnomalyDetector:
    def __init__(self) -> None:

        self.enabled = True

        self.max_401_attempts = 10
        self.max_requests_per_minute = 500
        self.max_distinct_404 = 20
        self.block_seconds = 3600

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

    def _key_token_ip(self, jti: str) -> str:
        return f"security:token-ip:{jti}"

    # =================================================
    # BLOQUEO
    # =================================================

    def is_ip_blocked(self, ip: str) -> bool:

        if not self.redis_client:
            return False

        try:
            return bool(self.redis_client.exists(self._key_blocked(ip)))
        except RedisError:
            return False

    def block_ip(self, ip: str, reason: str) -> None:

        if not self.redis_client:
            return

        try:
            self.redis_client.setex(
                self._key_blocked(ip),
                self.block_seconds,
                reason,
            )

            logger.warning("IP bloqueada por anomalía ip=%s reason=%s", ip, reason)

        except RedisError:
            pass

    # =================================================
    # EVENTOS 401
    # =================================================

    def record_401(self, ip: str) -> None:

        if not self.redis_client:
            return

        try:
            key = self._key_401(ip)
            current = self.redis_client.incr(key)

            if current == 1:
                self.redis_client.expire(key, 300)

            if current > self.max_401_attempts:
                self.block_ip(ip, "too_many_401")

        except RedisError:
            pass

    # =================================================
    # REQUEST RATE
    # =================================================

    def record_request(self, ip: str) -> None:

        if not self.redis_client:
            return

        try:
            key = self._key_req(ip)
            current = self.redis_client.incr(key)

            if current == 1:
                self.redis_client.expire(key, 60)

            if current > self.max_requests_per_minute:
                self.block_ip(ip, "too_many_requests")

        except RedisError:
            pass

    # =================================================
    # EVENTOS 404
    # =================================================

    def record_404(self, ip: str, path: str) -> None:

        if not self.redis_client:
            return

        try:
            key = self._key_404(ip)

            self.redis_client.sadd(key, path)
            self.redis_client.expire(key, 300)

            distinct_count = self.redis_client.scard(key)

            if distinct_count > self.max_distinct_404:
                self.block_ip(ip, "scanner_detected")

        except RedisError:
            pass

    # =================================================
    # TOKEN THEFT DETECTION
    # =================================================

    def detect_token_theft(self, jti: str, ip: str) -> bool:

        if not self.redis_client:
            return False

        key = self._key_token_ip(jti)

        try:
            stored_ip = self.redis_client.get(key)

            if stored_ip is None:
                self.redis_client.setex(key, 600, ip)
                return False

            if stored_ip != ip:
                logger.warning(
                    "SECURITY_EVENT posible_robo_token jti=%s ip1=%s ip2=%s",
                    jti,
                    stored_ip,
                    ip,
                )

                return True

            return False

        except RedisError:
            return False


# =====================================================
# SINGLETON
# =====================================================

anomaly_detector = AnomalyDetector()
