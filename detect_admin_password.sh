#!/bin/bash

BASE_URL="http://localhost:8000"
API_KEY="dev-secret-key-change-me"
EMAIL="admin@empresa.com"

echo "======================================"
echo "DETECTAR PASSWORD ACTUAL ADMIN"
echo "======================================"

for PASS in "Admin123!" "Admin1234!"; do
  echo ""
  echo "Probando: $PASS"
  RESP=$(curl -s -X POST "$BASE_URL/api/v1/auth/login" \
    -H "Content-Type: application/json" \
    -H "X-API-Key: $API_KEY" \
    -d "{\"email\":\"$EMAIL\",\"password\":\"$PASS\"}")

  echo "$RESP"

  TOKEN=$(python3 - <<PY
import json
raw = '''$RESP'''.strip()
try:
    data = json.loads(raw)
    print(data.get("access_token", ""))
except Exception:
    print("")
PY
)

  if [ -n "$TOKEN" ]; then
    echo ""
    echo "✅ PASSWORD VALIDA: $PASS"
    exit 0
  fi
done

echo ""
echo "❌ Ninguna de las dos passwords funcionó"
