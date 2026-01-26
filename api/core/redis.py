import json
from typing import Any
from redis.asyncio import Redis, from_url

from .config import settings

redis_client: Redis | None = None


async def init_redis() -> Redis:
    """Initialize Redis connection"""
    global redis_client
    redis_client = await from_url(
        settings.redis_url,
        encoding="utf-8",
        decode_responses=True,
    )
    return redis_client


async def close_redis() -> None:
    """Close Redis connection"""
    global redis_client
    if redis_client:
        await redis_client.close()
        redis_client = None


async def get_redis() -> Redis:
    """Dependency for getting Redis client"""
    if redis_client is None:
        await init_redis()
    return redis_client


class RedisCache:
    """Helper class for Redis caching operations"""

    def __init__(self, prefix: str = "krxusd"):
        self.prefix = prefix

    def _make_key(self, key: str) -> str:
        return f"{self.prefix}:{key}"

    async def get(self, key: str) -> Any | None:
        """Get value from cache"""
        client = await get_redis()
        value = await client.get(self._make_key(key))
        if value:
            return json.loads(value)
        return None

    async def set(self, key: str, value: Any, ttl: int = 60) -> None:
        """Set value in cache with TTL (default 60 seconds)"""
        client = await get_redis()
        await client.set(self._make_key(key), json.dumps(value), ex=ttl)

    async def delete(self, key: str) -> None:
        """Delete value from cache"""
        client = await get_redis()
        await client.delete(self._make_key(key))

    async def exists(self, key: str) -> bool:
        """Check if key exists in cache"""
        client = await get_redis()
        return await client.exists(self._make_key(key)) > 0

    async def get_or_set(
        self, key: str, getter: callable, ttl: int = 60
    ) -> Any:
        """Get from cache or set if not exists"""
        value = await self.get(key)
        if value is None:
            value = await getter()
            await self.set(key, value, ttl)
        return value


cache = RedisCache()
