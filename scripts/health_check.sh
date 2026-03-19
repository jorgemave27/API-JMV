#!/bin/bash

echo "🩺 Running production health check..."

BASE_URL="http://api-jmv.your-domain.com"

# Health principal
if ! curl --fail $BASE_URL/health; then
  echo "❌ Health failed"
  exit 1
fi

# API
if ! curl --fail $BASE_URL/api/v1/health; then
  echo "❌ API health failed"
  exit 1
fi

echo "✅ Production healthy"