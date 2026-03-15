#!/bin/bash

echo "======================================"
echo "REBUILD LIMPIO API-JMV"
echo "======================================"

echo ""
echo "1) Bajar servicios"
docker compose down

echo ""
echo "2) Rebuild SOLO del api sin cache"
docker compose build --no-cache api

echo ""
echo "3) Levantar api + redis + db"
docker compose up -d db redis api

echo ""
echo "4) Esperar 8 segundos"
sleep 8

echo ""
echo "5) Health"
curl -s http://localhost:8000/health
echo ""

echo ""
echo "6) Auth routes actuales"
curl -s http://localhost:8000/openapi.json | grep -o '"/api/v1/auth[^"]*' | sort -u || true

echo ""
echo "======================================"
echo "FIN REBUILD"
echo "======================================"
