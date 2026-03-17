# manage.py

from __future__ import annotations

import subprocess
import sys
from datetime import datetime

import typer
from faker import Faker
from sqlalchemy import text

# =========================================================
# IMPORT CRÍTICO PARA REGISTRAR MODELOS
# =========================================================
import app.models

from app.core.config import settings
from app.database.database import SessionLocal, engine
from app.models.item import Item

# Redis
try:
    import redis
except ImportError:
    redis = None

app = typer.Typer(help="CLI de administración API-JMV 🚀")
fake = Faker()


# =========================================================
# UTILS
# =========================================================
def get_redis():
    """
    Conexión Redis usando REDIS_URL.
    Compatible con Docker y local.
    """
    if not redis:
        return None

    try:
        return redis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
        )
    except Exception:
        return None


# =========================================================
# DB INIT
# =========================================================
@app.command("db:init")
def db_init():
    """
    Inicializa la base de datos:
    - Ejecuta migraciones
    - Ejecuta seed
    """
    typer.echo("🚀 DB INIT...")

    try:
        subprocess.run(["alembic", "upgrade", "head"], check=True)
        typer.echo("✅ Migraciones OK")

        subprocess.run([sys.executable, "manage.py", "db:seed"], check=True)
        typer.echo("✅ Seed OK")

    except Exception as e:
        typer.echo(f"❌ Error: {e}")
        raise typer.Exit(code=1)


# =========================================================
# DB SEED
# =========================================================
@app.command("db:seed")
def db_seed():
    """
    Inserta datos de prueba (idempotente).
    No duplica si ya existen registros.
    """
    typer.echo("🌱 Seeding...")

    db = SessionLocal()

    try:
        count = db.query(Item).count()

        if count > 0:
            typer.echo("⚠️ Ya hay datos, se omite seed")
            return

        for _ in range(10):
            item = Item(
                name=fake.word(),
                description=fake.sentence(),
                price=float(fake.random_int(min=10, max=500)),
                stock=fake.random_int(min=1, max=100),
            )
            db.add(item)

        db.commit()
        typer.echo("✅ Seed completado")

    except Exception as e:
        db.rollback()
        typer.echo(f"❌ Error: {e}")
        raise typer.Exit(code=1)

    finally:
        db.close()


# =========================================================
# DB BACKUP
# =========================================================
@app.command("db:backup")
def db_backup():
    """
    Genera backup de la base de datos.
    Compatible con SQLite y PostgreSQL.
    """
    typer.echo("💾 Backup...")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    try:
        if settings.DATABASE_URL.startswith("sqlite"):
            filename = f"backup_{timestamp}.db"
            src = settings.DATABASE_URL.replace("sqlite:///", "")

            subprocess.run(["cp", src, filename], check=True)

        else:
            filename = f"backup_{timestamp}.sql"

            subprocess.run(
                [
                    "pg_dump",
                    settings.DATABASE_URL,
                    "-f",
                    filename,
                ],
                check=True,
            )

        typer.echo(f"✅ Backup generado: {filename}")

    except Exception as e:
        typer.echo(f"❌ Error backup: {e}")
        raise typer.Exit(code=1)


# =========================================================
# CACHE FLUSH
# =========================================================
@app.command("cache:flush")
def cache_flush():
    """
    Limpia completamente Redis.
    """
    typer.echo("🧹 Cache flush...")

    r = get_redis()

    if not r:
        typer.echo("❌ Redis no disponible")
        raise typer.Exit(code=1)

    try:
        r.flushall()
        typer.echo("✅ Cache limpio")

    except Exception as e:
        typer.echo(f"❌ Error Redis: {e}")
        raise typer.Exit(code=1)


# =========================================================
# CACHE WARM
# =========================================================
@app.command("cache:warm")
def cache_warm():
    """
    Precarga cache con items más consultados.
    """
    typer.echo("🔥 Cache warm...")

    r = get_redis()

    if not r:
        typer.echo("❌ Redis no disponible")
        raise typer.Exit(code=1)

    db = SessionLocal()

    try:
        items = db.query(Item).limit(10).all()

        for item in items:
            key = f"item:{item.id}"
            r.set(key, item.name, ex=3600)

        typer.echo("✅ Cache cargado")

    except Exception as e:
        typer.echo(f"❌ Error: {e}")
        raise typer.Exit(code=1)

    finally:
        db.close()


# =========================================================
# HEALTH CHECK
# =========================================================
@app.command("health:check")
def health_check():
    """
    Verifica salud del sistema:
    - Base de datos
    - Redis

    Exit codes:
    0 = OK
    1 = FAIL
    """
    typer.echo("🩺 Health check...")

    try:
        # DB check
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))

        typer.echo("✅ DB OK")

        # Redis check
        r = get_redis()
        if r is None:
            typer.echo("❌ Redis no disponible")
            raise typer.Exit(code=1)

        r.ping()
        typer.echo("✅ Redis OK")

        typer.echo("🎉 Sistema saludable")
        return

    except typer.Exit:
        raise

    except Exception as e:
        typer.echo(f"❌ FAIL: {e}")
        raise typer.Exit(code=1)


# =========================================================
# DB DIFF
# =========================================================
@app.command("db:diff")
def db_diff():
    """
    Detecta diferencias entre modelos y BD usando Alembic.
    """
    typer.echo("🔍 DB DIFF...")

    try:
        result = subprocess.run(
            ["alembic", "revision", "--autogenerate", "-m", "diff_check"],
            capture_output=True,
            text=True,
        )

        stdout = result.stdout or ""
        stderr = result.stderr or ""

        if result.returncode != 0:
            typer.echo(f"❌ Error: {stderr.strip() or stdout.strip()}")
            raise typer.Exit(code=1)

        if "No changes detected" in stdout:
            typer.echo("✅ Sin cambios")
        else:
            typer.echo("⚠️ Hay diferencias detectadas")

    except typer.Exit:
        raise

    except Exception as e:
        typer.echo(f"❌ Error: {e}")
        raise typer.Exit(code=1)


# =========================================================
# ENTRYPOINT
# =========================================================
if __name__ == "__main__":
    app()