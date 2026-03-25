from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session
import uuid

from app.database.database import get_db
from app.models.item import Item
from app.storage.s3_client import upload_file, generate_presigned_url

router = APIRouter()

# =====================================================
# CONFIGURACIÓN
# =====================================================
MAX_SIZE = 5 * 1024 * 1024  # 5MB
ALLOWED_TYPES = ["image/jpeg", "image/png"]


# =====================================================
# 🔥 SUBIR IMAGEN A S3 (FIX COMPLETO)
# =====================================================
@router.post(
    "/items/{item_id}/imagen",
    summary="Subir imagen a S3 (multipart/form-data)",
)
async def upload_imagen(
    item_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """
    🔥 VERSIÓN FINAL ESTABLE

    FIXES:
    - Manejo de errores S3 (evita crash)
    - Manejo de errores DB (rollback seguro)
    - Validaciones completas
    """

    # -----------------------------
    # VALIDAR TIPO
    # -----------------------------
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(status_code=400, detail="Formato inválido")

    # -----------------------------
    # LEER CONTENIDO
    # -----------------------------
    content = await file.read()

    # -----------------------------
    # VALIDAR TAMAÑO
    # -----------------------------
    if len(content) > MAX_SIZE:
        raise HTTPException(status_code=400, detail="Archivo demasiado grande")

    # -----------------------------
    # OBTENER ITEM
    # -----------------------------
    item = db.query(Item).filter(Item.id == item_id).first()

    if not item:
        raise HTTPException(status_code=404, detail="Item no encontrado")

    # -----------------------------
    # GENERAR KEY ÚNICA
    # -----------------------------
    key = f"items/{item_id}/{uuid.uuid4()}.jpg"

    # -----------------------------
    # 🔥 SUBIR A S3 (PROTEGIDO)
    # -----------------------------
    try:
        upload_file(content, key, file.content_type)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error subiendo a S3: {str(e)}"
        )

    # -----------------------------
    # 🔥 GUARDAR EN DB (PROTEGIDO)
    # -----------------------------
    item.imagen_key = key

    try:
        db.commit()
        db.refresh(item)
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Error guardando en DB: {str(e)}"
        )

    return {
        "success": True,
        "message": "Imagen subida correctamente",
        "key": key,
    }


# =====================================================
# 🔥 GET ITEM (CON URL S3 PRESIGNADA)
# =====================================================
@router.get(
    "/items/{item_id}",
    summary="Obtener item con imagen S3",
)
async def get_item(
    item_id: int,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    """
    🔥 VERSIÓN FINAL

    FIXES:
    - Presigned URL segura
    - No rompe si S3 falla
    """

    item = db.query(Item).filter(Item.id == item_id).first()

    if not item:
        raise HTTPException(status_code=404, detail="Item no encontrado")

    # -----------------------------
    # RESPUESTA BASE
    # -----------------------------
    data = {
        "id": item.id,
        "name": item.name,
        "price": item.price,
        "stock": item.stock,
        "imagen_url": None,
    }

    # -----------------------------
    # 🔥 GENERAR URL S3 SEGURA
    # -----------------------------
    if item.imagen_key:
        try:
            data["imagen_url"] = generate_presigned_url(item.imagen_key)
        except Exception:
            # 🔥 No rompemos la API si S3 falla
            data["imagen_url"] = None

    return {
        "success": True,
        "message": "Item obtenido exitosamente",
        "data": data,
    }