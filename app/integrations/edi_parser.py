"""
EDI PARSER (CSV)

Este módulo interpreta archivos provenientes de sistemas legacy.
Simulamos un EDI simplificado usando CSV.

Formato esperado:
name,price,stock,sku

Ejemplo:
Laptop,1000,10,LAP-001
Mouse,50,100,MOU-002
"""

import csv


def parse_edi_csv(file_path: str):
    """
    Convierte un archivo CSV en una lista de items.

    Args:
        file_path: Ruta del archivo CSV

    Returns:
        Lista de diccionarios con datos de items

    Raises:
        ValueError: Si el formato es inválido
    """

    items = []

    with open(file_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        for row in reader:
            # Validación mínima de estructura
            if "name" not in row or "price" not in row:
                raise ValueError("Formato EDI inválido")

            items.append(
                {
                    "name": row["name"],
                    "price": float(row["price"]),
                    "stock": int(row.get("stock", 0)),
                    "sku": row.get("sku"),
                }
            )

    return items