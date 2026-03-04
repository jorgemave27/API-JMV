from __future__ import annotations

from fastapi import Request


def get_client_ip(request: Request) -> str:
    # Si un proxy mete X-Forwarded-For, lo respetamos
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def log_client_ip(request: Request) -> str:
    client_ip = request.client.host if request.client else "unknown"
    print(f"[IP] Cliente: {client_ip}")
    return client_ip

