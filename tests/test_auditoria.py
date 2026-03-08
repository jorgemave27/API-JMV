from __future__ import annotations

from datetime import datetime, timedelta


def test_crear_item_generates_audit_record(client, auth_headers, admin_auth_headers):
    """
    Verifica que al crear un item se genere un registro de auditoría CREATE.
    """
    create_response = client.post(
        "/api/v1/items/",
        json={
            "name": "Item Auditoria Create",
            "description": "Prueba auditoría create",
            "price": 100.0,
            "sku": "AUD-CREATE-001",
            "codigo_sku": "AU-1001",
            "stock": 10,
        },
        headers=admin_auth_headers,
    )

    assert create_response.status_code == 200
    created_item = create_response.json()["data"]
    item_id = created_item["id"]

    history_response = client.get(
        f"/api/v1/items/{item_id}/historial",
        headers=auth_headers,
    )

    assert history_response.status_code == 200
    history = history_response.json()["data"]

    assert len(history) >= 1
    assert history[0]["accion"] == "CREATE"
    assert history[0]["item_id"] == item_id
    assert history[0]["datos_anteriores"] is None
    assert history[0]["datos_nuevos"]["name"] == "Item Auditoria Create"
    assert history[0]["usuario_id"] is not None


def test_delete_item_generates_audit_record(client, auth_headers, admin_auth_headers):
    """
    Verifica que el soft delete genere un registro de auditoría DELETE.
    """
    create_response = client.post(
        "/api/v1/items/",
        json={
            "name": "Item Auditoria Delete",
            "description": "Prueba auditoría delete",
            "price": 150.0,
            "sku": "AUD-DELETE-001",
            "codigo_sku": "AD-1001",
            "stock": 5,
        },
        headers=admin_auth_headers,
    )

    assert create_response.status_code == 200
    item_id = create_response.json()["data"]["id"]

    delete_response = client.delete(
        f"/api/v1/items/{item_id}",
        headers=admin_auth_headers,
    )

    assert delete_response.status_code == 200

    history_response = client.get(
        f"/api/v1/items/{item_id}/historial",
        headers=auth_headers,
    )

    assert history_response.status_code == 200
    history = history_response.json()["data"]

    assert len(history) >= 2
    assert history[-1]["accion"] == "DELETE"
    assert history[-1]["datos_anteriores"]["eliminado"] is False
    assert history[-1]["datos_nuevos"]["eliminado"] is True


def test_restaurar_item_generates_update_audit_record(client, auth_headers, admin_auth_headers):
    """
    Verifica que restaurar un item eliminado genere auditoría UPDATE.
    """
    create_response = client.post(
        "/api/v1/items/",
        json={
            "name": "Item Auditoria Restore",
            "description": "Prueba auditoría restore",
            "price": 200.0,
            "sku": "AUD-RESTORE-001",
            "codigo_sku": "AR-1001",
            "stock": 7,
        },
        headers=admin_auth_headers,
    )

    assert create_response.status_code == 200
    item_id = create_response.json()["data"]["id"]

    delete_response = client.delete(
        f"/api/v1/items/{item_id}",
        headers=admin_auth_headers,
    )
    assert delete_response.status_code == 200

    restore_response = client.post(
        f"/api/v1/items/{item_id}/restaurar",
        headers=admin_auth_headers,
    )
    assert restore_response.status_code == 200

    history_response = client.get(
        f"/api/v1/items/{item_id}/historial",
        headers=auth_headers,
    )

    assert history_response.status_code == 200
    history = history_response.json()["data"]

    assert len(history) >= 3
    assert history[-1]["accion"] == "UPDATE"
    assert history[-1]["datos_anteriores"]["eliminado"] is True
    assert history[-1]["datos_nuevos"]["eliminado"] is False


def test_historial_returns_records_in_chronological_order(client, auth_headers, admin_auth_headers):
    """
    Verifica que el historial se regrese ordenado cronológicamente.
    """
    create_response = client.post(
        "/api/v1/items/",
        json={
            "name": "Item Auditoria Orden",
            "description": "Prueba orden historial",
            "price": 120.0,
            "sku": "AUD-ORDER-001",
            "codigo_sku": "AO-1001",
            "stock": 3,
        },
        headers=admin_auth_headers,
    )

    assert create_response.status_code == 200
    item_id = create_response.json()["data"]["id"]

    delete_response = client.delete(
        f"/api/v1/items/{item_id}",
        headers=admin_auth_headers,
    )
    assert delete_response.status_code == 200

    restore_response = client.post(
        f"/api/v1/items/{item_id}/restaurar",
        headers=admin_auth_headers,
    )
    assert restore_response.status_code == 200

    history_response = client.get(
        f"/api/v1/items/{item_id}/historial",
        headers=auth_headers,
    )

    assert history_response.status_code == 200
    history = history_response.json()["data"]

    timestamps = [row["timestamp"] for row in history]
    assert timestamps == sorted(timestamps)


def test_estado_reconstructs_item_state_at_specific_time(client, auth_headers, admin_auth_headers):
    """
    Verifica el reto: reconstrucción del estado del item en una fecha específica.
    """
    before_create = datetime.utcnow() - timedelta(seconds=1)

    create_response = client.post(
        "/api/v1/items/",
        json={
            "name": "Item Auditoria PITR",
            "description": "Prueba point in time recovery",
            "price": 300.0,
            "sku": "AUD-PITR-001",
            "codigo_sku": "AP-1001",
            "stock": 11,
        },
        headers=admin_auth_headers,
    )

    assert create_response.status_code == 200
    created_item = create_response.json()["data"]
    item_id = created_item["id"]

    history_response = client.get(
        f"/api/v1/items/{item_id}/historial",
        headers=auth_headers,
    )
    assert history_response.status_code == 200

    history = history_response.json()["data"]
    create_timestamp = history[0]["timestamp"]

    # -------------------------------------------------------------
    # Estado antes de la creación: no debería existir
    # -------------------------------------------------------------
    state_before_response = client.get(
        f"/api/v1/items/{item_id}/estado",
        params={"fecha": before_create.isoformat()},
        headers=auth_headers,
    )

    assert state_before_response.status_code == 200
    state_before_data = state_before_response.json()["data"]

    assert state_before_data["item_id"] == item_id
    assert state_before_data["exists_at_that_time"] is False
    assert state_before_data["estado"] is None

    # -------------------------------------------------------------
    # Estado en/tras creación: debería existir
    # -------------------------------------------------------------
    state_after_response = client.get(
        f"/api/v1/items/{item_id}/estado",
        params={"fecha": create_timestamp},
        headers=auth_headers,
    )

    assert state_after_response.status_code == 200
    state_after_data = state_after_response.json()["data"]

    assert state_after_data["item_id"] == item_id
    assert state_after_data["exists_at_that_time"] is True
    assert state_after_data["estado"]["name"] == "Item Auditoria Pitr"