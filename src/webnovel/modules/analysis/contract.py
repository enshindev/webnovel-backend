from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID

from webnovel.modules.chapters_versions.contract import Chapter


@dataclass(frozen=True, slots=True)
class OutlineDraft:
    id: UUID
    work_id: UUID
    analysis_run_id: UUID | None
    status: str
    content: dict[str, Any]


@dataclass(frozen=True, slots=True)
class AnalysisRun:
    id: UUID
    work_id: UUID
    kind: str
    status: str
    params: dict[str, Any]
    report: dict[str, Any]
    error: str | None
    created_at: datetime


@dataclass(frozen=True, slots=True)
class ChapterAnalysis:
    id: UUID
    run_id: UUID
    chapter_id: UUID
    version_id: UUID | None
    summary: str
    beats: list[dict[str, Any]]
    pov: str | None
    time_text: str | None
    characters: list[str]
    hook: str | None
    hook_type: str | None
    issues: list[dict[str, Any]]
    status: str
    progress: int
    boundary_confidence: float | None


@dataclass(frozen=True, slots=True)
class SplitChapterResult:
    first: Chapter
    second: Chapter


class AnalysisService(Protocol):
    async def start_reverse_outline(
        self, work_id: UUID, chapter_range: dict[str, int] | None = None
    ) -> AnalysisRun: ...

    async def get(self, run_id: UUID) -> AnalysisRun: ...

    async def list_runs(self, work_id: UUID, limit: int = 50) -> list[AnalysisRun]: ...

    async def import_document(self, work_id: UUID, filename: str, data: bytes) -> AnalysisRun: ...

    async def get_outline(self, run_id: UUID) -> OutlineDraft: ...

    async def apply(self, run_id: UUID) -> OutlineDraft: ...

    async def update_outline(
        self, run_id: UUID, content: dict[str, Any], status: str | None = None
    ) -> OutlineDraft: ...

    async def list_chapters(self, run_id: UUID) -> list[ChapterAnalysis]: ...

    async def update_chapter(
        self, run_id: UUID, chapter_id: UUID, values: dict[str, Any]
    ) -> ChapterAnalysis: ...

    async def retry_chapter(self, run_id: UUID, chapter_id: UUID) -> ChapterAnalysis: ...

    async def split_chapter(
        self, run_id: UUID, chapter_id: UUID, offset: int
    ) -> SplitChapterResult: ...
