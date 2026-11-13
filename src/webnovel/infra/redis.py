from __future__ import annotations

from typing import cast

from redis.asyncio import Redis

from webnovel.infra.config import get_settings


def create_redis() -> Redis:
    client = Redis.from_url(get_settings().redis_url, decode_responses=True)
    return cast(Redis, client)
