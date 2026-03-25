#!/bin/bash

echo "======================================"
echo "TASK 84 - NOTIFICATIONS TEST"
echo "======================================"

BASE_URL="http://localhost:8000"
API_KEY="dev-secret-key-change-me-123456"

echo ""
echo "1) LOGIN REAL..."

LOGIN_RESPONSE=$(curl -s -X POST "$BASE_URL/api/v1/auth/login" \
-H "Content-Type: application/json" \
-d '{"email":"admin@empresa.com","password":"Admin123!"}')

echo "$LOGIN_RESPONSE"

TOKEN=$(echo "$LOGIN_RESPONSE" | sed -E 's/.*"access_token":"([^"]+)".*/\1/')

# 🔥 VALIDACIÓN REAL
if [[ "$LOGIN_RESPONSE" == *"Credenciales inválidas"* ]]; then
  echo ""
  echo "❌ ERROR: CREDENCIALES MALAS"
  echo "👉 El usuario NO existe o el password NO coincide"
  exit 1
fi

if [[ "$LOGIN_RESPONSE" == *"401"* ]] || [ -z "$TOKEN" ]; then
  echo ""
  echo "❌ ERROR: NO SE PUDO OBTENER TOKEN"
  exit 1
fi

echo "✅ TOKEN OK"

echo ""
echo "2) Crear item..."

CREATE_RESPONSE=$(curl -s -X POST "$BASE_URL/api/v1/items/" \
-H "Authorization: Bearer $TOKEN" \
-H "X-API-Key: $API_KEY" \
-H "Content-Type: application/json" \
-d "{
\"name\":\"Item Notif Test\",
\"price\":100,
\"stock\":10,
\"sku\":\"TEST-NOTIF-$(date +%s)\",
\"codigo_sku\":\"AB-1234\"
}")

echo "$CREATE_RESPONSE"

echo ""
echo "3) Crear item STOCK BAJO..."

CREATE_LOW=$(curl -s -X POST "$BASE_URL/api/v1/items/" \
-H "Authorization: Bearer $TOKEN" \
-H "X-API-Key: $API_KEY" \
-H "Content-Type: application/json" \
-d "{
\"name\":\"Item Low Stock\",
\"price\":50,
\"stock\":3,
\"sku\":\"LOW-$(date +%s)\",
\"codigo_sku\":\"CD-5678\"
}")

echo "$CREATE_LOW"

echo ""
echo "4) Esperando..."
sleep 3

echo ""
echo "5) Verificando notificaciones..."

curl -s "$BASE_URL/api/v1/admin/notificaciones" | jq

echo ""
echo "======================================"