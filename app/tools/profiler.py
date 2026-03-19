from fastapi import Request
from pyinstrument import Profiler
from starlette.responses import HTMLResponse

from app.core.config import get_settings

settings = get_settings()


async def profile_endpoint(request: Request, call_next):
    if settings.APP_ENV != "development":
        return await call_next(request)

    profiler = Profiler()
    profiler.start()

    response = await call_next(request)

    profiler.stop()

    html = profiler.output_html()

    return HTMLResponse(content=html)
