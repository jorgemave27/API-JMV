#!/bin/bash

echo "======================================"
echo "RESTART API CLEAN"
echo "======================================"

docker compose stop api
docker compose rm -f api
docker compose build --no-cache api
docker compose up -d api

echo ""
echo "Esperando 10 segundos..."
sleep 10

echo ""
echo "Health:"
curl -i http://localhost:8000/health || true

echo ""
echo "Logs:"
docker logs --tail 120 api-jmv-api 2>&1 || true
