#!/usr/bin/env bash
set -euo pipefail

# =====================================================
# CONFIGURACIÓN
# =====================================================

BASE_URL="${BASE_URL:-http://localhost:8000}"
API_KEY="${API_KEY:-dev-secret-key-change-me}"

# -----------------------------------------------------
# CREDENCIALES
# -----------------------------------------------------
USER_EMAIL="${USER_EMAIL:-admin@empresa.com}"
USER_PASSWORD="${USER_PASSWORD:-Admin123!}"

print_section() {
  echo ""
  echo "======================================================"
  echo "$1"
  echo "======================================================"
}

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "❌ Falta comando requerido: $1"
    exit 1
  fi
}

extract_json_field() {
  local field="$1"
  python3 -c "import sys, json; print(json.load(sys.stdin).get('$field', ''))"
}

extract_item_id() {
  python3 -c "import sys, json
raw = sys.stdin.read().strip()
try:
    data = json.loads(raw)
    print(data.get('data', {}).get('id', 1))
except Exception:
    print(1)
"
}

require_cmd curl
require_cmd python3

print_section "1) HEALTH CHECK"
curl -i "$BASE_URL/health"
echo ""

print_section "2) LOGIN"

LOGIN_RESPONSE=$(curl -sS -X POST "$BASE_URL/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d "{
    \"email\": \"$USER_EMAIL\",
    \"password\": \"$USER_PASSWORD\"
  }")

echo "$LOGIN_RESPONSE"
echo ""

TOKEN=$(printf '%s' "$LOGIN_RESPONSE" | extract_json_field "access_token")

if [[ -z "${TOKEN:-}" ]]; then
  echo "❌ No se pudo obtener access_token"
  exit 1
fi

export TOKEN

echo "✅ TOKEN obtenido correctamente"
echo ""

print_section "3) VALIDAR TOKEN EN /auth/sesiones"
curl -sS "$BASE_URL/api/v1/auth/sesiones" \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-API-Key: $API_KEY"
echo ""

print_section "4) CREAR ITEM DE PRUEBA"

UNIQUE_SUFFIX="$(date +%s)"
SKU="METRIC-${UNIQUE_SUFFIX}"
CODIGO_SKU="METRIC-${UNIQUE_SUFFIX}"

CREATE_RESPONSE=$(curl -sS -X POST "$BASE_URL/api/v1/items/" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -H "Authorization: Bearer $TOKEN" \
  -d "{
    \"name\": \"Item Metric Test $UNIQUE_SUFFIX\",
    \"description\": \"Prueba metricas task 68\",
    \"price\": 199.99,
    \"sku\": \"$SKU\",
    \"codigo_sku\": \"$CODIGO_SKU\",
    \"stock\": 10,
    \"categoria_id\": null
  }")

echo "$CREATE_RESPONSE"
echo ""

ITEM_ID=$(printf '%s' "$CREATE_RESPONSE" | extract_item_id)

echo "ITEM_ID: $ITEM_ID"

print_section "5) LEER ITEM"
curl -sS "$BASE_URL/api/v1/items/$ITEM_ID" \
  -H "X-API-Key: $API_KEY"
echo ""

print_section "6) LISTAR ITEMS"
curl -sS "$BASE_URL/api/v1/items/" \
  -H "X-API-Key: $API_KEY"
echo ""

print_section "7) BUSCAR ITEM POR NOMBRE"
curl -sS "$BASE_URL/api/v1/items/buscar?nombre=Item%20Metric%20Test%20$UNIQUE_SUFFIX" \
  -H "X-API-Key: $API_KEY"
echo ""

print_section "8) CURSOR PAGINATION"
curl -sS "$BASE_URL/api/v1/items/cursor?cursor=0&limite=5" \
  -H "X-API-Key: $API_KEY"
echo ""

print_section "9) MÉTRICAS CUSTOM"

echo "--- crud_operations_total ---"
curl -sS "$BASE_URL/metrics" | grep "crud_operations_total" || true
echo ""

echo "--- items_created_by_category_total ---"
curl -sS "$BASE_URL/metrics" | grep "items_created_by_category_total" || true
echo ""

echo "--- db_query_duration_seconds ---"
curl -sS "$BASE_URL/metrics" | grep "db_query_duration_seconds" || true
echo ""

print_section "10) VALIDACIÓN FINAL"
echo "Prometheus: http://localhost:9090/targets"
echo "Grafana:    http://localhost:3000"
echo "Kibana:     http://localhost:5601"
echo ""
echo "✅ Si ves samples reales en las 3 métricas, la instrumentación base de la 68 quedó bien."