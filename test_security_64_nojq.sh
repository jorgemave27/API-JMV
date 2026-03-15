#!/bin/bash

BASE_URL="http://localhost:8000"
API_KEY="dev-secret-key-change-me"
EMAIL="admin@empresa.com"
PASSWORD="Admin123!"

echo "======================================"
echo "TASK 64 TEST SIN JQ"
echo "======================================"

echo ""
echo "1) Health"
curl -s "$BASE_URL/health"
echo ""
echo ""

echo "2) Login"
LOGIN_RESPONSE=$(curl -s -X POST "$BASE_URL/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\"}")

echo "$LOGIN_RESPONSE"

TOKEN=$(python3 - <<PY
import json
data=json.loads('''$LOGIN_RESPONSE''')
print(data.get("access_token",""))
PY
)

if [ -z "$TOKEN" ]; then
  echo ""
  echo "❌ No se pudo obtener access_token"
  exit 1
fi

echo ""
echo "TOKEN:"
echo "$TOKEN"

echo ""
echo "3) Probar sesiones con token válido"
curl -i -s "$BASE_URL/api/v1/auth/sesiones" \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-API-Key: $API_KEY"
echo ""
echo ""

echo "4) Logout"
curl -i -s -X POST "$BASE_URL/api/v1/auth/logout" \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-API-Key: $API_KEY"
echo ""
echo ""

echo "5) Reusar token revocado (debe fallar)"
curl -i -s "$BASE_URL/api/v1/auth/sesiones" \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-API-Key: $API_KEY"
echo ""
echo ""

echo "6) Login nuevo para sesión nueva"
LOGIN_RESPONSE_2=$(curl -s -X POST "$BASE_URL/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\"}")

echo "$LOGIN_RESPONSE_2"

TOKEN2=$(python3 - <<PY
import json
data=json.loads('''$LOGIN_RESPONSE_2''')
print(data.get("access_token",""))
PY
)

if [ -z "$TOKEN2" ]; then
  echo ""
  echo "❌ No se pudo obtener access_token del segundo login"
  exit 1
fi

echo ""
echo "TOKEN2:"
echo "$TOKEN2"

echo ""
echo "7) Listar sesiones"
SESSIONS_RESPONSE=$(curl -s "$BASE_URL/api/v1/auth/sesiones" \
  -H "Authorization: Bearer $TOKEN2" \
  -H "X-API-Key: $API_KEY")

echo "$SESSIONS_RESPONSE"

JTI=$(python3 - <<PY
import json
data=json.loads('''$SESSIONS_RESPONSE''')
items = data.get("data") or []
print(items[0].get("jti","") if items else "")
PY
)

echo ""
echo "JTI detectado:"
echo "$JTI"

if [ -z "$JTI" ]; then
  echo "❌ No se encontró jti en sesiones"
  exit 1
fi

echo ""
echo "8) Cerrar sesión remota"
curl -i -s -X POST "$BASE_URL/api/v1/auth/cerrar-sesion/$JTI" \
  -H "Authorization: Bearer $TOKEN2" \
  -H "X-API-Key: $API_KEY"
echo ""
echo ""

echo "9) Reusar token de sesión cerrada"
curl -i -s "$BASE_URL/api/v1/auth/sesiones" \
  -H "Authorization: Bearer $TOKEN2" \
  -H "X-API-Key: $API_KEY"
echo ""
echo ""

echo "10) Redis keys de seguridad"
REDIS_CONTAINER=$(docker ps --format '{{.Names}}' | grep redis | head -n 1)
if [ -n "$REDIS_CONTAINER" ]; then
  echo "Redis container: $REDIS_CONTAINER"
  docker exec -i "$REDIS_CONTAINER" redis-cli keys 'session:*'
  docker exec -i "$REDIS_CONTAINER" redis-cli keys 'blacklist:*'
else
  echo "⚠️ No se encontró contenedor Redis"
fi

echo ""
echo "======================================"
echo "FIN TEST TASK 64"
echo "======================================"
