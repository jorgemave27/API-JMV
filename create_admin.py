from app.database.database import SessionLocal
from app.models.usuario import Usuario
from app.core.security import hash_password

db = SessionLocal()

# 🔥 PASSWORD VÁLIDA
PASSWORD = "Admin123!"

try:
    user = db.query(Usuario).filter(Usuario.email == "admin@empresa.com").first()

    if user:
        print("⚠️ Usuario ya existe → actualizando password...")

        user.hashed_password = hash_password(PASSWORD)
        user.activo = True
        user.failed_login_attempts = 0
        user.blocked_until = None
        user.rol = "admin"

        db.add(user)
        db.commit()
        db.refresh(user)

        print("✅ Password actualizado")
        print("📧 Email: admin@empresa.com")
        print("🔑 Password: Admin123!")
    else:
        user = Usuario(
            email="admin@empresa.com",
            hashed_password=hash_password(PASSWORD),
            nombre="Admin",
            activo=True,
            rol="admin",
            failed_login_attempts=0,
            blocked_until=None,
        )

        db.add(user)
        db.commit()
        db.refresh(user)

        print("✅ Usuario creado")
        print("📧 Email: admin@empresa.com")
        print("🔑 Password: Admin123!")
finally:
    db.close()