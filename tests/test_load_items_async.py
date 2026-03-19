import asyncio
import time

import httpx
import pytest

from app.core.config import limiter
from app.main import app

API_KEY = "dev-secret-key-change-me"
ENDPOINT = "/api/v1/items/?page=1&page_size=10"
HEADERS = {"X-API-Key": API_KEY}


async def fetch_one(client: httpx.AsyncClient) -> int:
    response = await client.get(ENDPOINT, headers=HEADERS)
    return response.status_code


@pytest.mark.asyncio
async def test_load_listar_items_100_concurrent_requests(setup_db):
    """
    Prueba de carga básica contra la app ASGI en memoria.

    Importante:
    - Usa setup_db para que los overrides de DB sync/async estén activos.
    - Desactiva temporalmente rate limiting para que las 100 requests no fallen con 429.
    """
    # Desactivar temporalmente el rate limit
    original_enabled = limiter.enabled
    limiter.enabled = False

    try:
        start = time.perf_counter()

        transport = httpx.ASGITransport(app=app)

        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
            timeout=30.0,
        ) as client:
            tasks = [fetch_one(client) for _ in range(100)]
            statuses = await asyncio.gather(*tasks)

        total_time = time.perf_counter() - start

        assert all(status == 200 for status in statuses), statuses

        print(f"Tiempo total para 100 requests concurrentes: {total_time:.4f}s")
    finally:
        limiter.enabled = original_enabled
