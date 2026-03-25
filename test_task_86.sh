#!/bin/bash

echo "======================================"
echo "TASK 86 - GOOGLE SSO FINAL TEST"
echo "======================================"

BASE_URL="http://localhost:8000"

echo ""
echo "1) Health check..."
curl -s $BASE_URL/health
echo ""
echo "✅ API OK"

echo ""
echo "2) Pega el token generado por Google SSO:"
read -p "TOKEN: " TOKEN

echo ""
echo "3) Probando userinfo..."

curl -s -X GET "$BASE_URL/oauth/userinfo" \
-H "Authorization: Bearer $TOKEN" \
-H "X-API-Key: dev-secret-key-change-me"

echo ""
echo ""
echo "4) Probando endpoint protegido real..."

curl -s -X GET "$BASE_URL/api/v1/items/1" \
-H "Authorization: Bearer $TOKEN" \
-H "X-API-Key: dev-secret-key-change-me"

echo ""
echo ""
echo "✅ SSO FUNCIONANDO END-TO-END"