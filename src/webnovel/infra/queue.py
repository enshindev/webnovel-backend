from __future__ import annotations

from typing import Protocol
from uuid import UUID

from arq import create_pool
from arq.connections import RedisSettings


class GenerationQueue(Protocol):
    async def enqueue_generation(self, generation_id: UUID) -> None: ...


class ExtractionQueue(Protocol):
    async def enqueue_extraction(self, run_id: UUID) -> None: ...


class QualityQueue(Protocol):
    async def enqueue_review(self, report_id: UUID) -> None: ...


class ExportQueue(Protocol):
    async def enqueue_export(self, job_id: UUID) -> None: ...


class AnalysisQueue(Protocol):
    async def enqueue_analysis(self, run_id: UUID) -> None: ...


class AgentQueue(Protocol):
    async def enqueue_agent(self, run_id: UUID) -> None: ...


class ChapterExtractionQueue(Protocol):
    async def enqueue_chapter_extraction(
        self, chapter_id: UUID, delay_seconds: int = 30
    ) -> None: ...


class ArqGenerationQueue:
    """S1：每次 enqueue 建一个短连接池；单用户够用，后续可注入长连接。"""

    def __init__(self, redis_url: str) -> None:
        self._redis_settings = RedisSettings.from_dsn(redis_url)

    async def enqueue_generation(self, generation_id: UUID) -> None:
        pool = await create_pool(self._redis_settings)
        try:
            await pool.enqueue_job("run_generation", str(generation_id))
        finally:
            await pool.aclose()


class ArqExtractionQueue:
    def __init__(self, redis_url: str) -> None:
        self._redis_settings = RedisSettings.from_dsn(redis_url)

    async def enqueue_extraction(self, run_id: UUID) -> None:
        pool = await create_pool(self._redis_settings)
        try:
            await pool.enqueue_job("run_extraction", str(run_id))
        finally:
            await pool.aclose()


class ArqQualityQueue:
    def __init__(self, redis_url: str) -> None:
        self._redis_settings = RedisSettings.from_dsn(redis_url)

    async def enqueue_review(self, report_id: UUID) -> None:
        pool = await create_pool(self._redis_settings)
        try:
            await pool.enqueue_job("run_quality_review", str(report_id))
        finally:
            await pool.aclose()


class ArqExportQueue:
    def __init__(self, redis_url: str) -> None:
        self._redis_settings = RedisSettings.from_dsn(redis_url)

    async def enqueue_export(self, job_id: UUID) -> None:
        pool = await create_pool(self._redis_settings)
        try:
            await pool.enqueue_job("run_export", str(job_id))
        finally:
            await pool.aclose()


class ArqChapterExtractionQueue:
    def __init__(self, redis_url: str) -> None:
        self._redis_settings = RedisSettings.from_dsn(redis_url)

    async def enqueue_chapter_extraction(self, chapter_id: UUID, delay_seconds: int = 30) -> None:
        from datetime import timedelta

        pool = await create_pool(self._redis_settings)
        try:
            await pool.enqueue_job(
                "run_chapter_extraction",
                str(chapter_id),
                _job_id=f"chapter-extract:{chapter_id}",
                _defer_by=timedelta(seconds=delay_seconds),
            )
        finally:
            await pool.aclose()


class ArqAgentQueue:
    def __init__(self, redis_url: str) -> None:
        self._redis_settings = RedisSettings.from_dsn(redis_url)

    async def enqueue_agent(self, run_id: UUID) -> None:
        pool = await create_pool(self._redis_settings)
        try:
            await pool.enqueue_job("run_agent", str(run_id))
        finally:
            await pool.aclose()


class ArqAnalysisQueue:
    def __init__(self, redis_url: str) -> None:
        self._redis_settings = RedisSettings.from_dsn(redis_url)

    async def enqueue_analysis(self, run_id: UUID) -> None:
        pool = await create_pool(self._redis_settings)
        try:
            await pool.enqueue_job("run_analysis", str(run_id))
        finally:
            await pool.aclose()


class WorkflowQueue(Protocol):
    async def enqueue_workflow(self, run_id: UUID) -> None: ...

    async def enqueue_workflow_all(self, run_id: UUID) -> None: ...


class ArqWorkflowQueue:
    def __init__(self, redis_url: str) -> None:
        self._redis_settings = RedisSettings.from_dsn(redis_url)

    async def enqueue_workflow(self, run_id: UUID) -> None:
        pool = await create_pool(self._redis_settings)
        try:
            await pool.enqueue_job("run_workflow_stage", str(run_id))
        finally:
            await pool.aclose()

    async def enqueue_workflow_all(self, run_id: UUID) -> None:
        pool = await create_pool(self._redis_settings)
        try:
            await pool.enqueue_job("run_workflow_all", str(run_id))
        finally:
            await pool.aclose()
