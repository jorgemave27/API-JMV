#!/bin/bash

echo "==============================="
echo "API-JMV SECURITY TEST - TASK 64"
echo "==============================="

BASE_URL="http://localhost:8000"
API_KEY="dev-secret-key-change-me"

EMAIL="admin@empresa.com"
PASSWORD="Admin123!"

echo ""
echo "1️⃣ Health check"
curl -s $BASE_URL/health
echo ""

echo ""
echo "2️⃣ Login"
LOGIN_RESPONSE=$(curl -s -X POST "$BASE_URL/api/v1/auth/login" \
-H "Content-Type: application/json" \
-H "X-API-Key: $API_KEY" \
-d "{
\"email\":\"$EMAIL\",
\"password\":\"$PASSWORD\"
}")

echo $LOGIN_RESPONSE

TOKEN=$(echo $LOGIN_RESPONSE | jq -r '.access_token')

if [ "$TOKEN" = "null" ]; then
  echo "❌ LOGIN FALLÓ"
  exit 1
fi

echo ""
echo "TOKEN OBTENIDO:"
echo $TOKEN

echo ""
echo "3️⃣ Probar endpoint protegido"

curl -i $BASE_URL/api/v1/auth/sesiones \
-H "Authorization: Bearer $TOKEN" \
-H "X-API-Key: $API_KEY"

echo ""
echo "4️⃣ Logout (blacklist token)"

curl -s -X POST $BASE_URL/api/v1/auth/logout \
-H "Authorization: Bearer $TOKEN" \
-H "X-API-Key: $API_KEY"

echo ""

echo ""
echo "5️⃣ Intentar usar token revocado"

curl -i $BASE_URL/api/v1/auth/sesiones \
-H "Authorization: Bearer $TOKEN" \
-H "X-API-Key: $API_KEY"

echo ""

echo ""
echo "6️⃣ Login otra vez para nuevas sesiones"

LOGIN_RESPONSE2=$(curl -s -X POST "$BASE_URL/api/v1/auth/login" \
-H "Content-Type: application/json" \
-H "X-API-Key: $API_KEY" \
-d "{
\"email\":\"$EMAIL\",
\"password\":\"$PASSWORD\"
}")

TOKEN2=$(echo $LOGIN_RESPONSE2 | jq -r '.access_token')

echo ""
echo "TOKEN2:"
echo $TOKEN2

echo ""
echo "7️⃣ Listar sesiones"

SESSIONS=$(curl -s $BASE_URL/api/v1/auth/sesiones \
-H "Authorization: Bearer $TOKEN2" \
-H "X-API-Key: $API_KEY")

echo $SESSIONS

JTI=$(echo $SESSIONS | jq -r '.data[0].jti')

echo ""
echo "JTI detectado:"
echo $JTI

echo ""
echo "8️⃣ Cerrar sesión remota"

curl -s -X POST $BASE_URL/api/v1/auth/cerrar-sesion/$JTI \
-H "Authorization: Bearer $TOKEN2" \
-H "X-API-Key: $API_KEY"

echo ""

echo ""
echo "9️⃣ Verificar sesión cerrada"

curl -i $BASE_URL/api/v1/auth/sesiones \
-H "Authorization: Bearer $TOKEN2" \
-H "X-API-Key: $API_KEY"

echo ""

echo ""
echo "🔟 Probar detección de robo de token"

curl -s $BASE_URL/api/v1/auth/sesiones \
-H "Authorization: Bearer $TOKEN2" \
-H "X-API-Key: $API_KEY" \
-H "X-Forwarded-For: 8.8.8.8"

curl -s $BASE_URL/api/v1/auth/sesiones \
-H "Authorization: Bearer $TOKEN2" \
-H "X-API-Key: $API_KEY" \
-H "X-Forwarded-For: 1.1.1.1"

echo ""
echo "==============================="
echo "FIN DE PRUEBAS TASK 64"
echo "==============================="

