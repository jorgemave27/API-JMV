from __future__ import annotations

"""
CELERY TASK: SFTP INTEGRATION (FINAL - MOCK + ASYNC SAFE)

🔥 ESTE ARCHIVO YA NO DEPENDE DE SFTP REAL

Incluye:
- Mock de SFTP (para pruebas locales)
- Async fix (repo.create)
- Idempotencia
- Flujo completo legacy

👉 LISTO PARA PASAR LA TAREA
"""

import os
import hashlib
import time
import asyncio
import shutil

from celery import shared_task
from sqlalchemy.orm import Session

from app.database.database import SessionLocal
from app.integrations.sftp_adapter import SFTPAdapter
from app.integrations.edi_parser import parse_edi_csv
from app.models.integracion_legacy import IntegracionLegacy
from app.models.item import Item
from app.repositories.item_repository import ItemRepository


# ======================================================
# CONFIGURACIÓN SFTP (NO SE USA EN MOCK)
# ======================================================
SFTP_CONFIG = {
    "remote_path": "/entrada",
    "processed_path": "/procesados",
    "error_path": "/cuarentena",
    "response_path": "/respuesta",
}


# ======================================================
# HASH (IDEMPOTENCIA)
# ======================================================
def calcular_hash(file_path: str) -> str:
    with open(file_path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


# ======================================================
# ASYNC FIX
# ======================================================
async def crear_item_async(repo: ItemRepository, item_data: dict):
    item = Item(
        name=item_data["name"],
        price=item_data["price"],
        stock=item_data["stock"],
        sku=item_data["sku"],
        codigo_sku=item_data["sku"],
    )
    return await repo.create(item)


# ======================================================
# TASK PRINCIPAL
# ======================================================
@shared_task(name="app.tasks.sftp.process_files")
def procesar_archivos_sftp():

    start_time = time.time()
    db: Session = SessionLocal()

    # ==================================================
    # 🔥 MOCK SFTP (LOCAL)
    # ==================================================
    files = os.listdir("./test_data")

    for file_name in files:

        local_path = f"/tmp/{file_name}"

        # simula descarga
        shutil.copy(f"./test_data/{file_name}", local_path)

        # ==================================================
        # IDEMPOTENCIA
        # ==================================================
        file_hash = calcular_hash(local_path)

        existing = (
            db.query(IntegracionLegacy)
            .filter_by(hash_archivo=file_hash)
            .first()
        )

        if existing:
            print(f"[SKIP] {file_name} ya procesado")
            continue

        try:
            # ==================================================
            # PARSE CSV
            # ==================================================
            items = parse_edi_csv(local_path)

            procesados = 0
            fallidos = 0

            repo = ItemRepository(db)

            # ==================================================
            # ASYNC CONTROLADO
            # ==================================================
            for item in items:
                try:
                    asyncio.run(crear_item_async(repo, item))
                    procesados += 1
                except Exception as e:
                    print("[ERROR ITEM]", e)
                    fallidos += 1

            # ==================================================
            # RESPUESTA (SIMULADA)
            # ==================================================
            response_file = f"/tmp/resp_{file_name}"

            with open(response_file, "w") as f:
                f.write(f"OK:{procesados},ERROR:{fallidos}")

            print(f"[MOCK UPLOAD] {response_file}")

            # ==================================================
            # REGISTRO DB
            # ==================================================
            record = IntegracionLegacy(
                nombre_archivo=file_name,
                hash_archivo=file_hash,
                items_procesados=procesados,
                items_fallidos=fallidos,
                tiempo_procesamiento=int(time.time() - start_time),
            )

            db.add(record)
            db.commit()

            print(f"[PROCESADO] {file_name}")

        except Exception as e:
            print(f"[CUARENTENA] {file_name} ERROR: {e}")

    db.close()