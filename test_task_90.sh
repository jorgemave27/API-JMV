#!/bin/bash

echo "======================================"
echo "TASK 90 - SFTP INTEGRATION TEST"
echo "======================================"

echo "Ejecutando job manual..."

docker exec -it api-jmv-celery-worker \
python -c "from app.tasks.sftp_integration_task import procesar_archivos_sftp; procesar_archivos_sftp()"

echo ""
echo "Verifica:"
echo "- Archivos movidos en SFTP"
echo "- Registros en DB (integraciones_legacy)"
echo "- Archivo respuesta generado"

echo "======================================"
echo "FIN TEST"
echo "======================================"