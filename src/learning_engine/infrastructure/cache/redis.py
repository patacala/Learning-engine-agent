import json
from typing import Any

import redis.asyncio as redis

from learning_engine.config import settings


class RedisCache:
    def __init__(self, url: str | None = None):
        self._redis = redis.from_url(url or settings.redis_url, decode_responses=True)

    async def get(self, key: str) -> Any | None:
        value = await self._redis.get(key)
        if value is not None:
            return json.loads(value)
        return None

    async def set(self, key: str, value: Any, ttl: int = 3600) -> None:
        await self._redis.set(key, json.dumps(value, default=str), ex=ttl)

    async def delete(self, key: str) -> None:
        await self._redis.delete(key)

    async def list_push(self, key: str, value: str, ttl: int = 300) -> None:
        """Append to a Redis list (used by the CRM inbound debounce buffer).
        The TTL is a safety net so an abandoned buffer self-expires."""
        await self._redis.rpush(key, value)
        await self._redis.expire(key, ttl)

    async def list_drain(self, key: str) -> list[str]:
        """Atomically read AND clear a list, returning its items in order. The
        atomicity matters: with multiple web workers it guarantees only one
        drains a given buffer — the others get an empty list and no-op, so the
        same messages are never processed twice."""
        async with self._redis.pipeline(transaction=True) as pipe:
            pipe.lrange(key, 0, -1)
            pipe.delete(key)
            values, _ = await pipe.execute()
        return values or []

    async def close(self) -> None:
        await self._redis.aclose()
