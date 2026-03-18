#!/usr/bin/env bash
set -euo pipefail

echo "======================================"
echo "TASK 71 - PROFILING Y PERFORMANCE"
echo "======================================"
echo ""

BASE_URL="${BASE_URL:-http://localhost:8000}"
API_KEY="${API_KEY:-dev-secret-key-change-me}"
TOKEN="${TOKEN:-}"
PROFILE_PATH="${PROFILE_PATH:-/api/v1/items?page=1&page_size=10}"

if [ -z "$TOKEN" ]; then
  echo "❌ Falta TOKEN"
  echo "Ejecuta:"
  echo "export TOKEN='tu_access_token'"
  exit 1
fi

echo "1) Verificando dependencias dev..."
python - <<'PY'
mods = ["pyinstrument", "memory_profiler", "line_profiler"]
missing = []

for mod in mods:
    try:
        __import__(mod)
    except Exception:
        missing.append(mod)

if missing:
    print("Faltan dependencias:", ", ".join(missing))
    raise SystemExit(1)

print("✅ Dependencias dev OK")
PY
echo ""

echo "2) Verificando carpeta profiles..."
mkdir -p profiles
test -d profiles
echo "✅ profiles OK"
echo ""

echo "3) Health..."
curl -fsS "$BASE_URL/health" > /dev/null
echo "✅ health OK"
echo ""

echo "4) Auth sesiones..."
curl -fsS "$BASE_URL/api/v1/auth/sesiones" \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-API-Key: $API_KEY" > /dev/null
echo "✅ auth/sesiones OK"
echo ""

echo "5) Items..."
curl -fsS "$BASE_URL/api/v1/items?page=1&page_size=5" \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-API-Key: $API_KEY" > /dev/null
echo "✅ /api/v1/items OK"
echo ""

echo "6) Profiling manual..."
HTTP_CODE=$(curl -s -o /tmp/task71_profile.html -w "%{http_code}" \
  "$BASE_URL/api/v1/admin/profile?path=$PROFILE_PATH" \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-API-Key: $API_KEY")

if [ "$HTTP_CODE" != "200" ]; then
  echo "❌ Profiling manual falló. HTTP $HTTP_CODE"
  cat /tmp/task71_profile.html
  exit 1
fi

grep -qi "Profiling Report" /tmp/task71_profile.html
echo "✅ Profiling manual OK"
echo ""

echo "7) Forzando requests lentas..."
for i in 1 2 3 4 5; do
  curl -s "$BASE_URL/api/v1/items?page=1&page_size=100" \
    -H "Authorization: Bearer $TOKEN" \
    -H "X-API-Key: $API_KEY" > /dev/null || true
done
echo "✅ Requests ejecutadas"
echo ""

echo "8) Reportes generados..."
ls -lah profiles || true
COUNT=$(find profiles -type f \( -name "*.html" -o -name "*.svg" \) | wc -l | tr -d ' ')
echo "Reportes encontrados: $COUNT"
echo ""

echo "9) PERFORMANCE.md..."
test -f PERFORMANCE.md
echo "✅ PERFORMANCE.md existe"
echo ""

echo "10) Sintaxis..."
python -m py_compile \
  app/api/v1/endpoints/admin_profile.py \
  app/middlewares/request_logging.py \
  app/middlewares/auto_profiler.py \
  app/performance/auto_profiler.py \
  app/main.py
echo "✅ Sintaxis OK"
echo ""

echo "======================================"
echo "TASK 71 VALIDATION COMPLETED"
echo "======================================"
echo "✅ Tarea 71 validada"