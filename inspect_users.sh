#!/bin/bash

API_CONTAINER="api-jmv-api"

echo "======================================"
echo "INSPECT USERS"
echo "======================================"

docker exec -i "$API_CONTAINER" python - <<'PY'
from app.database.database import SessionLocal
from app.models.usuario import Usuario

db = SessionLocal()
try:
    users = db.query(Usuario).all()
    print(f"TOTAL_USUARIOS={len(users)}")
    for u in users:
        print(
            f"id={u.id} | email={u.email} | activo={u.activo} | rol={u.rol} | "
            f"failed_login_attempts={u.failed_login_attempts} | blocked_until={u.blocked_until}"
        )
finally:
    db.close()
PY

echo "======================================"
