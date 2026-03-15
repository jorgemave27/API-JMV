#!/bin/bash

echo "======================================"
echo "DEBUG API AFTER REBUILD"
echo "======================================"

echo ""
echo "1) docker compose ps"
docker compose ps

echo ""
echo "2) health raw"
curl -i http://localhost:8000/health || true

echo ""
echo "3) login raw"
curl -i -X POST "http://localhost:8000/api/v1/auth/login" \
-H "Content-Type: application/json" \
-H "X-API-Key: dev-secret-key-change-me" \
-d '{
  "email":"admin@empresa.com",
  "password":"Admin123!"
}' || true

echo ""
echo "4) últimos logs api"
docker logs --tail 200 api-jmv-api 2>&1 || true

echo ""
echo "======================================"
echo "FIN DEBUG"
echo "======================================"
