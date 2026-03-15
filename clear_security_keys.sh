#!/bin/bash

REDIS_CONTAINER=$(docker ps --format '{{.Names}}' | grep redis | head -n 1)

if [ -z "$REDIS_CONTAINER" ]; then
  echo "❌ No se encontró contenedor Redis"
  exit 1
fi

echo "Usando Redis: $REDIS_CONTAINER"

docker exec -i "$REDIS_CONTAINER" redis-cli --scan --pattern 'session:*' | while read key; do
  docker exec -i "$REDIS_CONTAINER" redis-cli del "$key" >/dev/null
done

docker exec -i "$REDIS_CONTAINER" redis-cli --scan --pattern 'blacklist:*' | while read key; do
  docker exec -i "$REDIS_CONTAINER" redis-cli del "$key" >/dev/null
done

docker exec -i "$REDIS_CONTAINER" redis-cli --scan --pattern 'security:*' | while read key; do
  docker exec -i "$REDIS_CONTAINER" redis-cli del "$key" >/dev/null
done

echo "✅ Keys de seguridad limpiadas"
