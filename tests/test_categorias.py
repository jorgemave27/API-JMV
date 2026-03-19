from __future__ import annotations

from typing import Any

from tests.conftest import create_item

BASE_CATEGORIAS = "/categorias"


def _extract_data(body: dict[str, Any]) -> Any:
    """
    Soporta respuestas con wrapper ApiResponse o respuestas planas.
    """
    if isinstance(body, dict) and "data" in body:
        return body["data"]
    return body


def _create_categoria(client, headers, *, nombre: str, descripcion: str = "categoria test") -> dict[str, Any]:
    payloads = [
        {"nombre": nombre, "descripcion": descripcion},
        {"name": nombre, "description": descripcion},
        {"nombre": nombre},
        {"name": nombre},
    ]

    last_response = None

    for payload in payloads:
        response = client.post(f"{BASE_CATEGORIAS}/", json=payload, headers=headers)
        last_response = response
        if response.status_code in (200, 201):
            body = response.json()
            data = _extract_data(body)
            assert isinstance(data, dict)
            assert "id" in data
            return data

    raise AssertionError(
        f"No se pudo crear categoría. "
        f"Último status={getattr(last_response, 'status_code', 'N/A')} "
        f"body={getattr(last_response, 'text', 'N/A')}"
    )


def _get_categoria(client, headers, categoria_id: int):
    return client.get(f"{BASE_CATEGORIAS}/{categoria_id}", headers=headers)


def _list_categorias(client, headers):
    return client.get(f"{BASE_CATEGORIAS}/", headers=headers)


def _update_categoria(client, headers, categoria_id: int, *, nombre: str, descripcion: str = "actualizada"):
    payloads = [
        {"nombre": nombre, "descripcion": descripcion},
        {"name": nombre, "description": descripcion},
        {"nombre": nombre},
        {"name": nombre},
    ]

    last_response = None

    for payload in payloads:
        response = client.put(f"{BASE_CATEGORIAS}/{categoria_id}", json=payload, headers=headers)
        last_response = response
        if response.status_code in (200, 201):
            return response

        if response.status_code == 405:
            response = client.patch(f"{BASE_CATEGORIAS}/{categoria_id}", json=payload, headers=headers)
            last_response = response
            if response.status_code in (200, 201):
                return response

    raise AssertionError(
        f"No se pudo actualizar categoría. "
        f"Último status={getattr(last_response, 'status_code', 'N/A')} "
        f"body={getattr(last_response, 'text', 'N/A')}"
    )


def _delete_categoria(client, headers, categoria_id: int):
    return client.delete(f"{BASE_CATEGORIAS}/{categoria_id}", headers=headers)


def test_categoria_crud_basico(client, admin_auth_headers):
    creada = _create_categoria(
        client,
        admin_auth_headers,
        nombre="Categoria CRUD",
        descripcion="categoria para probar CRUD",
    )
    categoria_id = creada["id"]

    response_list = _list_categorias(client, admin_auth_headers)
    assert response_list.status_code == 200, response_list.text
    list_body = response_list.json()
    list_data = _extract_data(list_body)

    if isinstance(list_data, dict) and "items" in list_data:
        categorias = list_data["items"]
    else:
        categorias = list_data

    assert isinstance(categorias, list)
    assert any(c["id"] == categoria_id for c in categorias)

    response_get = _get_categoria(client, admin_auth_headers, categoria_id)
    assert response_get.status_code == 200, response_get.text
    get_data = _extract_data(response_get.json())
    assert get_data["id"] == categoria_id

    response_update = _update_categoria(
        client,
        admin_auth_headers,
        categoria_id,
        nombre="Categoria CRUD Actualizada",
        descripcion="categoria editada",
    )
    assert response_update.status_code in (200, 201), response_update.text

    updated_data = _extract_data(response_update.json())
    assert updated_data["id"] == categoria_id

    response_get_updated = _get_categoria(client, admin_auth_headers, categoria_id)
    assert response_get_updated.status_code == 200, response_get_updated.text
    get_updated_data = _extract_data(response_get_updated.json())

    # La API aparentemente normaliza a Title Case.
    nombre_actual = get_updated_data.get("nombre") or get_updated_data.get("name")
    assert nombre_actual is not None
    assert nombre_actual.casefold() == "Categoria Crud Actualizada".casefold()


def test_eliminar_categoria_desasocia_items(client, admin_auth_headers):
    categoria = _create_categoria(
        client,
        admin_auth_headers,
        nombre="Categoria Con Items",
        descripcion="categoria para desasociar items",
    )
    categoria_id = categoria["id"]

    item = create_item(
        client,
        admin_auth_headers,
        name="Caja con categoria",
        price=120.0,
        stock=10,
        sku_prefix="CAT",
        categoria_id=categoria_id,
    )
    item_id = item["id"]

    response_delete = _delete_categoria(client, admin_auth_headers, categoria_id)
    assert response_delete.status_code in (200, 204), response_delete.text

    response_item = client.get(f"/api/v1/items/{item_id}", headers=admin_auth_headers)
    assert response_item.status_code == 200, response_item.text

    item_body = response_item.json()
    item_data = item_body["data"]
    assert item_data["categoria_id"] is None


def test_categoria_no_encontrada(client, admin_auth_headers):
    response_get = _get_categoria(client, admin_auth_headers, 999999)
    assert response_get.status_code in (404, 400), response_get.text

    response_delete = _delete_categoria(client, admin_auth_headers, 999999)
    assert response_delete.status_code in (404, 400), response_delete.text
