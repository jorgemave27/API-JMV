"""
SMS PROVIDER (SIMULADO)
"""

import logging

logger = logging.getLogger(__name__)


class SMSProvider:
    def send(self, phone: str, message: str) -> bool:
        """
        Simula envío SMS
        """
        logger.info(f"[SMS] {phone}: {message}")
        return True