from __future__ import annotations

import os
import time
from pathlib import Path

from httpx import ASGITransport, AsyncClient
from pyinstrument import Profiler

from app.core.config import settings


class AutoProfilerService:
    def __init__(self) -> None:
        self.output_dir = Path(settings.PROFILING_OUTPUT_DIR)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    async def profile_path(
        self,
        app,
        path: str,
        headers: dict[str, str] | None = None,
    ) -> str:
        headers = headers or {}

        profiler = Profiler(async_mode="enabled")

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://localhost:8000",
        ) as client:
            profiler.start()
            await client.get(path, headers=headers)
            profiler.stop()

        filename = f"profile_{path.strip('/').replace('/', '_').replace('?', '_').replace('&', '_').replace('=', '_')}_{int(time.time())}.html"
        filepath = self.output_dir / filename
        filepath.write_text(profiler.output_html(), encoding="utf-8")

        return str(filepath)


auto_profiler_service = AutoProfilerService()