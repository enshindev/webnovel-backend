from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from redis.asyncio import Redis


class StreamBuffer(Protocol):
    async def append(self, generation_id: str, text: str) -> int: ...

    async def read_after(self, generation_id: str, seq: int) -> list[tuple[int, str]]: ...

    async def close(self, generation_id: str) -> None: ...


class RedisStreamBuffer:
    def __init__(self, redis: Redis, *, ttl_seconds: int = 86_400) -> None:
        self._redis = redis
        self._ttl = ttl_seconds

    def _key(self, generation_id: str) -> str:
        return f"generation:{generation_id}:chunks"

    async def append(self, generation_id: str, text: str) -> int:
        key = self._key(generation_id)
        seq = int(await self._redis.rpush(key, text))  # type: ignore[misc]
        await self._redis.expire(key, self._ttl)
        return seq

    async def read_after(self, generation_id: str, seq: int) -> list[tuple[int, str]]:
        key = self._key(generation_id)
        start = max(seq, 0)
        rows: Sequence[str] = await self._redis.lrange(key, start, -1)  # type: ignore[misc]
        return [(start + index + 1, text) for index, text in enumerate(rows)]

    async def close(self, generation_id: str) -> None:
        _ = generation_id
