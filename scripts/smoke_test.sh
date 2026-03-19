#!/bin/bash

echo "🔥 Running smoke tests..."

BASE_URL="http://localhost:8000"

# Health
curl --fail $BASE_URL/health || exit 1

# API Health
curl --fail $BASE_URL/api/v1/health || exit 1

# Endpoint crítico (ejemplo)
curl --fail $BASE_URL/api/v1/items || exit 1

echo "✅ Smoke tests OK"