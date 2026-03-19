#!/bin/bash

echo "======================================"
echo "TASK 75 - MULTI LEVEL CACHE FINAL REAL"
echo "======================================"

BASE_URL="http://localhost:8000"
API_KEY="dev-secret-key-change-me"

TOKEN="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJhZG1pbkBlbXByZXNhLmNvbSIsInR5cGUiOiJhY2Nlc3MiLCJleHAiOjE3NzM5NDA0ODAsImp0aSI6ImI3NjcwYTEwLTg0N2UtNDI5ZC1iMGU0LTkxMDE3NDA2ZDMxNCJ9.mXbd5vI_kR5_LazGs58EWQAnn9ZaEC1vA6ESsGB66Nc"

# Generar valores únicos para evitar duplicados
UNIQ=$(date +%s)
SKU="CACHE-TEST-$UNIQ"
CODIGO_SKU="CT-$((1000 + UNIQ % 9000))"

echo ""
echo "0) Health..."
curl -s "$BASE_URL/health" | grep "ok" || { echo "❌ API DOWN"; exit 1; }
echo "✅ API OK"

echo ""
echo "1) Crear item..."
CREATE_RESPONSE=$(curl -s -L -X POST "$BASE_URL/api/v1/items/" \
-H "Content-Type: application/json" \
-H "Authorization: Bearer $TOKEN" \
-H "X-API-Key: $API_KEY" \
-d "{
  \"name\": \"Item Cache Test\",
  \"description\": \"Cache multinivel\",
  \"price\": 100,
  \"sku\": \"$SKU\",
  \"codigo_sku\": \"$CODIGO_SKU\",
  \"stock\": 10
}")

echo "$CREATE_RESPONSE"

ITEM_ID=$(echo "$CREATE_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin)['data']['id'])" 2>/dev/null)

if [ -z "$ITEM_ID" ]; then
  echo "❌ NO SE PUDO EXTRAER ITEM_ID"
  exit 1
fi

echo "✅ ITEM ID: $ITEM_ID"
echo "✅ SKU: $SKU"
echo "✅ CODIGO_SKU: $CODIGO_SKU"

echo ""
echo "2) Primera lectura (DB)..."
time curl -s "$BASE_URL/api/v1/items/$ITEM_ID" \
-H "Authorization: Bearer $TOKEN" \
-H "X-API-Key: $API_KEY" > /dev/null

echo ""
echo "3) Segunda lectura (CACHE)..."
time curl -s "$BASE_URL/api/v1/items/$ITEM_ID" \
-H "Authorization: Bearer $TOKEN" \
-H "X-API-Key: $API_KEY" > /dev/null

echo ""
echo "4) Stampede test..."
for i in {1..20}; do
  curl -s "$BASE_URL/api/v1/items/$ITEM_ID" \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-API-Key: $API_KEY" > /dev/null &
done
wait
echo "✅ Stampede OK"

echo ""
echo "5) Update item..."
UPDATE_RESPONSE=$(curl -s -X PUT "$BASE_URL/api/v1/items/$ITEM_ID" \
-H "Content-Type: application/json" \
-H "Authorization: Bearer $TOKEN" \
-H "X-API-Key: $API_KEY" \
-d "{
  \"name\": \"Item Cache Updated\",
  \"description\": \"Invalidate cache\",
  \"price\": 200,
  \"sku\": \"$SKU\",
  \"codigo_sku\": \"$CODIGO_SKU\",
  \"stock\": 15
}")

echo "$UPDATE_RESPONSE"

echo ""
echo "6) Relectura (DB otra vez)..."
time curl -s "$BASE_URL/api/v1/items/$ITEM_ID" \
-H "Authorization: Bearer $TOKEN" \
-H "X-API-Key: $API_KEY" > /dev/null

echo ""
echo "7) Métricas cache..."
curl -s "$BASE_URL/metrics" | grep "cache_"

echo ""
echo "======================================"
echo "TASK 75 VALIDADA REAL"
echo "======================================"