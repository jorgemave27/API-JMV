from PIL import Image
import io
from app.storage.s3_client import upload_file


def process_image(content: bytes, item_id: int):
    """
    Procesa una imagen subida y genera múltiples versiones optimizadas.

    Flujo:
    1. Abre la imagen desde bytes
    2. Genera versiones (thumbnail y medium)
    3. Las sube a S3 (MinIO)
    4. Retorna las keys generadas

    Parámetros:
    - content: bytes de la imagen original
    - item_id: ID del item (para organizar paths en S3)

    Retorna:
    - dict con keys S3 generadas por tamaño
    """

    # =========================================================
    # 🔹 ABRIR IMAGEN DESDE MEMORIA
    # =========================================================
    img = Image.open(io.BytesIO(content))

    # =========================================================
    # 🔹 DEFINICIÓN DE TAMAÑOS
    # =========================================================
    sizes = {
        "thumb": (100, 100),   # 🔹 miniatura
        "medium": (400, 400),  # 🔹 tamaño intermedio
    }

    keys = {}

    # =========================================================
    # 🔹 GENERAR VERSIONES
    # =========================================================
    for name, size in sizes.items():

        # 🔹 Clonar imagen original (evita modificar la base)
        img_copy = img.copy()

        # 🔹 Redimensionar manteniendo proporción
        img_copy.thumbnail(size)

        # =====================================================
        # 🔹 GUARDAR EN BUFFER (MEMORIA)
        # =====================================================
        buffer = io.BytesIO()

        # 🔹 Siempre normalizamos a JPEG (optimización)
        img_copy.save(buffer, format="JPEG")

        # =====================================================
        # 🔹 KEY EN S3 (ORGANIZACIÓN)
        # =====================================================
        key = f"items/{item_id}/{name}.jpg"

        # =====================================================
        # 🔹 SUBIR A S3
        # =====================================================
        upload_file(
            buffer.getvalue(),  # bytes
            key,
            "image/jpeg",
        )

        # 🔹 Guardar referencia
        keys[name] = key

    # =========================================================
    # 🔹 RETORNAR KEYS GENERADAS
    # =========================================================
    return keys