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
