from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration
ROOT = Path(__file__).resolve().parents[2]


async def test_generation_pipeline_with_fake_model(
    postgres_url: str, redis_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DATABASE_URL", postgres_url)
    monkeypatch.setenv("REDIS_URL", redis_url)
    monkeypatch.setenv("LLM_PROVIDER", "fake")
    monkeypatch.setenv("LLM_MODEL", "fake")
    from webnovel.infra.config import get_settings

    get_settings.cache_clear()
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=ROOT,
        env={**os.environ},
        check=True,
        capture_output=True,
        text=True,
    )
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from webnovel.infra.db.engine import create_engine
    from webnovel.infra.redis import create_redis
    from webnovel.infra.streams import RedisStreamBuffer
    from webnovel.llm.gateway.factory import build_model_client
    from webnovel.modules.chapters_versions.repository import SqlAlchemyChapterRepository
    from webnovel.modules.chapters_versions.service import ChaptersService
    from webnovel.modules.generation.contract import GenerationCreate, GenerationStatus, TaskType
    from webnovel.modules.generation.repository import SqlAlchemyGenerationRepository
    from webnovel.modules.generation.runner import GenerationRunner
    from webnovel.modules.generation.service import GenerationsService
    from webnovel.modules.usage.pricing import load_pricing
    from webnovel.modules.usage.repository import SqlAlchemyUsageRepository
    from webnovel.modules.usage.service import UsageServiceImpl
    from webnovel.modules.works.repository import SqlAlchemyWorkRepository
    from webnovel.modules.works.service import WorksService

    settings = get_settings()
    engine = create_engine()
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    redis = create_redis()
    try:
        async with session_factory() as session, session.begin():
            works = WorksService(SqlAlchemyWorkRepository(session))
            work = await works.create("E2E", "悬疑")
            chapters = ChaptersService(SqlAlchemyChapterRepository(session), works)
            chapter = await chapters.create(work.id, 1, "雨夜", "旧文。")
            generations = GenerationsService(SqlAlchemyGenerationRepository(session), chapters)
            generation = await generations.create(
                GenerationCreate(
                    work_id=work.id,
                    chapter_id=chapter.id,
                    task_type=TaskType.CONTINUE,
                ),
                "e2e-key",
            )
            usage = UsageServiceImpl(
                SqlAlchemyUsageRepository(session), load_pricing(settings.pricing_config_path)
            )
            runner = GenerationRunner(
                repository=SqlAlchemyGenerationRepository(session),
                chapter_service=chapters,
                model_client=build_model_client(settings),
                settings=settings,
                buffer=RedisStreamBuffer(redis),
                usage=usage,
            )
            await runner.run(generation.id)
            refreshed = await generations.get(generation.id)
            assert refreshed.status is GenerationStatus.SUCCEEDED
            draft = await generations.get_draft(
                refreshed.draft_id or generation.draft_id or chapter.id
            )
            assert "雨夜" in draft.content
    finally:
        await redis.aclose()
        await engine.dispose()
