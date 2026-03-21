#!/bin/bash

echo "======================================"
echo "TASK 81 - CHAOS ENGINEERING"
echo "======================================"

BASE_URL="http://localhost:8000"

echo ""
echo "1) Health normal"
curl -s $BASE_URL/health
echo ""
echo "✅ OK"

echo ""
echo "2) Activar slow_db"
curl -s -X POST $BASE_URL/api/v1/admin/chaos/slow_db
echo ""

echo "Probando endpoint..."
time curl -s $BASE_URL/api/v1/items > /dev/null
echo ""

echo ""
echo "3) Activar redis_down"
curl -s -X POST $BASE_URL/api/v1/admin/chaos/redis_down
echo ""

echo "Probando health..."
curl -s $BASE_URL/health
echo ""

echo ""
echo "4) Activar memory_pressure"
curl -s -X POST $BASE_URL/api/v1/admin/chaos/memory_pressure
echo ""

echo "======================================"
echo "TASK 81 DONE"
echo "======================================"