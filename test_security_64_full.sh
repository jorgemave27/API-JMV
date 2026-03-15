#!/bin/bash

BASE_URL="http://localhost:8000"
API_KEY="dev-secret-key-change-me"
EMAIL="admin@empresa.com"
PASSWORD="Admin123!"
NEW_PASSWORD="Admin1234!"

echo "======================================"
echo "TASK 64 FULL TEST"
echo "======================================"

extract_json_field() {
  local json="$1"
  local field="$2"
  python3 - <<PY
import json
data=json.loads('''$json''')
print(data.get("$field",""))
PY
}

extract_first_jti() {
  local json="$1"
  python3 - <<PY
import json
data=json.loads('''$json''')
items = data.get("data") or []
print(items[0].get("jti","") if items else "")
PY
}

echo ""
echo "1) Health"
curl -s "$BASE_URL/health"
echo ""
echo ""

echo "2) Login con password actual"
LOGIN1=$(curl -s -X POST "$BASE_URL/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\"}")
echo "$LOGIN1"
TOKEN1=$(extract_json_field "$LOGIN1" "access_token")

if [ -z "$TOKEN1" ]; then
  echo "❌ No se obtuvo TOKEN1"
  exit 1
fi

echo ""
echo "3) Probar sesiones con TOKEN1"
curl -i -s "$BASE_URL/api/v1/auth/sesiones" \
  -H "Authorization: Bearer $TOKEN1" \
  -H "X-API-Key: $API_KEY"
echo ""
echo ""

echo "4) Logout de TOKEN1"
curl -i -s -X POST "$BASE_URL/api/v1/auth/logout" \
  -H "Authorization: Bearer $TOKEN1" \
  -H "X-API-Key: $API_KEY"
echo ""
echo ""

echo "5) Reusar TOKEN1 revocado"
curl -i -s "$BASE_URL/api/v1/auth/sesiones" \
  -H "Authorization: Bearer $TOKEN1" \
  -H "X-API-Key: $API_KEY"
echo ""
echo ""

echo "6) Login nuevo para TOKEN2"
LOGIN2=$(curl -s -X POST "$BASE_URL/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\"}")
echo "$LOGIN2"
TOKEN2=$(extract_json_field "$LOGIN2" "access_token")

if [ -z "$TOKEN2" ]; then
  echo "❌ No se obtuvo TOKEN2"
  exit 1
fi

echo ""
echo "7) Listar sesiones con TOKEN2"
SESSIONS2=$(curl -s "$BASE_URL/api/v1/auth/sesiones" \
  -H "Authorization: Bearer $TOKEN2" \
  -H "X-API-Key: $API_KEY")
echo "$SESSIONS2"

JTI2=$(extract_first_jti "$SESSIONS2")
echo ""
echo "JTI2=$JTI2"

if [ -z "$JTI2" ]; then
  echo "❌ No se obtuvo JTI2"
  exit 1
fi

echo ""
echo "8) Cerrar sesión remota de TOKEN2"
curl -i -s -X POST "$BASE_URL/api/v1/auth/cerrar-sesion/$JTI2" \
  -H "Authorization: Bearer $TOKEN2" \
  -H "X-API-Key: $API_KEY"
echo ""
echo ""

echo "9) Reusar TOKEN2 tras cierre remoto"
curl -i -s "$BASE_URL/api/v1/auth/sesiones" \
  -H "Authorization: Bearer $TOKEN2" \
  -H "X-API-Key: $API_KEY"
echo ""
echo ""

echo "10) Login A para prueba de cambio de password"
LOGIN_A=$(curl -s -X POST "$BASE_URL/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\"}")
echo "$LOGIN_A"
TOKEN_A=$(extract_json_field "$LOGIN_A" "access_token")

echo ""
echo "11) Login B para prueba de cambio de password"
LOGIN_B=$(curl -s -X POST "$BASE_URL/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\"}")
echo "$LOGIN_B"
TOKEN_B=$(extract_json_field "$LOGIN_B" "access_token")

if [ -z "$TOKEN_A" ] || [ -z "$TOKEN_B" ]; then
  echo "❌ No se obtuvieron TOKEN_A o TOKEN_B"
  exit 1
fi

echo ""
echo "12) Cambiar password con TOKEN_A"
curl -i -s -X POST "$BASE_URL/api/v1/auth/cambiar-password" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN_A" \
  -H "X-API-Key: $API_KEY" \
  -d "{\"current_password\":\"$PASSWORD\",\"new_password\":\"$NEW_PASSWORD\"}"
echo ""
echo ""

echo "13) Reusar TOKEN_A tras cambio de password"
curl -i -s "$BASE_URL/api/v1/auth/sesiones" \
  -H "Authorization: Bearer $TOKEN_A" \
  -H "X-API-Key: $API_KEY"
echo ""
echo ""

echo "14) Reusar TOKEN_B tras cambio de password"
curl -i -s "$BASE_URL/api/v1/auth/sesiones" \
  -H "Authorization: Bearer $TOKEN_B" \
  -H "X-API-Key: $API_KEY"
echo ""
echo ""

echo "15) Login con nueva password"
LOGIN_NEW=$(curl -s -X POST "$BASE_URL/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$NEW_PASSWORD\"}")
echo "$LOGIN_NEW"
TOKEN_NEW=$(extract_json_field "$LOGIN_NEW" "access_token")

if [ -z "$TOKEN_NEW" ]; then
  echo "❌ No se pudo iniciar con nueva password"
  exit 1
fi

echo ""
echo "16) Sesiones con TOKEN_NEW"
curl -i -s "$BASE_URL/api/v1/auth/sesiones" \
  -H "Authorization: Bearer $TOKEN_NEW" \
  -H "X-API-Key: $API_KEY"
echo ""
echo ""

echo "17) Token theft detection"
echo "   17.1 Primera llamada"
curl -i -s "$BASE_URL/api/v1/auth/sesiones" \
  -H "Authorization: Bearer $TOKEN_NEW" \
  -H "X-API-Key: $API_KEY" \
  -H "X-Forwarded-For: 8.8.8.8"
echo ""
echo ""

echo "   17.2 Segunda llamada con otra IP"
curl -i -s "$BASE_URL/api/v1/auth/sesiones" \
  -H "Authorization: Bearer $TOKEN_NEW" \
  -H "X-API-Key: $API_KEY" \
  -H "X-Forwarded-For: 1.1.1.1"
echo ""
echo ""

echo "   17.3 Reusar token tras posible robo"
curl -i -s "$BASE_URL/api/v1/auth/sesiones" \
  -H "Authorization: Bearer $TOKEN_NEW" \
  -H "X-API-Key: $API_KEY"
echo ""
echo ""

echo "18) Logs recientes API"
docker logs --tail 80 api-jmv-api 2>&1 | grep -E "SECURITY_EVENT|posible_robo_token|Token revocado|Token revocado|revocado" || true
echo ""

echo "19) Redis keys"
REDIS_CONTAINER=$(docker ps --format '{{.Names}}' | grep redis | head -n 1)
if [ -n "$REDIS_CONTAINER" ]; then
  echo "Redis container: $REDIS_CONTAINER"
  docker exec -i "$REDIS_CONTAINER" redis-cli keys 'session:*'
  docker exec -i "$REDIS_CONTAINER" redis-cli keys 'blacklist:*'
  docker exec -i "$REDIS_CONTAINER" redis-cli keys 'security:*'
fi
echo ""

echo "20) Restaurar password original"
curl -i -s -X POST "$BASE_URL/api/v1/auth/cambiar-password" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN_NEW" \
  -H "X-API-Key: $API_KEY" \
  -d "{\"current_password\":\"$NEW_PASSWORD\",\"new_password\":\"$PASSWORD\"}"
echo ""
echo ""

echo "21) Verificar login con password original restaurado"
LOGIN_ORIG=$(curl -s -X POST "$BASE_URL/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\"}")
echo "$LOGIN_ORIG"

echo ""
echo "======================================"
echo "FIN TASK 64 FULL TEST"
echo "======================================"
