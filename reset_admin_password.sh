#!/bin/bash

API_CONTAINER="api-jmv-api"

echo "======================================"
echo "RESET ADMIN PASSWORD"
echo "======================================"

docker exec -i "$API_CONTAINER" python - <<'PY'
from app.database.database import SessionLocal
from app.models.usuario import Usuario
from app.core.security import hash_password

EMAIL = "admin@empresa.com"
NEW_PASSWORD = "Admin123!"

db = SessionLocal()
try:
    user = db.query(Usuario).filter(Usuario.email == EMAIL).first()

    if not user:
        print("❌ Usuario admin no encontrado")
        raise SystemExit(1)

    user.hashed_password = hash_password(NEW_PASSWORD)
    user.failed_login_attempts = 0
    user.blocked_until = None
    user.reset_token_hash = None
    user.reset_token_expires_at = None
    user.reset_token_used_at = None

    db.add(user)
    db.commit()
    db.refresh(user)

    print("✅ Password reseteado correctamente")
    print(f"email={user.email}")
    print("new_password=Admin123!")
finally:
    db.close()
PY

echo "======================================"
echo "FIN RESET"
echo "======================================"
