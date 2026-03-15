#!/bin/bash

BASE_URL="http://localhost:8000"
API_KEY="dev-secret-key-change-me"
EMAIL="admin@empresa.com"
PASSWORD="Admin123!"

echo "======================================"
echo "FINAL VALIDATION TASK 64"
echo "======================================"

echo ""
echo "1) Limpiando llaves de seguridad Redis..."

REDIS_CONTAINER=$(docker ps --format '{{.Names}}' | grep redis | head -n 1)

if [ -z "$REDIS_CONTAINER" ]; then
  echo "❌ Redis no encontrado"
  exit 1
fi

for pattern in 'session:*' 'blacklist:*' 'security:*'; do
  docker exec -i "$REDIS_CONTAINER" redis-cli --scan --pattern "$pattern" | while read key; do
    [ -n "$key" ] && docker exec -i "$REDIS_CONTAINER" redis-cli del "$key" >/dev/null
  done
done

echo "✅ Redis limpio"

echo ""
echo "2) Health check"
curl -s "$BASE_URL/health"
echo ""

echo ""
echo "3) Login test"
LOGIN=$(curl -s -X POST "$BASE_URL/api/v1/auth/login" \
-H "Content-Type: application/json" \
-H "X-API-Key: $API_KEY" \
-d "{\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\"}")

echo "$LOGIN"

TOKEN=$(python3 - <<PY
import json
raw='''$LOGIN'''
try:
 data=json.loads(raw)
 print(data.get("access_token",""))
except:
 print("")
PY
)

if [ -z "$TOKEN" ]; then
 echo "❌ Login falló"
 exit 1
fi

echo ""
echo "✅ Login OK"
echo ""

echo ""
echo "4) Test endpoint protegido"
curl -i "$BASE_URL/api/v1/auth/sesiones" \
-H "Authorization: Bearer $TOKEN" \
-H "X-API-Key: $API_KEY"

echo ""
echo ""
echo "======================================"
echo "TASK 64 READY"
echo "======================================"
