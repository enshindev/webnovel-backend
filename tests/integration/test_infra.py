from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration
ROOT = Path(__file__).resolve().parents[2]


async def test_postgres_migrations_apply(
    postgres_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    import asyncpg

    monkeypatch.setenv("DATABASE_URL", postgres_url)
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=ROOT,
        env={**os.environ},
        check=True,
        capture_output=True,
        text=True,
    )
    conn = await asyncpg.connect(postgres_url.replace("postgresql+asyncpg://", "postgresql://"))
    try:
        rows = await conn.fetch(
            "SELECT tablename FROM pg_tables WHERE schemaname IN ('public', 'exp_assistant')"
        )
        tables = {row["tablename"] for row in rows}
        assert {
            "works",
            "chapters",
            "generations",
            "usage_ledger",
            "quality_checks",
            "outbox_events",
            "knowledge_embeddings",
            "timeline_events",
            "library_documents",
            "library_chunks",
            "eval_runs",
            "outline_drafts",
            "volumes",
            "workflow_runs",
            "prompt_versions",
            "prompt_labels",
            "story_events",
            "knowledge_states",
        } <= tables
        assert "conversations" in tables
    finally:
        await conn.close()


async def test_redis_reachable(redis_url: str) -> None:
    from redis.asyncio import Redis

    client = Redis.from_url(redis_url, decode_responses=True)
    try:
        assert await client.ping() is True
    finally:
        await client.aclose()


async def test_expired_idempotency_keys_are_cleaned(postgres_url: str) -> None:
    from datetime import UTC, datetime, timedelta

    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from webnovel.modules.generation.models import IdempotencyKeyModel
    from webnovel.modules.generation.repository import delete_expired_idempotency_keys

    engine = create_async_engine(postgres_url)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with sessions() as session, session.begin():
            session.add(
                IdempotencyKeyModel(
                    key="expired-key",
                    scope="test",
                    payload_hash="hash",
                    expires_at=datetime.now(UTC) - timedelta(hours=1),
                )
            )
            session.add(
                IdempotencyKeyModel(
                    key="live-key",
                    scope="test",
                    payload_hash="hash",
                    expires_at=datetime.now(UTC) + timedelta(hours=1),
                )
            )

        async with sessions() as session, session.begin():
            deleted = await delete_expired_idempotency_keys(session)
            assert deleted == 1

        async with sessions() as session:
            keys = set((await session.scalars(select(IdempotencyKeyModel.key))).all())
            assert "live-key" in keys
            assert "expired-key" not in keys
    finally:
        await engine.dispose()
