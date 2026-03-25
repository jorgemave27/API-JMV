#!/bin/bash

echo "======================================"
echo "TASK 83 - VALIDACION S3 / MINIO (FIX)"
echo "======================================"

BASE_URL="http://localhost:8000"
API_KEY="dev-secret-key-change-me"

# ======================================================
# 1) LOGIN
# ======================================================
echo "1) Login..."

TOKEN=$(curl -s -X POST "$BASE_URL/api/v1/auth/login" \
-H "Content-Type: application/json" \
-d '{"email":"admin@empresa.com","password":"Admin123!"}' \
| sed -E 's/.*"access_token":"([^"]+)".*/\1/')

if [ -z "$TOKEN" ]; then
  echo "❌ ERROR: No se pudo obtener token"
  exit 1
fi

echo "✅ TOKEN OK"

# ======================================================
# 2) CREAR ITEM (🔥 USANDO TOKEN REAL)
# ======================================================
echo "2) Crear item..."

SKU="S3-TEST-$(date +%s)"

CREATE_RESPONSE=$(curl -s -X POST "$BASE_URL/api/v1/items/" \
-H "Authorization: Bearer $TOKEN" \
-H "X-API-Key: $API_KEY" \
-H "Content-Type: application/json" \
-d "{
\"name\":\"Item Test S3\",
\"price\":100,
\"stock\":10,
\"sku\":\"$SKU\",
\"codigo_sku\":\"AB-1234\"
}")

echo "$CREATE_RESPONSE"

ITEM_ID=$(echo "$CREATE_RESPONSE" | sed -E 's/.*"id":([0-9]+).*/\1/')

if [[ "$ITEM_ID" == "$CREATE_RESPONSE" ]]; then
  echo "❌ ERROR: No se pudo crear item"
  exit 1
fi

echo "✅ ITEM_ID=$ITEM_ID"

# ======================================================
# 3) SUBIR IMAGEN (🔥 multipart correcto)
# ======================================================
echo "3) Subir imagen..."

UPLOAD_RESPONSE=$(curl -s -X POST "$BASE_URL/api/v1/items/$ITEM_ID/imagen" \
-H "Authorization: Bearer $TOKEN" \
-H "X-API-Key: $API_KEY" \
-F "file=@test.jpg")

echo "$UPLOAD_RESPONSE"

# ======================================================
# 4) OBTENER ITEM
# ======================================================
echo "4) Obtener item..."

GET_RESPONSE=$(curl -s -X GET "$BASE_URL/api/v1/items/$ITEM_ID" \
-H "Authorization: Bearer $TOKEN" \
-H "X-API-Key: $API_KEY")

echo "$GET_RESPONSE"

# ======================================================
# 5) VALIDAR imagen_url
# ======================================================
echo "5) Validar imagen_url..."

echo "$GET_RESPONSE" | grep "imagen_url" > /dev/null

if [ $? -eq 0 ]; then
  echo "✅ imagen_url OK"
else
  echo "❌ ERROR: No viene imagen_url"
fi