# PERFORMANCE - API JMV

## Objetivo

Establecer una línea base de rendimiento, identificar endpoints lentos, perfilar con herramientas adecuadas y aplicar una optimización medible.

## Herramientas utilizadas

- `pyinstrument` para profiling por request y flamegraph HTML
- logs del middleware `RequestLoggingMiddleware`
- `py-spy` para profiling continuo sin detener la aplicación
- `memory-profiler` preparado para futura importación masiva CSV

## Metodología

1. Se revisaron los logs de tiempos de respuesta generados por middleware.
2. Se identificó el endpoint más probable de alta latencia: `GET /api/v1/items/`.
3. Se creó el endpoint administrativo `GET /api/v1/admin/profile?path=...` para ejecutar profiling manual en desarrollo.
4. Se implementó un auto-profiler para requests GET lentas repetidas.
5. Se optimizó el endpoint `listar_items` para reducir trabajo innecesario y consolidar mejor la respuesta cacheable.
6. Se dejó preparada la configuración para profiling continuo con `py-spy` en producción.

## Endpoint identificado como candidato principal

- `GET /api/v1/items/`

## Motivos

- Ejecuta consulta de conteo
- Ejecuta consulta paginada
- Aplica filtros dinámicos
- Realiza serialización HATEOAS
- Usa caché y carga de relaciones
- Es un endpoint central del sistema

## Optimización aplicada

- Mejora del cálculo de `count` usando `select(Item.id)` como base mínima
- Evita trabajo extra si la lista viene vacía
- Conserva caché de respuesta completa
- Mantiene paginación, filtros y HATEOAS sin romper compatibilidad

## Endpoint de profiling manual

`GET /api/v1/admin/profile?path=/api/v1/items?page=1&page_size=10`

Requisitos:

- ambiente `development`
- usuario autenticado con rol `admin`
- headers válidos (`Authorization`, `X-API-Key`)

## Auto profiling

Se activa automáticamente cuando un endpoint GET supera el umbral de lentitud configurado durante 3 requests consecutivas.

### Configuración

- `PROFILING_SLOW_REQUEST_THRESHOLD_MS=500`
- `PROFILING_CONSECUTIVE_SLOW_REQUESTS=3`
- `PROFILING_OUTPUT_DIR=profiles`

## Producción con py-spy

Ejemplo de uso:

```bash
ps aux | grep uvicorn
py-spy record -o profile.svg --pid <PID>
```
