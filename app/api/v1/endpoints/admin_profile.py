from __future__ import annotations

import time

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from httpx import ASGITransport, AsyncClient
from pyinstrument import Profiler
from starlette.responses import HTMLResponse

from app.core.config import settings
from app.core.security import get_current_user, require_role
from app.models.usuario import Usuario

router = APIRouter(tags=["Admin Profiling"])


def _normalize_path(path: str) -> str:
    path = path.strip()
    if not path.startswith("/"):
        path = f"/{path}"
    return path


@router.get(
    "/profile",
    response_class=HTMLResponse,
    summary="Perfilar un endpoint GET de la API",
)
async def profile_endpoint(
    request: Request,
    path: str = Query(..., description="Ruta a perfilar, ej: /api/v1/items?page=1&page_size=10"),
    current_user: Usuario = Depends(get_current_user),
    _: None = Depends(require_role("admin")),
) -> HTMLResponse:
    if settings.APP_ENV != "development":
        raise HTTPException(status_code=403, detail="Solo disponible en development")

    normalized_path = _normalize_path(path)

    headers: dict[str, str] = {}

    auth_header = request.headers.get("Authorization")
    api_key = request.headers.get("X-API-Key")

    if auth_header:
        headers["Authorization"] = auth_header
    if api_key:
        headers["X-API-Key"] = api_key

    profiler = Profiler(async_mode="enabled")

    async with AsyncClient(
        transport=ASGITransport(app=request.app),
        base_url="http://localhost:8000",
    ) as client:
        profiler.start()
        start = time.perf_counter()
        response = await client.get(normalized_path, headers=headers)
        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        profiler.stop()

    report_html = profiler.output_html()

    wrapper = f"""
    <html>
      <head>
        <meta charset="utf-8" />
        <title>API JMV Profiling Report</title>
        <style>
          body {{
            margin: 0;
            padding: 0;
            font-family: Arial, sans-serif;
            background: #111827;
            color: #f9fafb;
          }}
          .summary {{
            padding: 16px 20px;
            background: #1f2937;
            border-bottom: 1px solid #374151;
          }}
          .summary h1 {{
            margin: 0 0 10px 0;
            font-size: 22px;
          }}
          .summary p {{
            margin: 6px 0;
            font-size: 14px;
          }}
          .frame {{
            background: #fff;
          }}
        </style>
      </head>
      <body>
        <div class="summary">
          <h1>Profiling Report</h1>
          <p><strong>Path:</strong> {normalized_path}</p>
          <p><strong>Status code:</strong> {response.status_code}</p>
          <p><strong>Elapsed:</strong> {elapsed_ms} ms</p>
          <p><strong>Environment:</strong> {settings.APP_ENV}</p>
          <p><strong>User:</strong> {current_user.email}</p>
        </div>
        <div class="frame">
          {report_html}
        </div>
      </body>
    </html>
    """

    return HTMLResponse(content=wrapper, status_code=200)
