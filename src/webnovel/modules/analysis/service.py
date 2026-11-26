from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any
from uuid import UUID

from webnovel.kernel.errors import NotFoundError, ValidationError
from webnovel.modules.analysis.contract import (
    AnalysisRun,
    AnalysisService,
    ChapterAnalysis,
    OutlineDraft,
)
from webnovel.modules.analysis.importing import parse_manuscript, split_chapters
from webnovel.modules.analysis.repository import AnalysisRepository
from webnovel.modules.chapters_versions.contract import ChapterService
from webnovel.modules.works.contract import WorkService


class AnalysisServiceImpl(AnalysisService):
    def __init__(
        self,
        repository: AnalysisRepository,
        work_service: WorkService,
        chapter_service: ChapterService,
        enqueue: Callable[[UUID], Awaitable[None]] | None = None,
    ) -> None:
        self._repository = repository
        self._work_service = work_service
        self._chapter_service = chapter_service
        self._enqueue = enqueue

    async def start_reverse_outline(
        self, work_id: UUID, chapter_range: dict[str, int] | None = None
    ) -> AnalysisRun:
        await self._work_service.get(work_id)
        run = await self._repository.create_run(
            work_id, {"chapter_range": chapter_range} if chapter_range else {}
        )
        if self._enqueue is not None:
            await self._enqueue(run.id)
        return run

    async def get(self, run_id: UUID) -> AnalysisRun:
        run = await self._repository.get_run(run_id)
        if run is None:
            raise NotFoundError(f"analysis run not found: {run_id}", code="analysis.not_found")
        return run

    async def import_document(self, work_id: UUID, filename: str, data: bytes) -> AnalysisRun:
        await self._work_service.get(work_id)
        text = parse_manuscript(filename, data)
        chapters = split_chapters(text)
        if not chapters:
            raise ValidationError("empty manuscript", code="analysis.empty_document")
        existing = await self._chapter_service.list(work_id)
        offset = max((chapter.number for chapter in existing), default=0)
        for chapter in chapters:
            await self._chapter_service.create(
                work_id, offset + chapter.number, chapter.title, chapter.content
            )
        return await self.start_reverse_outline(work_id)

    async def list_runs(self, work_id: UUID, limit: int = 50) -> list[AnalysisRun]:
        return await self._repository.list_runs(work_id, limit)

    async def get_outline(self, run_id: UUID) -> OutlineDraft:
        run = await self.get(run_id)
        existing = await self._repository.get_outline(run_id)
        if existing is not None:
            return existing
        chapters = []
        for chapter in run.report.get("chapters", []):
            chapters.append(
                {
                    "chapter": chapter.get("chapter"),
                    "title": chapter.get("title", ""),
                    "summary": chapter.get("summary", ""),
                    "beats": chapter.get("beats", []),
                    "hook": chapter.get("hook"),
                }
            )
        return await self._repository.save_outline(
            run.id, run.work_id, {"kind": "reverse_outline", "chapters": chapters}
        )

    async def apply(self, run_id: UUID) -> OutlineDraft:
        return await self.get_outline(run_id)

    async def list_chapters(self, run_id: UUID) -> list[ChapterAnalysis]:
        await self.get(run_id)
        return await self._repository.list_chapters(run_id)

    async def update_chapter(
        self, run_id: UUID, chapter_id: UUID, values: dict[str, Any]
    ) -> ChapterAnalysis:
        await self.get(run_id)
        allowed = {
            "summary",
            "beats",
            "pov",
            "time_text",
            "characters",
            "hook",
            "hook_type",
            "boundary_confidence",
            "status",
            "progress",
        }
        filtered = {key: value for key, value in values.items() if key in allowed}
        chapter = await self._repository.update_chapter(run_id, chapter_id, filtered)
        if chapter is None:
            raise NotFoundError(
                f"chapter analysis not found: {chapter_id}", code="analysis.chapter_not_found"
            )
        return chapter

    async def split_chapter(self, run_id: UUID, chapter_id: UUID, offset: int) -> ChapterAnalysis:
        await self.get(run_id)
        if offset < 0:
            raise ValidationError("offset must be non-negative", code="analysis.invalid_offset")
        return await self.update_chapter(
            run_id,
            chapter_id,
            {"status": "needs_review", "progress": 0},
        )

    async def retry_chapter(self, run_id: UUID, chapter_id: UUID) -> ChapterAnalysis:
        chapter = await self.update_chapter(
            run_id, chapter_id, {"status": "pending", "progress": 0}
        )
        await self._repository.clear_chapters(run_id)
        await self._repository.set_status(run_id, "queued")
        if self._enqueue is not None:
            await self._enqueue(run_id)
        return chapter

    async def update_outline(
        self, run_id: UUID, content: dict[str, Any], status: str | None = None
    ) -> OutlineDraft:
        await self.get_outline(run_id)
        updated = await self._repository.update_outline(run_id, content, status)
        if updated is None:
            raise NotFoundError(f"outline not found: {run_id}", code="analysis.outline_not_found")
        return updated
