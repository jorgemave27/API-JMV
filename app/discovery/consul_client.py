from __future__ import annotations

import logging

import consul

from app.core.config import settings

logger = logging.getLogger(__name__)


def get_consul_client() -> consul.Consul:
    """
    Crea un cliente de Consul usando la configuración central.
    """
    return consul.Consul(host=settings.CONSUL_HOST, port=settings.CONSUL_PORT)


def build_service_id(name: str, host: str, port: int) -> str:
    """
    Construye un service_id estable para la instancia actual.
    """
    safe_host = host.replace(".", "-")
    return f"{name}-{safe_host}-{port}"


def register_service(name: str, port: int, tags: list[str] | None = None) -> str:
    """
    Registra este servicio en Consul con health check HTTP a /health.

    Retorna:
    - service_id para poder desregistrarlo en shutdown.
    """
    client = get_consul_client()
    host = settings.SERVICE_HOST
    tags = tags or []

    service_id = build_service_id(name=name, host=host, port=port)

    check = consul.Check.http(
        url=f"http://{host}:{port}/health",
        interval="10s",
        timeout="5s",
        deregister="1m",
    )

    client.agent.service.register(
        name=name,
        service_id=service_id,
        address=host,
        port=port,
        tags=tags,
        check=check,
    )

    logger.info(
        "Servicio registrado en Consul",
        extra={
            "service_name": name,
            "service_id": service_id,
            "service_host": host,
            "service_port": port,
            "service_tags": tags,
        },
    )

    return service_id


def deregister_service(service_id: str) -> None:
    """
    Elimina un servicio registrado en Consul.
    """
    client = get_consul_client()
    client.agent.service.deregister(service_id)

    logger.info(
        "Servicio desregistrado de Consul",
        extra={"service_id": service_id},
    )


def discover_service(name: str) -> tuple[str, int] | None:
    """
    Descubre una instancia healthy de un servicio por nombre.

    Retorna:
    - (host, port) si encuentra una instancia passing
    - None si no encuentra ninguna
    """
    client = get_consul_client()

    _, services = client.health.service(name, passing=True)

    if not services:
        logger.warning(
            "No se encontraron instancias healthy en Consul",
            extra={"service_name": name},
        )
        return None

    service = services[0]
    address = service["Service"].get("Address") or service["Node"].get("Address")
    port = service["Service"]["Port"]

    logger.info(
        "Servicio descubierto vía Consul",
        extra={
            "service_name": name,
            "address": address,
            "port": port,
        },
    )

    return address, port
