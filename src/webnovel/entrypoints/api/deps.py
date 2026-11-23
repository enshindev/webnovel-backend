from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated, Any
from uuid import UUID

import structlog
from fastapi import Depends
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from webnovel.infra.config import Settings, get_settings
from webnovel.infra.db.session import get_session
from webnovel.infra.queue import (
    ArqAgentQueue,
    ArqAnalysisQueue,
    ArqChapterExtractionQueue,
    ArqExportQueue,
    ArqExtractionQueue,
    ArqGenerationQueue,
    ArqQualityQueue,
    ArqWorkflowQueue,
    ChapterExtractionQueue,
    WorkflowQueue,
)
from webnovel.infra.redis import create_redis
from webnovel.llm.embeddings.factory import build_embedding_client
from webnovel.llm.gateway.factory import build_model_client
from webnovel.llm.rerank.factory import build_reranker
from webnovel.modules.agent.contract import AgentService
from webnovel.modules.agent.repository import SqlAlchemyAgentRepository
from webnovel.modules.agent.service import AgentServiceImpl
from webnovel.modules.analysis.contract import AnalysisService
from webnovel.modules.analysis.repository import SqlAlchemyAnalysisRepository
from webnovel.modules.analysis.service import AnalysisServiceImpl
from webnovel.modules.assistant.chat import AssistantChatRunner
from webnovel.modules.assistant.contract import AssistantService
from webnovel.modules.assistant.knowledge import KnowledgeRetriever, KnowledgeSearchService
from webnovel.modules.assistant.knowledge_repository import SqlAlchemyKnowledgeRepository
from webnovel.modules.assistant.repository import SqlAlchemyAssistantRepository
from webnovel.modules.assistant.service import AssistantServiceImpl
from webnovel.modules.assistant.tools import AssistantTools
from webnovel.modules.audit.contract import AuditService
from webnovel.modules.audit.repository import SqlAlchemyAuditRepository
from webnovel.modules.audit.service import AuditServiceImpl
from webnovel.modules.chapters_versions.contract import ChapterService
from webnovel.modules.chapters_versions.repository import SqlAlchemyChapterRepository
from webnovel.modules.chapters_versions.service import ChaptersService
from webnovel.modules.export.contract import ExportService
from webnovel.modules.export.repository import SqlAlchemyExportRepository
from webnovel.modules.export.service import ExportServiceImpl
from webnovel.modules.generation.contract import GenerationService
from webnovel.modules.generation.preference import SqlAlchemyPreferenceRecorder
from webnovel.modules.generation.repository import SqlAlchemyGenerationRepository
from webnovel.modules.generation.service import GenerationsService
from webnovel.modules.library.contract import LibraryService
from webnovel.modules.library.repository import SqlAlchemyLibraryRepository
from webnovel.modules.library.service import LibraryServiceImpl
from webnovel.modules.memory.chapter_embedding_repository import (
    SqlAlchemyChapterEmbeddingRepository,
)
from webnovel.modules.memory.contract import MemoryService
from webnovel.modules.memory.embedding_repository import SqlAlchemyEmbeddingRepository
from webnovel.modules.memory.materializer import EntityMaterializerImpl
from webnovel.modules.memory.repository import SqlAlchemyMemoryRepository
from webnovel.modules.memory.retrieval import MemoryVectorService
from webnovel.modules.memory.service import MemoryServiceImpl
from webnovel.modules.outbox.contract import OutboxService
from webnovel.modules.outbox.repository import SqlAlchemyOutboxRepository
from webnovel.modules.outbox.service import OutboxServiceImpl
from webnovel.modules.quality.contract import QualityService
from webnovel.modules.quality.repository import SqlAlchemyQualityRepository
from webnovel.modules.quality.rules import load_platform_rules
from webnovel.modules.quality.service import QualityServiceImpl
from webnovel.modules.settings.contract import SettingsService
from webnovel.modules.settings.repository import SqlAlchemySettingsRepository
from webnovel.modules.settings.service import SettingsServiceImpl
from webnovel.modules.style.contract import StyleService
from webnovel.modules.style.repository import SqlAlchemyStyleRepository
from webnovel.modules.style.service import StyleServiceImpl
from webnovel.modules.usage.alert_repository import SqlAlchemyBudgetAlertRepository
from webnovel.modules.usage.alert_service import BudgetAlertService
from webnovel.modules.usage.budget import BudgetGuard
from webnovel.modules.usage.contract import UsageService
from webnovel.modules.usage.pricing import load_pricing
from webnovel.modules.usage.repository import SqlAlchemyUsageRepository
from webnovel.modules.usage.service import UsageServiceImpl
from webnovel.modules.volumes.contract import VolumeService
from webnovel.modules.volumes.repository import SqlAlchemyVolumeRepository
from webnovel.modules.volumes.service import VolumeServiceImpl
from webnovel.modules.workflow.contract import WorkflowService
from webnovel.modules.workflow.executor import WorkflowExecutor
from webnovel.modules.workflow.repository import SqlAlchemyWorkflowRepository
from webnovel.modules.workflow.service import WorkflowServiceImpl
from webnovel.modules.works.contract import WorkService
from webnovel.modules.works.repository import SqlAlchemyWorkRepository
from webnovel.modules.works.service import WorksService

logger = structlog.get_logger(__name__)

SettingsDep = Annotated[Settings, Depends(get_settings)]
SessionDep = Annotated[AsyncSession, Depends(get_session)]


def require_assistant(settings: SettingsDep) -> None:
    if not settings.assistant_enabled:
        from webnovel.kernel.errors import NotFoundError

        raise NotFoundError("assistant is disabled", code="assistant.disabled")


async def get_redis() -> AsyncIterator[Redis]:
    client = create_redis()
    try:
        yield client
    finally:
        await client.aclose()


RedisDep = Annotated[Redis, Depends(get_redis)]


def get_chapter_extraction_queue(settings: SettingsDep) -> ChapterExtractionQueue:
    return ArqChapterExtractionQueue(settings.redis_url)


def get_audit_service(session: SessionDep) -> AuditService:
    return AuditServiceImpl(SqlAlchemyAuditRepository(session))


def get_library_service(session: SessionDep, settings: SettingsDep) -> LibraryService:
    from webnovel.experiments.multimodal.factory import build_transcription_provider

    embedding_client = build_embedding_client(settings)
    usage = UsageServiceImpl(
        SqlAlchemyUsageRepository(session), load_pricing(settings.pricing_config_path)
    )
    return LibraryServiceImpl(
        SqlAlchemyLibraryRepository(session),
        settings,
        embedding_client,
        usage,
        build_reranker(settings),
        build_transcription_provider(settings),
        settings.enable_experiments,
    )


def get_outbox_service(session: SessionDep) -> OutboxService:
    return OutboxServiceImpl(SqlAlchemyOutboxRepository(session))


def get_agent_service(session: SessionDep, settings: SettingsDep) -> AgentService:
    return AgentServiceImpl(
        SqlAlchemyAgentRepository(session),
        ArqAgentQueue(settings.redis_url).enqueue_agent,
    )


def get_work_service(
    session: SessionDep,
    audit: Annotated[AuditService, Depends(get_audit_service)],
) -> WorkService:
    return WorksService(SqlAlchemyWorkRepository(session), audit)


def get_analysis_service(
    session: SessionDep,
    work_service: Annotated[WorkService, Depends(get_work_service)],
    chapter_service: Annotated[ChapterService, Depends(get_chapter_service)],
    settings: SettingsDep,
) -> AnalysisService:
    return AnalysisServiceImpl(
        SqlAlchemyAnalysisRepository(session),
        work_service,
        chapter_service,
        ArqAnalysisQueue(settings.redis_url).enqueue_analysis,
    )


def get_volume_service(
    session: SessionDep,
    work_service: Annotated[WorkService, Depends(get_work_service)],
) -> VolumeService:
    return VolumeServiceImpl(SqlAlchemyVolumeRepository(session), work_service)


def get_workflow_service(
    session: SessionDep,
    work_service: Annotated[WorkService, Depends(get_work_service)],
) -> WorkflowService:
    return WorkflowServiceImpl(SqlAlchemyWorkflowRepository(session), work_service)


def get_workflow_queue(settings: SettingsDep) -> WorkflowQueue:
    return ArqWorkflowQueue(settings.redis_url)


def get_workflow_executor(
    session: SessionDep,
    work_service: Annotated[WorkService, Depends(get_work_service)],
    settings: SettingsDep,
) -> WorkflowExecutor:
    usage = UsageServiceImpl(
        SqlAlchemyUsageRepository(session), load_pricing(settings.pricing_config_path)
    )
    return WorkflowExecutor(
        repository=SqlAlchemyWorkflowRepository(session),
        work_service=work_service,
        model_client=build_model_client(settings),
        settings=settings,
        usage=usage,
    )


def get_chapter_service(
    session: SessionDep, work_service: Annotated[WorkService, Depends(get_work_service)]
) -> ChapterService:
    volume_service = VolumeServiceImpl(SqlAlchemyVolumeRepository(session), work_service)
    preference = SqlAlchemyPreferenceRecorder(session)
    return ChaptersService(
        SqlAlchemyChapterRepository(session),
        work_service,
        volume_service,
        on_saved=preference.edited_after_accept,
    )


def get_settings_service(session: SessionDep) -> SettingsService:
    return SettingsServiceImpl(SqlAlchemySettingsRepository(session))


def get_memory_service(session: SessionDep, settings: SettingsDep) -> MemoryService:
    queue = ArqExtractionQueue(settings.redis_url)
    embedding_client = build_embedding_client(settings)
    reranker = build_reranker(settings)
    usage = UsageServiceImpl(
        SqlAlchemyUsageRepository(session), load_pricing(settings.pricing_config_path)
    )
    indexer = (
        MemoryVectorService(
            client=embedding_client,
            repository=SqlAlchemyEmbeddingRepository(session),
            model_name=settings.embedding_model,
            chapter_repository=SqlAlchemyChapterEmbeddingRepository(session),
            usage=usage,
            reranker=reranker,
        )
        if embedding_client is not None
        else None
    )
    return MemoryServiceImpl(SqlAlchemyMemoryRepository(session), queue.enqueue_extraction, indexer)


def get_multimodal_service(session: SessionDep, settings: SettingsDep) -> Any:
    from webnovel.experiments.multimodal.factory import build_multimodal_service

    usage = UsageServiceImpl(
        SqlAlchemyUsageRepository(session), load_pricing(settings.pricing_config_path)
    )
    return build_multimodal_service(settings, usage)


def get_graphrag_service(
    memory: Annotated[MemoryService, Depends(get_memory_service)],
) -> Any:
    from webnovel.experiments.graphrag.service import GraphRagService

    return GraphRagService(memory)


def get_assistant_service(
    session: SessionDep,
    work_service: Annotated[WorkService, Depends(get_work_service)],
    chapter_service: Annotated[ChapterService, Depends(get_chapter_service)],
    audit: Annotated[AuditService, Depends(get_audit_service)],
    outbox: Annotated[OutboxService, Depends(get_outbox_service)],
    settings: SettingsDep,
) -> AssistantService:
    repository = SqlAlchemyAssistantRepository(session)
    usage = UsageServiceImpl(
        SqlAlchemyUsageRepository(session), load_pricing(settings.pricing_config_path)
    )
    memory_repository = SqlAlchemyMemoryRepository(session)
    embedding_client = build_embedding_client(settings)
    reranker = build_reranker(settings)
    retrieval = (
        MemoryVectorService(
            client=embedding_client,
            repository=SqlAlchemyEmbeddingRepository(session),
            model_name=settings.embedding_model,
            chapter_repository=SqlAlchemyChapterEmbeddingRepository(session),
            usage=usage,
            reranker=reranker,
        )
        if embedding_client is not None
        else None
    )
    from webnovel.experiments.multimodal.factory import build_transcription_provider

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
                reranker,
                build_transcription_provider(settings),
            )
            if settings.assistant_library_search_enabled
            else None
        ),
    )
    knowledge_store = (
        KnowledgeSearchService(embedding_client, SqlAlchemyKnowledgeRepository(session))
        if embedding_client is not None
        else None
    )
    chat = None
    if settings.llm_model and settings.llm_base_url:
        chat = AssistantChatRunner(
            repository=repository,
            work_service=work_service,
            chapter_service=chapter_service,
            model_client=build_model_client(settings),
            settings=settings,
            usage=usage,
            tools=tools,
            knowledge=KnowledgeRetriever(settings.knowledge_dir, embedding_client),
            knowledge_store=knowledge_store,
        )
    return AssistantServiceImpl(
        repository,
        work_service,
        EntityMaterializerImpl(session),
        chat,
        audit,
        outbox,
        SqlAlchemyPreferenceRecorder(session),
    )


def get_style_service(
    session: SessionDep,
    chapter_service: Annotated[ChapterService, Depends(get_chapter_service)],
    settings: SettingsDep,
) -> StyleService:
    model_client = (
        build_model_client(settings) if settings.llm_model and settings.llm_base_url else None
    )
    usage = UsageServiceImpl(
        SqlAlchemyUsageRepository(session), load_pricing(settings.pricing_config_path)
    )
    return StyleServiceImpl(
        SqlAlchemyStyleRepository(session),
        chapter_service,
        model_client,
        settings,
        usage,
    )


def get_quality_service(
    session: SessionDep,
    chapter_service: Annotated[ChapterService, Depends(get_chapter_service)],
    audit: Annotated[AuditService, Depends(get_audit_service)],
    outbox: Annotated[OutboxService, Depends(get_outbox_service)],
    settings: SettingsDep,
) -> QualityService:
    queue = ArqQualityQueue(settings.redis_url)
    memory = MemoryServiceImpl(SqlAlchemyMemoryRepository(session))
    return QualityServiceImpl(
        SqlAlchemyQualityRepository(session),
        chapter_service,
        load_platform_rules(settings.platform_config_path),
        queue.enqueue_review,
        audit,
        outbox,
        memory.contradictions if settings.story_state_contradictions_in_quality else None,
    )


def get_usage_service(session: SessionDep, settings: SettingsDep) -> UsageService:
    return UsageServiceImpl(
        SqlAlchemyUsageRepository(session), load_pricing(settings.pricing_config_path)
    )


def get_budget_alert_service(session: SessionDep) -> BudgetAlertService:
    return BudgetAlertService(SqlAlchemyBudgetAlertRepository(session))


def get_budget_guard(
    usage: Annotated[UsageService, Depends(get_usage_service)],
    alerts: Annotated[BudgetAlertService, Depends(get_budget_alert_service)],
    settings: SettingsDep,
) -> BudgetGuard:
    return BudgetGuard(usage, settings.daily_budget, alerts.record)


def get_export_service(
    session: SessionDep,
    chapter_service: Annotated[ChapterService, Depends(get_chapter_service)],
    quality_service: Annotated[QualityService, Depends(get_quality_service)],
    work_service: Annotated[WorkService, Depends(get_work_service)],
    audit: Annotated[AuditService, Depends(get_audit_service)],
    outbox: Annotated[OutboxService, Depends(get_outbox_service)],
    settings: SettingsDep,
) -> ExportService:
    from webnovel.experiments.multimodal.factory import (
        build_cover_provider,
        build_speech_provider,
    )

    queue = ArqExportQueue(settings.redis_url)
    return ExportServiceImpl(
        SqlAlchemyExportRepository(session),
        chapter_service=chapter_service,
        quality_service=quality_service,
        work_service=work_service,
        enqueue=queue.enqueue_export,
        audit=audit,
        outbox=outbox,
        speech=build_speech_provider(settings),
        cover=build_cover_provider(settings),
    )


def get_generation_service(
    session: SessionDep,
    chapter_service: Annotated[ChapterService, Depends(get_chapter_service)],
    memory_service: Annotated[MemoryService, Depends(get_memory_service)],
    quality_service: Annotated[QualityService, Depends(get_quality_service)],
    audit: Annotated[AuditService, Depends(get_audit_service)],
    outbox: Annotated[OutboxService, Depends(get_outbox_service)],
    settings: SettingsDep,
) -> GenerationService:
    queue = ArqGenerationQueue(settings.redis_url)

    async def on_accepted(work_id: UUID, chapter_id: UUID, version_id: UUID) -> None:
        try:
            await memory_service.start_extraction(work_id, chapter_id, version_id)
        except Exception:
            logger.exception("memory.enqueue_failed", chapter_id=str(chapter_id))
        try:
            await quality_service.check_chapter(work_id, chapter_id)
        except Exception:
            logger.exception("quality.check_failed", chapter_id=str(chapter_id))

    return GenerationsService(
        SqlAlchemyGenerationRepository(session),
        chapter_service,
        queue.enqueue_generation,
        on_accepted,
        audit,
        outbox,
    )


WorkServiceDep = Annotated[WorkService, Depends(get_work_service)]
ChapterServiceDep = Annotated[ChapterService, Depends(get_chapter_service)]
GenerationServiceDep = Annotated[GenerationService, Depends(get_generation_service)]
MemoryServiceDep = Annotated[MemoryService, Depends(get_memory_service)]
GraphRagServiceDep = Annotated[Any, Depends(get_graphrag_service)]
MultimodalServiceDep = Annotated[Any, Depends(get_multimodal_service)]
AuditServiceDep = Annotated[AuditService, Depends(get_audit_service)]
AnalysisServiceDep = Annotated[AnalysisService, Depends(get_analysis_service)]
LibraryServiceDep = Annotated[LibraryService, Depends(get_library_service)]
WorkflowQueueDep = Annotated[WorkflowQueue, Depends(get_workflow_queue)]
WorkflowExecutorDep = Annotated[WorkflowExecutor, Depends(get_workflow_executor)]
WorkflowServiceDep = Annotated[WorkflowService, Depends(get_workflow_service)]
VolumeServiceDep = Annotated[VolumeService, Depends(get_volume_service)]
ChapterExtractionQueueDep = Annotated[ChapterExtractionQueue, Depends(get_chapter_extraction_queue)]
AgentServiceDep = Annotated[AgentService, Depends(get_agent_service)]
QualityServiceDep = Annotated[QualityService, Depends(get_quality_service)]
StyleServiceDep = Annotated[StyleService, Depends(get_style_service)]
AssistantServiceDep = Annotated[AssistantService, Depends(get_assistant_service)]
ExportServiceDep = Annotated[ExportService, Depends(get_export_service)]
UsageServiceDep = Annotated[UsageService, Depends(get_usage_service)]
BudgetGuardDep = Annotated[BudgetGuard, Depends(get_budget_guard)]
BudgetAlertServiceDep = Annotated[BudgetAlertService, Depends(get_budget_alert_service)]
SettingsServiceDep = Annotated[SettingsService, Depends(get_settings_service)]
