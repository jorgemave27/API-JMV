#!/bin/bash

API_CONTAINER="api-jmv-api"

echo "======================================"
echo "ENSURE ADMIN USER"
echo "======================================"

docker exec -i "$API_CONTAINER" python - <<'PY'
from app.database.database import SessionLocal
from app.models.usuario import Usuario
from app.core.security import hash_password

EMAIL = "admin@empresa.com"
PASSWORD = "Admin123!"
ROL = "admin"

db = SessionLocal()
try:
    user = db.query(Usuario).filter(Usuario.email == EMAIL).first()

    if user is None:
        user = Usuario(
            email=EMAIL,
            hashed_password=hash_password(PASSWORD),
            activo=True,
            rol=ROL,
            failed_login_attempts=0,
            blocked_until=None,
            reset_token_hash=None,
            reset_token_expires_at=None,
            reset_token_used_at=None,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        print("✅ Usuario admin creado")
    else:
        user.hashed_password = hash_password(PASSWORD)
        user.activo = True
        user.rol = ROL
        user.failed_login_attempts = 0
        user.blocked_until = None
        user.reset_token_hash = None
        user.reset_token_expires_at = None
        user.reset_token_used_at = None
        db.add(user)
        db.commit()
        db.refresh(user)
        print("✅ Usuario admin actualizado")

    print(f"id={user.id}")
    print(f"email={user.email}")
    print(f"rol={user.rol}")
    print("password=Admin123!")
finally:
    db.close()
PY

echo "======================================"
