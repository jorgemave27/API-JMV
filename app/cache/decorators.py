"""
Decoradores de caché automático
"""

from functools import wraps
from typing import Callable

from app.cache.multi_level_cache import get_or_set, invalidate


def cacheable(ttl: int, key_fn: Callable):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            key = key_fn(*args, **kwargs)

            async def fetch():
                return await func(*args, **kwargs)

            return await get_or_set(
                key=key,
                ttl=ttl,
                fetch_func=fetch,
            )

        return wrapper

    return decorator


def cache_invalidate(key_fn: Callable):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            result = await func(*args, **kwargs)

            key = key_fn(*args, **kwargs)
            await invalidate(key)

            return result

        return wrapper

    return decorator