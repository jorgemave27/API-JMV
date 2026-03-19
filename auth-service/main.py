# Ruta: auth-service/main.py

from fastapi import FastAPI

from app.api.routes import internal

app = FastAPI(title="Auth Service", version="1.0.0")

# 🔥 Router interno
app.include_router(internal.router, prefix="/internal", tags=["Internal"])


@app.get("/health")
def health():
    return {"status": "ok", "service": "auth-service"}