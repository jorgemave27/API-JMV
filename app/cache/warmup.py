"""
Precalentar cache
"""

from app.cache.multi_level_cache import get_or_set


async def warm_items_cache(repo, db):
    items = await repo.list_items(db)

    for item in items:
        await get_or_set(
            key=f"item:{item.id}",
            ttl=300,
            fetch_func=lambda i=item: i
        )