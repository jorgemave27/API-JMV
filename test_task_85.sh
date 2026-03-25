#!/bin/bash

# ==========================================================
# TASK 85 - STRIPE PAYMENTS E2E FULL TEST
# ==========================================================

set -e

BASE_URL="http://localhost:8000"
API_KEY=$(grep '^API_KEY=' .env.development | cut -d '=' -f2-)
DB_FILE="database.db"

echo "======================================"
echo "TASK 85 - STRIPE PAYMENTS FULL E2E"
echo "======================================"
echo ""

echo "0) VALIDANDO API..."
curl -s "$BASE_URL/health"
echo ""
echo ""

echo "0.1) VALIDANDO DB..."
if [[ ! -f "$DB_FILE" ]]; then
  echo "❌ No existe $DB_FILE"
  exit 1
fi
echo "✅ DB encontrada"

echo ""
echo "0.2) VALIDANDO ITEM ID=1..."
ITEM_RESPONSE=$(curl -s -X GET "$BASE_URL/api/v1/items/1" \
  -H "X-API-Key: $API_KEY" || true)

echo "$ITEM_RESPONSE"

if ! echo "$ITEM_RESPONSE" | grep -qi '"success":true'; then
  echo "❌ Item 1 no válido"
  exit 1
fi
echo "✅ Item OK"

echo ""
echo "1) LOGIN..."
LOGIN_RESPONSE=$(curl -s -X POST "$BASE_URL/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@empresa.com","password":"Admin123!"}')

echo "$LOGIN_RESPONSE"

TOKEN=$(echo "$LOGIN_RESPONSE" | sed -n 's/.*"access_token":"\([^"]*\)".*/\1/p')

if [[ -z "$TOKEN" ]]; then
  echo "❌ ERROR TOKEN"
  exit 1
fi

echo "✅ TOKEN OK"
echo "TOKEN=${TOKEN:0:40}..."

echo ""
echo "2) CREANDO PEDIDO DIRECTO EN SQLITE..."
SAGA_ID="saga-$(date +%s)"
NOW=$(date +"%Y-%m-%d %H:%M:%S")

sqlite3 "$DB_FILE" <<SQL
INSERT INTO pedidos (
  saga_id,
  usuario_id,
  item_id,
  cantidad,
  monto_total,
  email_cliente,
  estado,
  created_at,
  updated_at
) VALUES (
  '$SAGA_ID',
  1,
  1,
  1,
  100.0,
  'cliente@correo.com',
  'PENDIENTE',
  '$NOW',
  '$NOW'
);
SQL

PEDIDO_ID=$(sqlite3 "$DB_FILE" "SELECT id FROM pedidos WHERE saga_id='$SAGA_ID' LIMIT 1;")

if [[ -z "$PEDIDO_ID" ]]; then
  echo "❌ ERROR CREANDO PEDIDO"
  exit 1
fi

echo "✅ Pedido ID=$PEDIDO_ID"

echo ""
echo "3) CREANDO PAGO..."
PAGO_RESPONSE=$(curl -s -X POST "$BASE_URL/api/v1/pagos/crear?pedido_id=$PEDIDO_ID" \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-API-Key: $API_KEY")

echo "$PAGO_RESPONSE"

PAGO_ID=$(echo "$PAGO_RESPONSE" | sed -n 's/.*"pago_id":\([0-9][0-9]*\).*/\1/p')
PAYMENT_INTENT_ID=$(echo "$PAGO_RESPONSE" | sed -n 's/.*"payment_intent_id":"\([^"]*\)".*/\1/p')

if [[ -z "$PAGO_ID" ]]; then
  echo "❌ ERROR PAGO"
  exit 1
fi

echo "✅ Pago ID=$PAGO_ID"
echo "✅ PaymentIntent ID=$PAYMENT_INTENT_ID"

echo ""
echo "4) CONFIRMANDO EL MISMO PAGO EN TEST MODE..."
CONFIRM_RESPONSE=$(curl -s -X POST "$BASE_URL/api/v1/pagos/$PAGO_ID/confirm-test" \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-API-Key: $API_KEY")

echo "$CONFIRM_RESPONSE"

echo ""
echo "5) ESPERANDO WEBHOOK..."
sleep 4

echo ""
echo "6) SINCRONIZANDO DESDE STRIPE POR SI EL WEBHOOK TARDA..."
SYNC_RESPONSE=$(curl -s -X POST "$BASE_URL/api/v1/pagos/$PAGO_ID/sync" \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-API-Key: $API_KEY")

echo "$SYNC_RESPONSE"

echo ""
echo "7) RESULTADO FINAL EN DB..."

echo ""
echo "TABLA pagos:"
sqlite3 "$DB_FILE" <<SQL
.headers on
.mode column
SELECT id, pedido_id, stripe_payment_intent_id, estado, created_at, updated_at
FROM pagos
ORDER BY id DESC
LIMIT 10;
SQL

echo ""
echo "TABLA pedidos:"
sqlite3 "$DB_FILE" <<SQL
.headers on
.mode column
SELECT id, saga_id, estado, created_at, updated_at
FROM pedidos
ORDER BY id DESC
LIMIT 10;
SQL

PAGO_ESTADO=$(sqlite3 "$DB_FILE" "SELECT estado FROM pagos WHERE id=$PAGO_ID LIMIT 1;")
PEDIDO_ESTADO=$(sqlite3 "$DB_FILE" "SELECT estado FROM pedidos WHERE id=$PEDIDO_ID LIMIT 1;")

echo ""
echo "8) VALIDACIÓN FINAL..."
echo "PAGO_ESTADO=$PAGO_ESTADO"
echo "PEDIDO_ESTADO=$PEDIDO_ESTADO"

if [[ "$PAGO_ESTADO" == "pagado" && "$PEDIDO_ESTADO" == "CONFIRMADO" ]]; then
  echo "✅ TASK 85 VALIDADA AL 100%"
  exit 0
fi

echo "❌ TASK 85 NO QUEDÓ AL 100%"
exit 1