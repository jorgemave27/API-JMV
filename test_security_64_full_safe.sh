#!/bin/bash

BASE_URL="http://localhost:8000"
API_KEY="dev-secret-key-change-me"
EMAIL="admin@empresa.com"
PASSWORD="Admin123!"
NEW_PASSWORD="Admin1234!"

echo "======================================"
echo "TASK 64 FULL TEST SAFE"
echo "======================================"

extract_json_field() {
  local json="$1"
  local field="$2"
  python3 - <<PY
import json
raw = '''$json'''.strip()
if not raw:
    print("")
else:
    try:
        data=json.loads(raw)
        print(data.get("$field",""))
    except Exception:
        print("")
PY
}

extract_first_jti() {
  local json="$1"
  python3 - <<PY
import json
raw = '''$json'''.strip()
if not raw:
    print("")
else:
    try:
        data=json.loads(raw)
        items = data.get("data") or []
        print(items[0].get("jti","") if items else "")
    except Exception:
        print("")
PY
}

echo ""
echo "1) Health"
HEALTH=$(curl -s "$BASE_URL/health")
echo "$HEALTH"
if [ -z "$HEALTH" ]; then
  echo "❌ Health vacío. Revisa contenedor API."
  exit 1
fi

echo ""
echo "2) Login con password actual"
LOGIN1=$(curl -s -X POST "$BASE_URL/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\"}")
echo "$LOGIN1"

TOKEN1=$(extract_json_field "$LOGIN1" "access_token")

if [ -z "$TOKEN1" ]; then
  echo "❌ No se obtuvo TOKEN1. La respuesta de login no fue JSON válido."
  exit 1
fi

echo ""
echo "TOKEN1 OK"
