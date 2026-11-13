from __future__ import annotations

import asyncio
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile

import pgserver
import redislite
from sqlalchemy.ext.asyncio import async_sessionmaker


async def main() -> None:
    pgdata = pathlib.Path(tempfile.mkdtemp(prefix="webnovel-real-pg-"))
    server = pgserver.get_server(pgdata)
    redis_client = redislite.Redis()
    redis_path = redis_client.connection_pool.connection_kwargs["path"]
    os.environ["DATABASE_URL"] = server.get_uri().replace("postgresql://", "postgresql+asyncpg://")
    os.environ["REDIS_URL"] = f"unix://{redis_path}"
    try:
        subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            check=True,
            capture_output=True,
            text=True,
        )
        from webnovel.infra.config import get_settings
        from webnovel.infra.db.engine import create_engine
        from webnovel.infra.redis import create_redis
        from webnovel.infra.streams import RedisStreamBuffer
        from webnovel.llm.gateway.factory import build_model_client
        from webnovel.modules.chapters_versions.repository import (
            SqlAlchemyChapterRepository,
        )
        from webnovel.modules.chapters_versions.service import ChaptersService
        from webnovel.modules.generation.contract import (
            GenerationCreate,
            GenerationStatus,
            TaskType,
        )
        from webnovel.modules.generation.repository import SqlAlchemyGenerationRepository
        from webnovel.modules.generation.runner import GenerationRunner
        from webnovel.modules.generation.service import GenerationsService
        from webnovel.modules.usage.pricing import load_pricing
        from webnovel.modules.usage.repository import SqlAlchemyUsageRepository
        from webnovel.modules.usage.service import UsageServiceImpl
        from webnovel.modules.works.repository import SqlAlchemyWorkRepository
        from webnovel.modules.works.service import WorksService

        get_settings.cache_clear()
        settings = get_settings()
        engine = create_engine()
        factory = async_sessionmaker(engine, expire_on_commit=False)
        redis = create_redis()
        try:
            async with factory() as session, session.begin():
                works = WorksService(SqlAlchemyWorkRepository(session))
                work = await works.create("真实模型联调", "悬疑")
                chapters = ChaptersService(SqlAlchemyChapterRepository(session), works)
                chapter = await chapters.create(work.id, 1, "雨夜", "沈砚听见旧巷里第二声钟响。")
                generations = GenerationsService(SqlAlchemyGenerationRepository(session), chapters)
                generation = await generations.create(
                    GenerationCreate(
                        work_id=work.id,
                        chapter_id=chapter.id,
                        task_type=TaskType.CONTINUE,
                    ),
                    "real-smoke",
                )
                usage = UsageServiceImpl(
                    SqlAlchemyUsageRepository(session),
                    load_pricing(settings.pricing_config_path),
                )
                buffer = RedisStreamBuffer(redis)
                runner = GenerationRunner(
                    repository=SqlAlchemyGenerationRepository(session),
                    chapter_service=chapters,
                    model_client=build_model_client(settings),
                    settings=settings,
                    buffer=buffer,
                    usage=usage,
                )
                await runner.run(generation.id)
                refreshed = await generations.get(generation.id)
                print("status:", refreshed.status)
                draft = await generations.get_draft(
                    refreshed.draft_id or generation.draft_id or chapter.id
                )
                chunks = await buffer.read_after(str(generation.id), 0)
                print("stream_chunks:", len(chunks))
                print("draft:", draft.content[:200])
                if not chunks:
                    raise SystemExit(1)
                if refreshed.status is not GenerationStatus.SUCCEEDED:
                    raise SystemExit(1)
        finally:
            await redis.aclose()
            await engine.dispose()
    finally:
        redis_client.shutdown()
        server.cleanup()
        shutil.rmtree(pgdata, ignore_errors=True)


if __name__ == "__main__":
    asyncio.run(main())
