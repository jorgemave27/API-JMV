#!/usr/bin/env bash
set -euo pipefail

# ==========================================================
# TASK 79 - ELASTICSEARCH FULL-TEXT SEARCH
# ==========================================================
# Valida:
# 1) Elasticsearch levantado
# 2) Índice items existente
# 3) Login y token
# 4) Creación de item
# 5) Búsqueda full-text exacta
# 6) Búsqueda fuzzy
# 7) Suggest/autocomplete
# 8) Update sync con Elasticsearch
# 9) Popularidad / consultas_count
# 10) Delete sync con Elasticsearch
# ==========================================================

BASE_URL="${BASE_URL:-http://localhost:8000}"
ES_URL="${ES_URL:-http://localhost:9200}"
API_PREFIX="${API_PREFIX:-/api/v1}"
ITEMS_URL="${BASE_URL}${API_PREFIX}/items"
LOGIN_URL="${BASE_URL}${API_PREFIX}/auth/login"
API_KEY="${API_KEY:-dev-secret-key-change-me}"

ADMIN_EMAIL="${ADMIN_EMAIL:-admin@empresa.com}"
ADMIN_PASSWORD="${ADMIN_PASSWORD:-Admin123!}"

RUN_ID="$(date +%s)"

TEST_NAME="Laptop Gamer Pro ${RUN_ID}"
TEST_DESC="Laptop de alta gama para gaming y edición de video"
TEST_PRICE="25999.90"
TEST_SKU="SKU-ES-TEST-${RUN_ID}"
TEST_CODIGO_SKU="ES-${RUN_ID: -4}"
TEST_STOCK="12"

UPDATED_NAME="Laptop Gamer Ultra ${RUN_ID}"
UPDATED_DESC="Laptop premium actualizada con mejor GPU"
UPDATED_PRICE="28999.50"
UPDATED_SKU="SKU-ES-TEST-${RUN_ID}"
UPDATED_CODIGO_SKU="ES-${RUN_ID: -4}"
UPDATED_STOCK="8"

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

ITEM_CREATE_JSON="$TMP_DIR/item_create.json"
ITEM_UPDATE_JSON="$TMP_DIR/item_update.json"
LOGIN_RESPONSE="$TMP_DIR/login_response.json"
CREATE_RESPONSE="$TMP_DIR/create_response.json"
SEARCH_RESPONSE="$TMP_DIR/search_response.json"
FUZZY_RESPONSE="$TMP_DIR/fuzzy_response.json"
SUGGEST_RESPONSE="$TMP_DIR/suggest_response.json"
GET_RESPONSE="$TMP_DIR/get_response.json"
UPDATE_RESPONSE="$TMP_DIR/update_response.json"
DELETE_RESPONSE="$TMP_DIR/delete_response.json"
ES_DOC_RESPONSE="$TMP_DIR/es_doc_response.json"
ES_SEARCH_AFTER_DELETE="$TMP_DIR/es_search_after_delete.json"

cat > "$ITEM_CREATE_JSON" <<EOF
{
  "name": "$TEST_NAME",
  "description": "$TEST_DESC",
  "price": $TEST_PRICE,
  "sku": "$TEST_SKU",
  "codigo_sku": "$TEST_CODIGO_SKU",
  "stock": $TEST_STOCK,
  "categoria_id": null
}
EOF

cat > "$ITEM_UPDATE_JSON" <<EOF
{
  "name": "$UPDATED_NAME",
  "description": "$UPDATED_DESC",
  "price": $UPDATED_PRICE,
  "sku": "$UPDATED_SKU",
  "codigo_sku": "$UPDATED_CODIGO_SKU",
  "stock": $UPDATED_STOCK,
  "categoria_id": null
}
EOF

print_header() {
  echo ""
  echo "=================================================="
  echo "$1"
  echo "=================================================="
}

assert_contains() {
  local file="$1"
  local pattern="$2"
  local message="$3"

  if grep -q "$pattern" "$file"; then
    echo "✅ $message"
  else
    echo "❌ $message"
    echo "---- contenido ----"
    cat "$file" || true
    echo ""
    exit 1
  fi
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "❌ Falta comando requerido: $1"
    exit 1
  }
}

require_cmd curl
require_cmd jq

print_header "TASK 79 - VALIDACION ELASTICSEARCH"

echo "BASE_URL=$BASE_URL"
echo "ES_URL=$ES_URL"
echo "ITEMS_URL=$ITEMS_URL"

# ==========================================================
# 0) Health Elasticsearch
# ==========================================================
print_header "0) Elasticsearch arriba"

curl -fsS "$ES_URL" > "$TMP_DIR/es_root.json"
echo "✅ Elasticsearch responde"

# ==========================================================
# 1) Verificar índice items
# ==========================================================
print_header "1) Verificar indice items"

if curl -fsS "$ES_URL/items" > "$TMP_DIR/index_items.json"; then
  echo "✅ Índice 'items' existe"
else
  echo "❌ El índice 'items' no existe o no responde"
  echo "Tip: asegúrate de ejecutar create_index() en startup"
  exit 1
fi

# ==========================================================
# 2) Login y token
# ==========================================================
print_header "2) Login y token"

curl -fsS -X POST "$LOGIN_URL" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"$ADMIN_EMAIL\",\"password\":\"$ADMIN_PASSWORD\"}" \
  > "$LOGIN_RESPONSE"

TOKEN="$(jq -r '.access_token // .data.access_token // empty' "$LOGIN_RESPONSE")"

if [[ -z "${TOKEN:-}" || "$TOKEN" == "null" ]]; then
  echo "❌ No se pudo obtener access_token"
  echo "Respuesta login:"
  cat "$LOGIN_RESPONSE"
  echo ""
  exit 1
fi

echo "✅ Token obtenido"

# ==========================================================
# 3) Crear item
# ==========================================================
print_header "3) Crear item"

curl -fsS -X POST "$ITEMS_URL/" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -H "Authorization: Bearer $TOKEN" \
  -d @"$ITEM_CREATE_JSON" \
  > "$CREATE_RESPONSE"

assert_contains "$CREATE_RESPONSE" "\"success\":true" "Creación de item OK"

ITEM_ID="$(jq -r '.data.id // .data.item_id // empty' "$CREATE_RESPONSE")"

if [[ -z "${ITEM_ID:-}" || "$ITEM_ID" == "null" ]]; then
  echo "❌ No se pudo extraer item_id de la respuesta de creación"
  cat "$CREATE_RESPONSE"
  echo ""
  exit 1
fi

echo "✅ Item creado con ID=$ITEM_ID"

# Dar tiempo corto si hiciera falta, aunque refresh=true debería bastar
sleep 1

# ==========================================================
# 4) Buscar exacto en Elasticsearch vía API
# ==========================================================
print_header "4) Buscar exacto"

curl -fsS "$ITEMS_URL/buscar?q=Laptop" \
  -H "X-API-Key: $API_KEY" \
  > "$SEARCH_RESPONSE"

assert_contains "$SEARCH_RESPONSE" "\"success\":true" "Búsqueda exacta responde OK"
assert_contains "$SEARCH_RESPONSE" "Laptop" "Búsqueda exacta encuentra resultados"

# ==========================================================
# 5) Buscar fuzzy
# ==========================================================
print_header "5) Buscar fuzzy"

curl -fsS "$ITEMS_URL/buscar?q=laptp" \
  -H "X-API-Key: $API_KEY" \
  > "$FUZZY_RESPONSE"

assert_contains "$FUZZY_RESPONSE" "\"success\":true" "Búsqueda fuzzy responde OK"
assert_contains "$FUZZY_RESPONSE" "Laptop" "Búsqueda fuzzy encuentra Laptop"

# ==========================================================
# 6) Suggest / autocomplete
# ==========================================================
print_header "6) Suggest"

curl -fsS "$ITEMS_URL/sugerir?q=Lap" \
  -H "X-API-Key: $API_KEY" \
  > "$SUGGEST_RESPONSE"

assert_contains "$SUGGEST_RESPONSE" "\"success\":true" "Suggester responde OK"
assert_contains "$SUGGEST_RESPONSE" "Laptop" "Suggester devuelve Laptop"

# ==========================================================
# 7) Obtener item por ID (incrementa popularidad)
# ==========================================================
print_header "7) Obtener item por ID y aumentar popularidad"

for i in 1 2 3; do
  curl -fsS "$ITEMS_URL/$ITEM_ID" \
    -H "X-API-Key: $API_KEY" \
    -H "Authorization: Bearer $TOKEN" \
    > "$GET_RESPONSE"
done

assert_contains "$GET_RESPONSE" "\"success\":true" "GET item por ID OK"

# Verificar documento en ES y consultas_count
curl -fsS "$ES_URL/items/_doc/$ITEM_ID" > "$ES_DOC_RESPONSE"
assert_contains "$ES_DOC_RESPONSE" "\"found\":true" "Documento existe en Elasticsearch"

CONSULTAS_COUNT="$(jq -r '._source.consultas_count // 0' "$ES_DOC_RESPONSE")"
echo "consultas_count=$CONSULTAS_COUNT"

if [[ "$CONSULTAS_COUNT" -ge 1 ]]; then
  echo "✅ Popularidad incrementada"
else
  echo "❌ consultas_count no incrementó"
  cat "$ES_DOC_RESPONSE"
  echo ""
  exit 1
fi

# ==========================================================
# 8) Actualizar item
# ==========================================================
print_header "8) Actualizar item"

curl -fsS -X PUT "$ITEMS_URL/$ITEM_ID" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -H "Authorization: Bearer $TOKEN" \
  -d @"$ITEM_UPDATE_JSON" \
  > "$UPDATE_RESPONSE"

assert_contains "$UPDATE_RESPONSE" "\"success\":true" "Update item OK"

sleep 1

curl -fsS "$ES_URL/items/_doc/$ITEM_ID" > "$ES_DOC_RESPONSE"
assert_contains "$ES_DOC_RESPONSE" "$UPDATED_NAME" "Elasticsearch refleja update de nombre"
assert_contains "$ES_DOC_RESPONSE" "$UPDATED_DESC" "Elasticsearch refleja update de descripción"

# ==========================================================
# 9) Buscar nombre actualizado
# ==========================================================
print_header "9) Buscar nombre actualizado"

curl -fsS "$ITEMS_URL/buscar?q=Ultra" \
  -H "X-API-Key: $API_KEY" \
  > "$SEARCH_RESPONSE"

assert_contains "$SEARCH_RESPONSE" "\"success\":true" "Búsqueda del nombre actualizado OK"
assert_contains "$SEARCH_RESPONSE" "Ultra" "Búsqueda encuentra nombre actualizado"

# ==========================================================
# 10) Eliminar item
# ==========================================================
print_header "10) Eliminar item"

curl -fsS -X DELETE "$ITEMS_URL/$ITEM_ID" \
  -H "X-API-Key: $API_KEY" \
  -H "Authorization: Bearer $TOKEN" \
  > "$DELETE_RESPONSE"

assert_contains "$DELETE_RESPONSE" "\"success\":true" "Delete item OK"

sleep 1

# Verificar que ya no esté en Elasticsearch
HTTP_CODE="$(curl -s -o "$TMP_DIR/es_delete_check.json" -w "%{http_code}" "$ES_URL/items/_doc/$ITEM_ID")"
if [[ "$HTTP_CODE" == "404" ]]; then
  echo "✅ Documento eliminado de Elasticsearch"
else
  FOUND_VALUE="$(jq -r '.found // "unknown"' "$TMP_DIR/es_delete_check.json" 2>/dev/null || echo "unknown")"
  if [[ "$FOUND_VALUE" == "false" ]]; then
    echo "✅ Documento ya no existe en Elasticsearch"
  else
    echo "❌ Documento sigue existiendo en Elasticsearch"
    cat "$TMP_DIR/es_delete_check.json" || true
    echo ""
    exit 1
  fi
fi

# Búsqueda post-delete
curl -fsS "$ITEMS_URL/buscar?q=Ultra" \
  -H "X-API-Key: $API_KEY" \
  > "$ES_SEARCH_AFTER_DELETE"

if grep -q "\"id\":$ITEM_ID" "$ES_SEARCH_AFTER_DELETE"; then
  echo "❌ El item eliminado sigue apareciendo en la búsqueda"
  cat "$ES_SEARCH_AFTER_DELETE"
  echo ""
  exit 1
else
  echo "✅ El item eliminado ya no aparece en la búsqueda"
fi

print_header "RESULTADO FINAL"
echo "✅ TASK 79 VALIDADA CORRECTAMENTE"
echo "✅ Elasticsearch index/create/update/delete/search/suggest funcionando"
echo "✅ Popularidad funcionando"
echo "✅ Fuzzy search funcionando"
echo ""
echo "Ya podrías hacer commit si todo esto pasó en verde."