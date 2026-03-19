from __future__ import annotations

from app.core.security import hash_password, verify_password
from app.models.usuario import Usuario


def test_usuario_model_uses_hashed_password_not_plaintext(client, db_session, admin_auth_headers):
    """
    Verifica que el registro de usuario guarde hashed_password y nunca texto plano.
    """
    response = client.post(
        "/api/v1/usuarios/",
        json={
            "email": "nuevo@test.com",
            "password": "Segura123!",
            "rol": "lector",
        },
        headers=admin_auth_headers,
    )

    assert response.status_code == 200

    user = db_session.query(Usuario).filter(Usuario.email == "nuevo@test.com").first()
    assert user is not None
    assert user.hashed_password != "Segura123!"
    assert verify_password("Segura123!", user.hashed_password) is True


def test_registro_rechaza_password_debil(client, admin_auth_headers):
    """
    Verifica que el registro rechace contraseñas débiles.
    """
    response = client.post(
        "/api/v1/usuarios/",
        json={
            "email": "debil@test.com",
            "password": "abc123",
            "rol": "lector",
        },
        headers=admin_auth_headers,
    )

    assert response.status_code == 422


def test_cambiar_password_requires_current_password(client, auth_headers):
    """
    Verifica que cambiar contraseña requiera la contraseña actual correcta.
    """
    response = client.post(
        "/api/v1/auth/cambiar-password",
        json={
            "current_password": "Incorrecta123!",
            "new_password": "NuevaSegura123!",
        },
        headers=auth_headers,
    )

    assert response.status_code == 400


def test_login_blocks_after_5_failed_attempts(client, db_session):
    """
    Verifica bloqueo temporal después de 5 intentos fallidos.
    """
    user = Usuario(
        email="bloqueo@test.com",
        hashed_password=hash_password("Valida123!"),
        activo=True,
        rol="lector",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    payload = {
        "email": "bloqueo@test.com",
        "password": "Incorrecta123!",
    }

    last_status = None
    for _ in range(5):
        response = client.post("/api/v1/auth/login", json=payload)
        last_status = response.status_code

    assert last_status == 401

    blocked_response = client.post("/api/v1/auth/login", json=payload)
    assert blocked_response.status_code == 423


def test_forgot_password_generates_reset_token_data(client, db_session):
    """
    Verifica que forgot-password genere hash y expiración del token.
    """
    user = Usuario(
        email="reset@test.com",
        hashed_password=hash_password("Valida123!"),
        activo=True,
        rol="lector",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    response = client.post(
        "/api/v1/auth/forgot-password",
        json={"email": "reset@test.com"},
    )

    assert response.status_code == 200

    db_session.refresh(user)
    assert user.reset_token_hash is not None
    assert user.reset_token_expires_at is not None
    assert user.reset_token_used_at is None
