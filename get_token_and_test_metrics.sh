#!/usr/bin/env bash
set -euo pipefail

# =====================================================
# CONFIG
# =====================================================

BASE_URL="${BASE_URL:-http://localhost:8000}"
API_KEY="${API_KEY:-dev-secret-key-change-me}"
LOGIN_URL="$BASE_URL/api/v1/auth/login"

# AJUSTA SI TUS CREDENCIALES SON OTRAS
USER_EMAIL="${USER_EMAIL:-admin@empresa.com}"
USER_PASSWORD="${USER_PASSWORD:-admin123}"

TOKEN=""

print_section() {
  echo ""
  echo "======================================================"
  echo "$1"
  echo "======================================================"
}

extract_token() {
  local raw="$1"
  python3 - <<'PY' "$raw"
import json, sys

raw = sys.argv[1]
try:
    data = json.loads(raw)
except Exception:
    print("")
    raise SystemExit(0)

paths = [
    ("access_token",),
    ("token",),
    ("data", "access_token"),
    ("data", "token"),
    ("data", "access"),
]

token = ""
for path in paths:
    cur = data
    ok = True
    for key in path:
        if isinstance(cur, dict) and key in cur:
            cur = cur[key]
        else:
            ok = False
            break
    if ok and isinstance(cur, str) and cur.strip():
        token = cur.strip()
        break

print(token)
PY
}

try_request() {
  local label="$1"
  local response="$2"

  echo ""
  echo ">>> $label"
  echo "$response"

  local maybe_token
  maybe_token="$(extract_token "$response")"

  if [[ -n "$maybe_token" ]]; then
    TOKEN="$maybe_token"
    return 0
  fi

  return 1
}

print_section "1) HEALTH"
curl -i "$BASE_URL/health" || true

print_section "2) LOGIN - PROBANDO FORMATOS"

# -----------------------------------------------------
# FORMATO 1: JSON email/password
# -----------------------------------------------------
RESP=$(curl -sS -X POST "$LOGIN_URL" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d "{
    \"email\": \"$USER_EMAIL\",
    \"password\": \"$USER_PASSWORD\"
  }" || true)

try_request "JSON email/password" "$RESP" || true

# -----------------------------------------------------
# FORMATO 2: JSON username/password
# -----------------------------------------------------
if [[ -z "$TOKEN" ]]; then
  RESP=$(curl -sS -X POST "$LOGIN_URL" \
    -H "Content-Type: application/json" \
    -H "X-API-Key: $API_KEY" \
    -d "{
      \"username\": \"$USER_EMAIL\",
      \"password\": \"$USER_PASSWORD\"
    }" || true)

  try_request "JSON username/password" "$RESP" || true
fi

# -----------------------------------------------------
# FORMATO 3: FORM username/password
# -----------------------------------------------------
if [[ -z "$TOKEN" ]]; then
  RESP=$(curl -sS -X POST "$LOGIN_URL" \
    -H "Content-Type: application/x-www-form-urlencoded" \
    -H "X-API-Key: $API_KEY" \
    --data "username=$USER_EMAIL&password=$USER_PASSWORD" || true)

  try_request "FORM username/password" "$RESP" || true
fi

# -----------------------------------------------------
# FORMATO 4: FORM email/password
# -----------------------------------------------------
if [[ -z "$TOKEN" ]]; then
  RESP=$(curl -sS -X POST "$LOGIN_URL" \
    -H "Content-Type: application/x-www-form-urlencoded" \
    -H "X-API-Key: $API_KEY" \
    --data "email=$USER_EMAIL&password=$USER_PASSWORD" || true)

  try_request "FORM email/password" "$RESP" || true
fi

# -----------------------------------------------------
# FORMATO 5: OAuth style grant_type=password
# -----------------------------------------------------
if [[ -z "$TOKEN" ]]; then
  RESP=$(curl -sS -X POST "$LOGIN_URL" \
    -H "Content-Type: application/x-www-form-urlencoded" \
    -H "X-API-Key: $API_KEY" \
    --data "grant_type=password&username=$USER_EMAIL&password=$USER_PASSWORD" || true)

  try_request "FORM OAuth password grant" "$RESP" || true
fi

# -----------------------------------------------------
# FORMATO 6: JSON con api_key en body
# -----------------------------------------------------
if [[ -z "$TOKEN" ]]; then
  RESP=$(curl -sS -X POST "$LOGIN_URL" \
    -H "Content-Type: application/json" \
    -d "{
      \"email\": \"$USER_EMAIL\",
      \"password\": \"$USER_PASSWORD\",
      \"api_key\": \"$API_KEY\"
    }" || true)

  try_request "JSON email/password + api_key body" "$RESP" || true
fi

# -----------------------------------------------------
# FORMATO 7: FORM + api_key en body
# -----------------------------------------------------
if [[ -z "$TOKEN" ]]; then
  RESP=$(curl -sS -X POST "$LOGIN_URL" \
    -H "Content-Type: application/x-www-form-urlencoded" \
    --data "username=$USER_EMAIL&password=$USER_PASSWORD&api_key=$API_KEY" || true)

  try_request "FORM username/password + api_key body" "$RESP" || true
fi

# =====================================================
# SI NO HAY TOKEN
# =====================================================
if [[ -z "$TOKEN" ]]; then
  print_section "NO SE PUDO OBTENER TOKEN"
  echo "Ahora sí necesito el archivo completo:"
  echo "sed -n '1,220p' app/api/v1/endpoints/auth.py"
  exit 1
fi

export TOKEN

print_section "3) TOKEN OBTENIDO"
echo "$TOKEN"

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

ITEM_ID=$(python3 - <<'PY' "$CREATE_RESPONSE"
import json, sys

raw = sys.argv[1]
try:
    data = json.loads(raw)
except Exception:
    print("1")
    raise SystemExit(0)

cur = data.get("data", {})
item_id = cur.get("id", 1) if isinstance(cur, dict) else 1
print(str(item_id))
PY
)

print_section "5) LEER ITEM"
curl -sS "$BASE_URL/api/v1/items/$ITEM_ID" \
  -H "X-API-Key: $API_KEY"

print_section "6) LISTAR ITEMS"
curl -sS "$BASE_URL/api/v1/items/" \
  -H "X-API-Key: $API_KEY"

print_section "7) MÉTRICAS CUSTOM"

echo "--- crud_operations_total ---"
curl -sS "$BASE_URL/metrics" | grep "crud_operations_total" || true
echo ""

echo "--- items_created_by_category_total ---"
curl -sS "$BASE_URL/metrics" | grep "items_created_by_category_total" || true
echo ""

echo "--- db_query_duration_seconds ---"
curl -sS "$BASE_URL/metrics" | grep "db_query_duration_seconds" || true
echo ""

print_section "8) URLS"
echo "Prometheus: http://localhost:9090/targets"
echo "Grafana:    http://localhost:3000"
echo "Kibana:     http://localhost:5601"