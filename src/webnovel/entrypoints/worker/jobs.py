from __future__ import annotations

from uuid import UUID

import structlog

from webnovel.experiments.multimodal.factory import (
    build_cover_provider,
    build_speech_provider,
    build_transcription_provider,
)
from webnovel.infra.config import get_settings
from webnovel.infra.db.session import session_factory
from webnovel.infra.queue import ArqExtractionQueue
from webnovel.infra.redis import create_redis
from webnovel.infra.streams import RedisStreamBuffer
from webnovel.llm.embeddings.factory import build_embedding_client
from webnovel.llm.gateway.factory import build_model_client
from webnovel.llm.rerank.factory import build_reranker
from webnovel.modules.agent.executor import AgentExecutor
from webnovel.modules.agent.repository import SqlAlchemyAgentRepository
from webnovel.modules.analysis.repository import SqlAlchemyAnalysisRepository
from webnovel.modules.analysis.runner import AnalysisRunner
from webnovel.modules.assistant.knowledge import KnowledgeIndexer, KnowledgeRetriever
from webnovel.modules.assistant.knowledge_repository import SqlAlchemyKnowledgeRepository
from webnovel.modules.assistant.tools import AssistantTools
from webnovel.modules.audit.repository import SqlAlchemyAuditRepository
from webnovel.modules.audit.service import AuditServiceImpl
from webnovel.modules.chapters_versions.repository import SqlAlchemyChapterRepository
from webnovel.modules.chapters_versions.service import ChaptersService
from webnovel.modules.export.cleanup import cleanup_exports
from webnovel.modules.export.repository import SqlAlchemyExportRepository
from webnovel.modules.export.runner import ExportRunner
from webnovel.modules.generation.repository import (
    SqlAlchemyGenerationRepository,
    delete_expired_idempotency_keys,
)
from webnovel.modules.generation.runner import GenerationRunner
from webnovel.modules.library.repository import SqlAlchemyLibraryRepository
from webnovel.modules.library.service import LibraryServiceImpl
from webnovel.modules.memory.chapter_embedding_repository import (
    SqlAlchemyChapterEmbeddingRepository,
)
from webnovel.modules.memory.embedding_repository import SqlAlchemyEmbeddingRepository
from webnovel.modules.memory.extraction import ExtractionRunner
from webnovel.modules.memory.repository import SqlAlchemyMemoryRepository
from webnovel.modules.memory.retrieval import MemoryVectorService
from webnovel.modules.memory.service import MemoryServiceImpl
from webnovel.modules.outbox.dispatcher import dispatch_once
from webnovel.modules.quality.repository import SqlAlchemyQualityRepository
from webnovel.modules.quality.review import QualityReviewRunner
from webnovel.modules.style.repository import SqlAlchemyStyleRepository
from webnovel.modules.style.service import StyleServiceImpl
from webnovel.modules.usage.pricing import load_pricing
from webnovel.modules.usage.repository import SqlAlchemyUsageRepository
from webnovel.modules.usage.service import UsageServiceImpl
from webnovel.modules.workflow.auto import WorkflowAutoRunner
from webnovel.modules.workflow.executor import WorkflowExecutor
from webnovel.modules.workflow.repository import SqlAlchemyWorkflowRepository
from webnovel.modules.workflow.service import WorkflowServiceImpl
from webnovel.modules.works.repository import SqlAlchemyWorkRepository
from webnovel.modules.works.service import WorksService

logger = structlog.get_logger(__name__)


async def run_generation(ctx: object, generation_id: str) -> None:
    _ = ctx
    settings = get_settings()
    redis = create_redis()
    buffer = RedisStreamBuffer(redis)
    try:
        async with session_factory() as session, session.begin():
            work_service = WorksService(SqlAlchemyWorkRepository(session))
            chapter_service = ChaptersService(SqlAlchemyChapterRepository(session), work_service)
            usage = UsageServiceImpl(
                SqlAlchemyUsageRepository(session),
                load_pricing(settings.pricing_config_path),
            )
            embedding_client = build_embedding_client(settings)
            retrieval = (
                MemoryVectorService(
                    client=embedding_client,
                    repository=SqlAlchemyEmbeddingRepository(session),
                    model_name=settings.embedding_model,
                    chapter_repository=SqlAlchemyChapterEmbeddingRepository(session),
                    usage=usage,
                    reranker=build_reranker(settings),
                )
                if embedding_client is not None
                else None
            )
            style_service = StyleServiceImpl(SqlAlchemyStyleRepository(session), chapter_service)
            runner = GenerationRunner(
                repository=SqlAlchemyGenerationRepository(session),
                chapter_service=chapter_service,
                model_client=build_model_client(settings),
                settings=settings,
                buffer=buffer,
                retrieval=retrieval,
                style_reader=style_service,
                usage=usage,
            )
            await runner.run(UUID(generation_id))
    finally:
        await redis.aclose()


async def run_extraction(ctx: object, run_id: str) -> None:
    _ = ctx
    settings = get_settings()
    async with session_factory() as session, session.begin():
        work_service = WorksService(SqlAlchemyWorkRepository(session))
        chapter_service = ChaptersService(SqlAlchemyChapterRepository(session), work_service)
        usage = UsageServiceImpl(
            SqlAlchemyUsageRepository(session),
            load_pricing(settings.pricing_config_path),
        )
        embedding_client = build_embedding_client(settings)
        indexer = (
            MemoryVectorService(
                client=embedding_client,
                repository=SqlAlchemyEmbeddingRepository(session),
                model_name=settings.embedding_model,
                chapter_repository=SqlAlchemyChapterEmbeddingRepository(session),
                usage=usage,
                reranker=build_reranker(settings),
            )
            if embedding_client is not None
            else None
        )
        runner = ExtractionRunner(
            repository=SqlAlchemyMemoryRepository(session),
            chapter_service=chapter_service,
            model_client=build_model_client(settings, profile="batch"),
            settings=settings,
            indexer=indexer,
            usage=usage,
        )
        await runner.run(UUID(run_id))


async def run_quality_review(ctx: object, report_id: str) -> None:
    _ = ctx
    settings = get_settings()
    async with session_factory() as session, session.begin():
        work_service = WorksService(SqlAlchemyWorkRepository(session))
        chapter_service = ChaptersService(SqlAlchemyChapterRepository(session), work_service)
        usage = UsageServiceImpl(
            SqlAlchemyUsageRepository(session),
            load_pricing(settings.pricing_config_path),
        )
        runner = QualityReviewRunner(
            repository=SqlAlchemyQualityRepository(session),
            chapter_service=chapter_service,
            model_client=build_model_client(settings, profile="batch"),
            settings=settings,
            usage=usage,
        )
        await runner.run(UUID(report_id))


async def run_export(ctx: object, job_id: str) -> None:
    _ = ctx
    settings = get_settings()
    async with session_factory() as session, session.begin():
        work_service = WorksService(SqlAlchemyWorkRepository(session))
        chapter_service = ChaptersService(SqlAlchemyChapterRepository(session), work_service)
        usage = UsageServiceImpl(
            SqlAlchemyUsageRepository(session),
            load_pricing(settings.pricing_config_path),
        )
        runner = ExportRunner(
            repository=SqlAlchemyExportRepository(session),
            chapter_service=chapter_service,
            work_service=work_service,
            settings=settings,
            speech=build_speech_provider(settings),
            cover=build_cover_provider(settings),
            usage=usage,
        )
        await runner.run(UUID(job_id))


async def run_export_cleanup(ctx: object) -> None:
    _ = ctx
    async with session_factory() as session, session.begin():
        await cleanup_exports(SqlAlchemyExportRepository(session))


async def run_chapter_extraction(ctx: object, chapter_id: str) -> None:
    _ = ctx
    settings = get_settings()
    async with session_factory() as session, session.begin():
        work_service = WorksService(SqlAlchemyWorkRepository(session))
        chapter_service = ChaptersService(SqlAlchemyChapterRepository(session), work_service)
        chapter = await chapter_service.get(UUID(chapter_id))
        if chapter.current_version_id is None:
            return
        memory = MemoryServiceImpl(
            SqlAlchemyMemoryRepository(session),
            ArqExtractionQueue(settings.redis_url).enqueue_extraction,
        )
        await memory.start_extraction(chapter.work_id, chapter.id, chapter.current_version_id)


async def run_agent(ctx: object, run_id: str) -> None:
    _ = ctx
    settings = get_settings()
    async with session_factory() as session, session.begin():
        usage = UsageServiceImpl(
            SqlAlchemyUsageRepository(session),
            load_pricing(settings.pricing_config_path),
        )
        embedding_client = build_embedding_client(settings)
        retrieval = (
            MemoryVectorService(
                client=embedding_client,
                repository=SqlAlchemyEmbeddingRepository(session),
                model_name=settings.embedding_model,
                chapter_repository=SqlAlchemyChapterEmbeddingRepository(session),
                usage=usage,
                reranker=build_reranker(settings),
            )
            if embedding_client is not None
            else None
        )
        memory_repository = SqlAlchemyMemoryRepository(session)
        tools = AssistantTools(
            retrieval=retrieval,
            memory_repository=memory_repository,
            story_state=MemoryServiceImpl(memory_repository),
            library=(
                LibraryServiceImpl(
                    SqlAlchemyLibraryRepository(session),
                    settings,
                    embedding_client,
                    usage,
                    build_reranker(settings),
                    build_transcription_provider(settings),
                )
                if settings.assistant_library_search_enabled
                else None
            ),
        )
        executor = AgentExecutor(
            repository=SqlAlchemyAgentRepository(session),
            model_client=build_model_client(settings),
            settings=settings,
            usage=usage,
            tools=tools,
        )
        await executor.run(UUID(run_id))


async def run_outbox_dispatch(ctx: object) -> None:
    _ = ctx
    async with session_factory() as session, session.begin():
        audit = AuditServiceImpl(SqlAlchemyAuditRepository(session))
        await dispatch_once(session, audit=audit)


async def run_knowledge_index(ctx: object) -> None:
    _ = ctx
    settings = get_settings()
    embedding_client = build_embedding_client(settings)
    if embedding_client is None:
        return
    async with session_factory() as session, session.begin():
        indexer = KnowledgeIndexer(embedding_client, SqlAlchemyKnowledgeRepository(session))
        await indexer.index(KnowledgeRetriever(settings.knowledge_dir))


async def run_analysis(ctx: object, run_id: str) -> None:
    _ = ctx
    settings = get_settings()
    async with session_factory() as session, session.begin():
        work_service = WorksService(SqlAlchemyWorkRepository(session))
        chapter_service = ChaptersService(SqlAlchemyChapterRepository(session), work_service)
        usage = UsageServiceImpl(
            SqlAlchemyUsageRepository(session),
            load_pricing(settings.pricing_config_path),
        )
        runner = AnalysisRunner(
            repository=SqlAlchemyAnalysisRepository(session),
            chapter_service=chapter_service,
            model_client=build_model_client(settings, profile="batch")
            if settings.llm_model and settings.llm_base_url
            else None,
            settings=settings,
            usage=usage,
        )
        await runner.run(UUID(run_id))


async def run_workflow_stage(ctx: object, run_id: str) -> None:
    _ = ctx
    settings = get_settings()
    async with session_factory() as session, session.begin():
        work_service = WorksService(SqlAlchemyWorkRepository(session))
        usage = UsageServiceImpl(
            SqlAlchemyUsageRepository(session),
            load_pricing(settings.pricing_config_path),
        )
        executor = WorkflowExecutor(
            repository=SqlAlchemyWorkflowRepository(session),
            work_service=work_service,
            model_client=build_model_client(settings),
            settings=settings,
            usage=usage,
        )
        await executor.execute(UUID(run_id))


async def run_workflow_all(ctx: object, run_id: str) -> None:
    _ = ctx
    settings = get_settings()
    async with session_factory() as session, session.begin():
        work_service = WorksService(SqlAlchemyWorkRepository(session))
        usage = UsageServiceImpl(
            SqlAlchemyUsageRepository(session),
            load_pricing(settings.pricing_config_path),
        )
        executor = WorkflowExecutor(
            repository=SqlAlchemyWorkflowRepository(session),
            work_service=work_service,
            model_client=build_model_client(settings),
            settings=settings,
            usage=usage,
        )
        service = WorkflowServiceImpl(SqlAlchemyWorkflowRepository(session), work_service)
        await WorkflowAutoRunner(executor, service).run_all(run_id)


async def run_idempotency_cleanup(ctx: object) -> None:
    _ = ctx
    async with session_factory() as session, session.begin():
        deleted = await delete_expired_idempotency_keys(session)
    logger.info("idempotency.cleanup", deleted=deleted)
