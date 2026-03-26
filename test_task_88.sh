#!/bin/bash

BASE_URL="http://localhost:8000/api/v1"

echo "======================================"
echo "TASK 88 - LLM TEST"
echo "======================================"

echo ""
echo "1) Clasificar item..."
curl -X POST "$BASE_URL/items/clasificar-automaticamente" \
-H "Content-Type: application/json" \
-d '{
  "nombre": "Laptop Gamer RTX 4060",
  "descripcion": "Laptop potente para gaming y edición"
}'
echo ""

echo ""
echo "2) Preguntar catálogo..."
curl -X POST "$BASE_URL/catalogo/preguntar" \
-H "Content-Type: application/json" \
-d '{
  "pregunta": "tienes laptops baratas?"
}'
echo ""

echo ""
echo "======================================"
echo "FIN TEST"
echo "======================================"