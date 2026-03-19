from __future__ import annotations

import re
from typing import Optional

import bleach


def sanitize_text(
    value: Optional[str],
    *,
    field_name: str = "field",
    max_length: int = 255,
) -> Optional[str]:
    """
    Sanitiza texto de entrada para prevenir XSS y entradas basura.

    Reglas:
    - Si es None, regresa None
    - Debe ser string
    - Elimina tags HTML/JS con bleach.clean()
    - Normaliza espacios múltiples
    - Hace strip()
    - Rechaza contenido vacío o solo espacios
    - Valida longitud máxima
    """
    if value is None:
        return None

    if not isinstance(value, str):
        raise ValueError(f"{field_name} debe ser texto")

    # -------------------------------------------------------------
    # Eliminar HTML / JS
    # tags=[] y strip=True elimina cualquier tag permitido
    # -------------------------------------------------------------
    cleaned = bleach.clean(value, tags=[], attributes={}, strip=True)

    # -------------------------------------------------------------
    # Normalizar espacios múltiples
    # -------------------------------------------------------------
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    # -------------------------------------------------------------
    # Rechazar contenido vacío
    # -------------------------------------------------------------
    if not cleaned:
        raise ValueError(f"{field_name} no puede estar vacío o contener solo espacios")

    # -------------------------------------------------------------
    # Validar longitud máxima
    # -------------------------------------------------------------
    if len(cleaned) > max_length:
        raise ValueError(f"{field_name} no puede exceder {max_length} caracteres")

    return cleaned
