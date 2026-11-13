from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID


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
