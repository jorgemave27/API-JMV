#!/bin/bash

echo "=================================================="
echo "       API-JMV BACKEND DEBUG CHECK"
echo "=================================================="

BASE_URL="http://localhost:8000"

echo ""
echo "1) Puerto 8000 en uso"
echo "--------------------------------------------------"
lsof -i :8000 || true

echo ""
echo "2) Contenedores Docker activos"
echo "--------------------------------------------------"
docker ps || true

echo ""
echo "3) Docker Compose services"
echo "--------------------------------------------------"
docker compose ps || true

echo ""
echo "4) Health endpoint"
echo "--------------------------------------------------"
curl -s $BASE_URL/health
echo ""
echo ""
echo "5) API v1 health endpoint"
echo "--------------------------------------------------"
curl -s $BASE_URL/api/v1/health
echo ""

echo ""
echo "6) OpenAPI contiene rutas auth?"
echo "--------------------------------------------------"
curl -s $BASE_URL/openapi.json | grep -E 'auth|sesiones|logout|cerrar-sesion|login|refresh' || true

echo ""
echo "7) OpenAPI contiene rutas exactas esperadas?"
echo "--------------------------------------------------"
for route in \
  "/api/v1/auth/login" \
  "/api/v1/auth/refresh" \
  "/api/v1/auth/logout" \
  "/api/v1/auth/sesiones" \
  "/api/v1/auth/cerrar-sesion/{jti}" \
  "/api/v1/auth/cambiar-password" \
  "/api/v1/auth/forgot-password" \
  "/api/v1/auth/reset-password"
do
  echo "Buscando $route"
  curl -s $BASE_URL/openapi.json | grep "$route" >/dev/null && echo "  ✅ OK" || echo "  ❌ NO ENCONTRADA"
done

echo ""
echo "8) Prueba directa endpoint sesiones sin auth"
echo "--------------------------------------------------"
curl -i -s $BASE_URL/api/v1/auth/sesiones
echo ""

echo ""
echo "9) Redis keys de seguridad"
echo "--------------------------------------------------"
REDIS_CONTAINER=$(docker ps --format '{{.Names}}' | grep redis | head -n 1)
if [ -n "$REDIS_CONTAINER" ]; then
  echo "Redis container: $REDIS_CONTAINER"
  docker exec -i $REDIS_CONTAINER redis-cli keys 'session:*' || true
  docker exec -i $REDIS_CONTAINER redis-cli keys 'blacklist:*' || true
  docker exec -i $REDIS_CONTAINER redis-cli keys 'security:*' || true
else
  echo "❌ No se encontró contenedor redis"
fi

echo ""
echo "10) Logs recientes del contenedor API"
echo "--------------------------------------------------"
API_CONTAINER=$(docker ps --format '{{.Names}}' | grep -E 'api$|api-' | head -n 1)
if [ -n "$API_CONTAINER" ]; then
  echo "API container: $API_CONTAINER"
  docker logs --tail 120 $API_CONTAINER 2>&1 || true
else
  echo "❌ No se encontró contenedor API"
fi

echo ""
echo "11) Ver archivo auth.py dentro del contenedor"
echo "--------------------------------------------------"
if [ -n "$API_CONTAINER" ]; then
  docker exec -i $API_CONTAINER sh -c "ls -la /app/app/api/v1/endpoints/auth.py && echo '---' && sed -n '1,260p' 
/app/app/api/v1/endpoints/auth.py" || true
fi

echo ""
echo "12) Ver app/api/v1/__init__.py dentro del contenedor"
echo "--------------------------------------------------"
if [ -n "$API_CONTAINER" ]; then
  docker exec -i $API_CONTAINER sh -c "ls -la /app/app/api/v1/__init__.py && echo '---' && sed -n '1,220p' 
/app/app/api/v1/__init__.py" || true
fi

echo ""
echo "13) Ver app/main.py dentro del contenedor"
echo "--------------------------------------------------"
if [ -n "$API_CONTAINER" ]; then
  docker exec -i $API_CONTAINER sh -c "ls -la /app/app/main.py && echo '---' && sed -n '1,260p' /app/app/main.py" 
|| true
fi

echo ""
echo "14) Resumen rápido"
echo "--------------------------------------------------"
echo "Si /health responde pero /api/v1/auth/sesiones da 404, casi seguro:"
echo "  - router auth no está incluido en app/api/v1/__init__.py"
echo "  - o api_router_v1 no está incluido en main.py"
echo "  - o Docker sigue con build viejo"
echo ""
echo "Si openapi.json NO contiene /api/v1/auth/sesiones:"
echo "  - FastAPI no montó ese router"
echo ""
echo "Si el archivo dentro del contenedor sí tiene los endpoints pero openapi no:"
echo "  - error de import o router no incluido"
echo ""
echo "Si el archivo local está bien pero dentro del contenedor no:"
echo "  - rebuild pendiente"
echo ""
echo "=================================================="
echo "              FIN DEBUG CHECK"
echo "=================================================="
