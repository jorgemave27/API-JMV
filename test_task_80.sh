#!/bin/bash

echo "======================================"
echo "TASK 80 - LOAD TEST REAL"
echo "======================================"

BASE_URL="http://localhost:8000"

echo ""
echo "1) Health check..."
curl -s $BASE_URL/health
echo ""
echo "✅ API OK"

echo ""
echo "2) Test 100 conexiones..."

bombardier -c 100 -d 10s $BASE_URL/health

echo ""
echo "3) Test 500 conexiones..."

bombardier -c 500 -d 10s $BASE_URL/health

echo ""
echo "4) Test 1000 conexiones (debe activar backpressure)..."

bombardier -c 1000 -d 10s $BASE_URL/health

echo ""
echo "======================================"
echo "FIN TEST"
echo "======================================"