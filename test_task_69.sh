#!/bin/bash

set -e  # rompe si algo falla

echo "======================================"
echo "TASK 69 - ADMIN SCRIPTS"
echo "======================================"

echo ""
echo "🔧 Detectando entorno..."

# Detectar si Redis está en Docker o local
if nc -z localhost 6379; then
  export REDIS_URL="redis://localhost:6379/0"
  echo "✅ Redis local detectado"
else
  export REDIS_URL="redis://redis:6379/0"
  echo "✅ Redis Docker detectado"
fi

echo ""
echo "1) DB INIT (migraciones + seed)"
python manage.py db:init

echo ""
echo "2) DB SEED (idempotente)"
python manage.py db:seed

echo ""
echo "3) DB BACKUP"
python manage.py db:backup

echo ""
echo "4) CACHE FLUSH"
python manage.py cache:flush

echo ""
echo "5) CACHE WARM"
python manage.py cache:warm

echo ""
echo "6) HEALTH CHECK"

set +e  # permitimos capturar exit code
python manage.py health:check
STATUS=$?
set -e

if [ $STATUS -eq 0 ]; then
  echo "✅ HEALTH CHECK OK"
else
  echo "❌ HEALTH CHECK FALLÓ"
  exit 1
fi

echo ""
echo "7) DB DIFF"
python manage.py db:diff

echo ""
echo "======================================"
echo "🎉 TASK 69 COMPLETADA"
echo "======================================"