#!/bin/bash

API_CONTAINER="api-jmv-api"

echo "======================================"
echo "INSPECCION REAL DE AUTH EN API CONTAINER"
echo "======================================"

echo ""
echo "1) Contenedor objetivo"
docker ps --format "table {{.Names}}\t{{.Image}}\t{{.Ports}}" | grep "$API_CONTAINER" || true

echo ""
echo "2) OpenAPI routes auth actuales"
curl -s http://localhost:8000/openapi.json | grep -o '"/api/v1/auth[^"]*' | sort -u || true

echo ""
echo "3) Ver auth.py dentro del contenedor"
docker exec -i "$API_CONTAINER" sh -c '
echo "--- PWD ---"
pwd
echo "--- /app ---"
ls -la /app || true
echo "--- auth.py encontrado? ---"
find / -path "*app/api/v1/endpoints/auth.py" 2>/dev/null
echo "--- contenido auth.py ---"
AUTH_FILE=$(find / -path "*app/api/v1/endpoints/auth.py" 2>/dev/null | head -n 1)
if [ -n "$AUTH_FILE" ]; then
  sed -n "1,260p" "$AUTH_FILE"
else
  echo "NO SE ENCONTRO auth.py"
fi
'

echo ""
echo "4) Buscar strings clave dentro del contenedor"
docker exec -i "$API_CONTAINER" sh -c '
AUTH_FILE=$(find / -path "*app/api/v1/endpoints/auth.py" 2>/dev/null | head -n 1)
if [ -n "$AUTH_FILE" ]; then
  echo "logout:"
  grep -n "logout" "$AUTH_FILE" || true
  echo "sesiones:"
  grep -n "sesiones" "$AUTH_FILE" || true
  echo "cerrar-sesion:"
  grep -n "cerrar-sesion" "$AUTH_FILE" || true
else
  echo "NO SE ENCONTRO auth.py"
fi
'

echo ""
echo "5) Ver __init__.py de api/v1 dentro del contenedor"
docker exec -i "$API_CONTAINER" sh -c '
INIT_FILE=$(find / -path "*app/api/v1/__init__.py" 2>/dev/null | head -n 1)
echo "INIT_FILE=$INIT_FILE"
if [ -n "$INIT_FILE" ]; then
  sed -n "1,220p" "$INIT_FILE"
else
  echo "NO SE ENCONTRO __init__.py"
fi
'

echo ""
echo "6) Ver main.py dentro del contenedor"
docker exec -i "$API_CONTAINER" sh -c '
MAIN_FILE=$(find / -path "*app/main.py" 2>/dev/null | head -n 1)
echo "MAIN_FILE=$MAIN_FILE"
if [ -n "$MAIN_FILE" ]; then
  sed -n "1,260p" "$MAIN_FILE"
else
  echo "NO SE ENCONTRO main.py"
fi
'

echo ""
echo "======================================"
echo "FIN INSPECCION"
echo "======================================"
