from __future__ import annotations

import random
import string
import uuid
from typing import Any

import pytest

API_KEY = "dev-secret-key-change-me"
BASE_ITEMS = "/api/v1/items"

BASE_CATEGORIAS_CANDIDATAS = [
    "/categorias",
    "/api/v1/categorias",
]


def _headers(api_key: str = API_KEY, token: str | None = None) -> dict[str, str]:
    headers = {"X-API-Key": api_key}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _unique_sku(prefix: str = "SKU") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8].upper()}"


def _unique_codigo_sku() -> str:
    letras = "".join(random.choices(string.ascii_uppercase, k=2))
    numeros = "".join(random.choices(string.digits, k=4))
    return f"{letras}-{numeros}"


def _create_categoria(client, *, nombre: str, token: str | None = None) -> tuple[str, dict[str, Any]]:
    payload_variants = [
        {"nombre": nombre},
        {"name": nombre},
        {"nombre": nombre, "descripcion": "Categoría de prueba"},
        {"name": nombre, "description": "Categoría de prueba"},
    ]

    last_response = None

    for base in BASE_CATEGORIAS_CANDIDATAS:
        for payload in payload_variants:
            response = client.post(base, json=payload, headers=_headers(token=token))
            last_response = response
            if response.status_code in (200, 201):
                return base.rstrip("/"), response.json()

    raise AssertionError(
        f"No se pudo crear categoría. "
        f"Último status={getattr(last_response, 'status_code', 'N/A')} "
        f"body={getattr(last_response, 'text', 'N/A')}"
    )


def _delete_categoria(client, *, base_path: str, categoria_id: int, token: str | None = None) -> None:
    response = client.delete(
        f"{base_path}/{categoria_id}",
        headers=_headers(token=token),
    )
    assert response.status_code in (200, 204), response.text


def _list_items(client, *, token: str | None = None, params: dict[str, Any] | None = None) -> dict[str, Any]:
    response = client.get(
        f"{BASE_ITEMS}/",
        headers=_headers(token=token),
        params=params or {},
    )
    assert response.status_code == 200, response.text
    return response.json()


def _get_item(client, *, item_id: int, token: str | None = None) -> dict[str, Any]:
    response = client.get(
        f"{BASE_ITEMS}/{item_id}",
        headers=_headers(token=token),
    )
    assert response.status_code == 200, response.text
    return response.json()


def _create_item(
    client,
    *,
    token: str,
    name: str,
    price: float,
    stock: int,
    categoria_id: int | None = None,
) -> dict[str, Any]:
    payload = {
        "name": name,
        "description": "Item e2e",
        "price": price,
        "sku": _unique_sku("ITEM"),
        "codigo_sku": _unique_codigo_sku(),
        "stock": stock,
    }
    if categoria_id is not None:
        payload["categoria_id"] = categoria_id

    response = client.post(
        f"{BASE_ITEMS}/",
        json=payload,
        headers=_headers(token=token),
    )
    assert response.status_code in (200, 201), response.text
    return response.json()


def _update_item_price(client, *, token: str, item_id: int, new_price: float) -> dict[str, Any]:
    current = _get_item(client, item_id=item_id, token=token)
    current_data = current["data"]

    full_payload = {
        "name": current_data["name"],
        "description": current_data.get("description"),
        "price": new_price,
        "sku": current_data["sku"],
        "codigo_sku": current_data["codigo_sku"],
        "stock": current_data["stock"],
        "categoria_id": current_data.get("categoria_id"),
    }

    response = client.put(
        f"{BASE_ITEMS}/{item_id}",
        json=full_payload,
        headers=_headers(token=token),
    )

    if response.status_code == 200:
        return response.json()

    if response.status_code != 405:
        raise AssertionError(response.text)

    patch_payload = {
        "price": new_price,
    }

    response = client.patch(
        f"{BASE_ITEMS}/{item_id}",
        json=patch_payload,
        headers=_headers(token=token),
    )
    assert response.status_code == 200, response.text
    return response.json()


def _get_item_historial(client, *, item_id: int, token: str | None = None) -> list[dict[str, Any]]:
    response = client.get(
        f"{BASE_ITEMS}/{item_id}/historial",
        headers=_headers(token=token),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    return body.get("data", [])


@pytest.fixture
def admin_token(usuario_admin) -> str:
    return usuario_admin["token"]


@pytest.fixture
def lector_token(usuario_lector) -> str:
    return usuario_lector["token"]


def test_flujo_integracion_1_registro_login_item_auditoria(client, admin_token):
    created = _create_item(
        client,
        token=admin_token,
        name="Caja Integracion Flujo 1",
        price=100.0,
        stock=10,
    )
    item = created["data"]
    item_id = item["id"]

    buscados = client.get(
        f"{BASE_ITEMS}/buscar",
        params={"nombre": "Caja Integracion Flujo 1"},
        headers=_headers(token=admin_token),
    )
    assert buscados.status_code == 200, buscados.text
    buscados_body = buscados.json()
    assert len(buscados_body["data"]) >= 1
    assert any(i["id"] == item_id for i in buscados_body["data"])

    updated = _update_item_price(
        client,
        token=admin_token,
        item_id=item_id,
        new_price=149.99,
    )
    assert updated["data"]["price"] == 149.99

    historial = _get_item_historial(client, item_id=item_id, token=admin_token)
    assert len(historial) >= 2

    acciones = [h.get("accion") for h in historial]
    assert "CREATE" in acciones
    assert "UPDATE" in acciones

    update_events = [h for h in historial if h.get("accion") == "UPDATE"]
    assert update_events, "No se encontró evento UPDATE en auditoría"

    found_price_change = False
    for ev in update_events:
        datos_nuevos = ev.get("datos_nuevos") or {}
        if datos_nuevos.get("price") == 149.99:
            found_price_change = True
            break

    assert found_price_change, "La auditoría no refleja el cambio de precio esperado"


def test_flujo_integracion_2_categoria_item_relacion(client, admin_token):
    categoria_nombre = f"Categoria E2E {uuid.uuid4().hex[:6]}"
    categorias_base, categoria_response = _create_categoria(
        client,
        nombre=categoria_nombre,
        token=admin_token,
    )

    categoria_data = categoria_response.get("data", categoria_response)
    categoria_id = categoria_data["id"]

    created = _create_item(
        client,
        token=admin_token,
        name="Caja con categoria e2e",
        price=80.0,
        stock=5,
        categoria_id=categoria_id,
    )
    item_id = created["data"]["id"]

    listed = _list_items(
        client,
        token=admin_token,
        params={"categoria_id": categoria_id},
    )

    listed_items = listed["data"]["items"]
    assert any(i["id"] == item_id for i in listed_items), (
        "El item creado no apareció al filtrar por categoria_id."
    )

    _delete_categoria(
        client,
        base_path=categorias_base,
        categoria_id=categoria_id,
        token=admin_token,
    )

    item_after = _get_item(client, item_id=item_id, token=admin_token)
    assert item_after["data"]["categoria_id"] is None


def test_flujo_integracion_3_rbac_lector_vs_admin(client, admin_token, lector_token):
    payload = {
        "name": "Caja RBAC E2E",
        "description": "Prueba RBAC end to end",
        "price": 55.0,
        "sku": _unique_sku("RBAC"),
        "codigo_sku": _unique_codigo_sku(),
        "stock": 3,
    }

    forbidden = client.post(
        f"{BASE_ITEMS}/",
        json=payload,
        headers=_headers(token=lector_token),
    )
    assert forbidden.status_code == 403, forbidden.text

    created = client.post(
        f"{BASE_ITEMS}/",
        json=payload,
        headers=_headers(token=admin_token),
    )
    assert created.status_code in (200, 201), created.text

    item_id = created.json()["data"]["id"]

    read_by_lector = client.get(
        f"{BASE_ITEMS}/{item_id}",
        headers=_headers(token=lector_token),
    )
    assert read_by_lector.status_code == 200, read_by_lector.text
    assert read_by_lector.json()["data"]["id"] == item_id