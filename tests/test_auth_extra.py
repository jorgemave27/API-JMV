from __future__ import annotations

from app.core.security import hash_password
from app.models.usuario import Usuario


def test_refresh_token_rechaza_access_token(client, admin_auth_headers):
    access_token = admin_auth_headers["Authorization"].replace("Bearer ", "")

    response = client.post(
        "/api/v1/auth/refresh",
        headers={"X-API-Key": "dev-secret-key-change-me"},
        json={"refresh_token": access_token},
    )

    assert response.status_code == 401, response.text
    assert "refresh token" in response.text.lower()


def test_cambiar_password_exitoso(client, admin_auth_headers):
    response = client.post(
        "/api/v1/auth/cambiar-password",
        headers=admin_auth_headers,
        json={
            "current_password": "Test123!",
            "new_password": "Nuevo123!",
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["success"] is True


def test_forgot_password_generates_reset_token_data(client, admin_auth_headers, db_session):
    # El usuario admin@test.com ya existe por la fixture admin_auth_headers
    response = client.post(
        "/api/v1/auth/forgot-password",
        headers={"X-API-Key": "dev-secret-key-change-me"},
        json={"email": "admin@test.com"},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["success"] is True

    user = db_session.query(Usuario).filter(Usuario.email == "admin@test.com").first()
    assert user is not None
    assert user.reset_token_hash is not None
    assert user.reset_token_expires_at is not None
    assert user.reset_token_used_at is None


def test_reset_password_token_invalido(client):
    response = client.post(
        "/api/v1/auth/reset-password",
        headers={"X-API-Key": "dev-secret-key-change-me"},
        json={
            "token": "token-invalido",
            "new_password": "Reset123!",
        },
    )

    assert response.status_code == 400, response.text
    assert "token inválido" in response.text.lower() or "token invalido" in response.text.lower()


def test_login_usuario_inactivo(client, db_session):
    user = Usuario(
        email="inactivo@test.com",
        hashed_password=hash_password("Test123!"),
        activo=False,
        rol="lector",
    )
    db_session.add(user)
    db_session.commit()

    response = client.post(
        "/api/v1/auth/login",
        headers={"X-API-Key": "dev-secret-key-change-me"},
        json={
            "email": "inactivo@test.com",
            "password": "Test123!",
        },
    )

    assert response.status_code == 401, response.text
    assert "inactivo" in response.text.lower()


def test_cambiar_password_falla_si_password_actual_es_incorrecta(client, admin_auth_headers):
    response = client.post(
        "/api/v1/auth/cambiar-password",
        headers=admin_auth_headers,
        json={
            "current_password": "PasswordIncorrecta123!",
            "new_password": "Nuevo123!",
        },
    )

    assert response.status_code == 400, response.text
    assert "contraseña actual" in response.text.lower() or "contrasena actual" in response.text.lower()
