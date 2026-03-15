#!/bin/bash

echo "======================================"
echo "CHECK AUTH ROUTES"
echo "======================================"

OPENAPI=$(curl -s http://localhost:8000/openapi.json)

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
  echo "$OPENAPI" | grep -F "$route" >/dev/null && echo "  OK" || echo "  FALTA"
done

echo "======================================"
