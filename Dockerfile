# =========================================================
# STAGE 1: BUILD / TEST
# - Instala dependencias
# - Copia proyecto
# - Ejecuta pytest
# - Si falla pytest, NO se construye la imagen final
# - Celery corre en modo eager + memoria para no depender
#   de Redis durante el build
# =========================================================
FROM python:3.11-slim AS build

# Variables de Python
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Variables mínimas para Settings
ENV APP_ENV=development
ENV DATABASE_URL=sqlite:///./test.db
ENV API_KEY=dev-secret-key-change-me
ENV JWT_SECRET_KEY=super-secret-jwt-key-for-tests
ENV SECRET_KEY=super-secret-key-for-tests
ENV ACCESS_TOKEN_EXPIRE_MINUTES=30
ENV REFRESH_TOKEN_EXPIRE_DAYS=7
ENV CORS_ALLOW_ORIGINS=http://localhost:3000,http://127.0.0.1:3000

# Redis de la app en tests:
# Se deja definido para cualquier import que lo necesite,
# pero Celery NO lo usará porque abajo se sobreescribe.
ENV REDIS_URL=redis://localhost:6379/1

# Celery en modo local para tests del build
ENV CELERY_BROKER_URL=memory://
ENV CELERY_RESULT_BACKEND=cache+memory://
ENV CELERY_TASK_ALWAYS_EAGER=true
ENV CELERY_TASK_EAGER_PROPAGATES=true
ENV CELERY_TASK_STORE_EAGER_RESULT=false

# Directorio de trabajo
WORKDIR /app

# Dependencias del sistema
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copiar requirements primero para cache de capas
COPY requirements.txt .

# Instalar dependencias Python
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copiar el proyecto completo
COPY . .

# Ejecutar pruebas
RUN pytest -q

# =========================================================
# STAGE 2: PRODUCTION
# - Imagen final limpia
# - Usuario no-root
# - Usa Redis/PostgreSQL reales vía docker-compose
# =========================================================
FROM python:3.11-slim AS production

# Variables de Python
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Directorio de trabajo
WORKDIR /app

# Crear usuario no-root
RUN useradd -m appuser

# Copiar runtime ya instalado desde build
COPY --from=build /usr/local /usr/local

# Copiar solo lo necesario del proyecto
COPY --from=build /app/app /app/app
COPY --from=build /app/alembic /app/alembic
COPY --from=build /app/alembic.ini /app/alembic.ini
COPY --from=build /app/requirements.txt /app/requirements.txt

# Permisos
RUN chown -R appuser:appuser /app

# Usuario no-root
USER appuser

# Puerto expuesto
EXPOSE 8000

# Arranque de la API
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]