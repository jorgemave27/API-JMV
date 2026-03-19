# scripts/create_admin_pg.py
import sys
from pathlib import Path

# -----------------------------------------------------
# Agregar root del proyecto al PYTHONPATH
# -----------------------------------------------------
sys.path.append(str(Path(__file__).resolve().parents[1]))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.security import hash_password
from app.models.usuario import Usuario

DATABASE_URL = "postgresql://postgres:postgres@localhost:5432/api_jmv"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def main():
    db = SessionLocal()

    try:
        existing = db.query(Usuario).filter(Usuario.email == "admin@empresa.com").first()

        if existing:
            print("El usuario admin ya existe")
            return

        user = Usuario(
            email="admin@empresa.com",
            hashed_password=hash_password("Admin123*"),
            rol="admin",
            activo=True,
        )

        db.add(user)
        db.commit()
        db.refresh(user)

        print(f"Usuario creado: id={user.id}, email={user.email}, rol={user.rol}")

    finally:
        db.close()


if __name__ == "__main__":
    main()
