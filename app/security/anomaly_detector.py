"""
Sistema de detección de anomalías e intrusiones.

Detecta:
- Fuerza bruta (401 repetidos)
- Scraping (alto volumen requests)
- Escaneo de endpoints (muchos 404 distintos)

Utiliza Redis para contadores con TTL.
"""

from __future__ import annotations

import ipaddress
from typing import Optional

from app.core.redis_client import redis_client


class AnomalyDetector:
    """
    Detector de anomalías basado en Redis.
    """

    # ------------------------------
    # UMBRALES DE SEGURIDAD
    # ------------------------------

    MAX_401_ATTEMPTS = 10
    WINDOW_401_SECONDS = 300

    MAX_REQUESTS_PER_MINUTE = 500

    MAX_404_ENDPOINTS = 20

    BLOCK_TIME_SECONDS = 3600

    # ------------------------------
    # IPs / hosts explícitamente seguros
    # ------------------------------
    SAFE_IPS = {
        "127.0.0.1",
        "::1",
        "localhost",
        "unknown",
        "host.docker.internal",
        "api-jmv-api",
        "gateway",
        "nginx",
    }

    # ------------------------------

    def __init__(self) -> None:
        self.redis = redis_client

    # ------------------------------
    # UTILIDADES
    # ------------------------------

    def _key_401(self, ip: str) -> str:
        return f"security:401:{ip}"

    def _key_rate(self, ip: str) -> str:
        return f"security:rate:{ip}"

    def _key_404(self, ip: str) -> str:
        return f"security:404:{ip}"

    def _key_block(self, ip: str) -> str:
        return f"security:block:{ip}"

    def is_safe_ip(self, ip: str) -> bool:
        """
        Determina si una IP o host es seguro para entorno local/dev.

        Se consideran seguros:
        - localhost
        - loopback
        - redes privadas RFC1918
        - hosts comunes de Docker / reverse proxy local
        """
        if not ip:
            return True

        ip_normalized = ip.strip().lower()

        if ip_normalized in self.SAFE_IPS:
            return True

        try:
            parsed_ip = ipaddress.ip_address(ip_normalized)

            if parsed_ip.is_loopback:
                return True

            if parsed_ip.is_private:
                return True

            return False

        except ValueError:
            # Si no parsea como IP, permitimos hosts típicos de red local/dev
            if (
                ip_normalized.startswith("172.")
                or ip_normalized.startswith("192.168.")
                or ip_normalized.startswith("10.")
            ):
                return True

            return False

    # ------------------------------
    # BLOQUEO IP
    # ------------------------------

    def block_ip(self, ip: str) -> None:
        """
        Bloquea IP temporalmente.
        Las IPs seguras nunca se bloquean.
        """
        if self.is_safe_ip(ip):
            return

        self.redis.setex(self._key_block(ip), self.BLOCK_TIME_SECONDS, "1")

    def is_ip_blocked(self, ip: str) -> bool:
        """
        Verifica si IP está bloqueada.
        Las IPs seguras nunca se consideran bloqueadas.
        """
        if self.is_safe_ip(ip):
            return False

        return self.redis.exists(self._key_block(ip)) == 1

    # ------------------------------
    # DETECCIÓN 401 (fuerza bruta)
    # ------------------------------

    def record_401(self, ip: str) -> Optional[str]:
        """
        Registra intento fallido de autenticación.
        """
        if self.is_safe_ip(ip):
            return None

        key = self._key_401(ip)

        count = self.redis.incr(key)

        if count == 1:
            self.redis.expire(key, self.WINDOW_401_SECONDS)

        if count > self.MAX_401_ATTEMPTS:
            self.block_ip(ip)
            return "too_many_401"

        return None

    # ------------------------------
    # RATE LIMIT
    # ------------------------------

    def record_request(self, ip: str) -> Optional[str]:
        """
        Registra requests por minuto.
        """
        if self.is_safe_ip(ip):
            return None

        key = self._key_rate(ip)

        count = self.redis.incr(key)

        if count == 1:
            self.redis.expire(key, 60)

        if count > self.MAX_REQUESTS_PER_MINUTE:
            return "rate_limit"

        return None

    # ------------------------------
    # SCANNER DETECTION
    # ------------------------------

    def record_404(self, ip: str, endpoint: str) -> Optional[str]:
        """
        Detecta escaneo de endpoints.
        """
        if self.is_safe_ip(ip):
            return None

        key = self._key_404(ip)

        self.redis.sadd(key, endpoint)
        self.redis.expire(key, 300)

        count = self.redis.scard(key)

        if count > self.MAX_404_ENDPOINTS:
            self.block_ip(ip)
            return "scanner_detected"

        return None
