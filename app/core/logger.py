from __future__ import annotations

"""
Centralized structured logging for API-JMV.

- JSON structured logs
- Logstash async handler
- Trace correlation support
- Compatible with ELK stack
"""

import json
import logging
import os
import sys
from datetime import datetime
from typing import Any

from logstash_async.formatter import LogstashFormatter
from logstash_async.handler import AsynchronousLogstashHandler


# ---------------------------------------------------------
# Configuración básica
# ---------------------------------------------------------

SERVICE_NAME = os.getenv("SERVICE_NAME", "api-jmv")
ENVIRONMENT = os.getenv("APP_ENV", "development")

LOGSTASH_HOST = os.getenv("LOGSTASH_HOST", "logstash")
LOGSTASH_PORT = int(os.getenv("LOGSTASH_PORT", "5044"))

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()


# ---------------------------------------------------------
# JSON Formatter
# ---------------------------------------------------------

class JsonFormatter(logging.Formatter):
    """
    Convierte los logs en JSON estructurado
    para que ELK pueda indexarlos correctamente.
    """

    def format(self, record: logging.LogRecord) -> str:

        log_record: dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat(),
            "service_name": SERVICE_NAME,
            "environment": ENVIRONMENT,
            "level": record.levelname,
            "message": record.getMessage(),
        }

        # campos opcionales que agregan middlewares
        if hasattr(record, "trace_id"):
            log_record["trace_id"] = record.trace_id

        if hasattr(record, "user_id"):
            log_record["user_id"] = record.user_id

        if hasattr(record, "path"):
            log_record["path"] = record.path

        if hasattr(record, "method"):
            log_record["method"] = record.method

        if hasattr(record, "status_code"):
            log_record["status_code"] = record.status_code

        if hasattr(record, "latency_ms"):
            log_record["latency_ms"] = record.latency_ms

        # errores
        if record.exc_info:
            log_record["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_record)


# ---------------------------------------------------------
# Setup logging
# ---------------------------------------------------------

def setup_logging() -> logging.Logger:
    """
    Configura logging global.

    - stdout JSON logs
    - envío asíncrono a Logstash
    """

    logger = logging.getLogger("api-jmv")
    logger.setLevel(LOG_LEVEL)

    # evita duplicación si ya existe
    if logger.handlers:
        return logger

    # -----------------------------------
    # Console handler (stdout)
    # -----------------------------------

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(JsonFormatter())

    logger.addHandler(console_handler)

    # -----------------------------------
    # Logstash handler
    # -----------------------------------

    try:

        logstash_handler = AsynchronousLogstashHandler(
            host=LOGSTASH_HOST,
            port=LOGSTASH_PORT,
            database_path=None,
        )

        logstash_handler.setFormatter(LogstashFormatter())

        logger.addHandler(logstash_handler)

    except Exception:
        # Si logstash no está levantado no rompe la app
        pass

    return logger


# ---------------------------------------------------------
# Logger global
# ---------------------------------------------------------

logger = setup_logging()