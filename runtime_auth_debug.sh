#!/bin/bash

echo "======================================"
echo "RUNTIME AUTH DEBUG"
echo "======================================"

echo ""
echo "1) Rutas reales de app.main"
docker exec -i api-jmv-api python - <<'PY'
from app.main import app
print("=== AUTH ROUTES EN app ===")
for route in app.routes:
    path = getattr(route, "path", "")
    methods = getattr(route, "methods", set())
    if "auth" in path:
        print(sorted(methods), path)
PY

echo ""
echo "2) Rutas del auth.router"
docker exec -i api-jmv-api python - <<'PY'
from app.api.v1.endpoints.auth import router
print("=== AUTH ROUTES EN auth.router ===")
for route in router.routes:
    path = getattr(route, "path", "")
    methods = getattr(route, "methods", set())
    print(sorted(methods), path)
PY

echo ""
echo "3) Rutas del api_router_v1"
docker exec -i api-jmv-api python - <<'PY'
from app.api.v1 import api_router_v1
print("=== AUTH ROUTES EN api_router_v1 ===")
for route in api_router_v1.routes:
    path = getattr(route, "path", "")
    methods = getattr(route, "methods", set())
    if "auth" in path:
        print(sorted(methods), path)
PY

echo ""
echo "======================================"
echo "FIN DEBUG"
echo "======================================"
