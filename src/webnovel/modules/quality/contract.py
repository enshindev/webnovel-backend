from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID


@dataclass(frozen=True, slots=True)
class EvalRunInfo:
    id: UUID
    task: str
    prompt_name: str | None
    prompt_version: int | None
    status: str
    metrics: dict[str, Any]


@dataclass(frozen=True, slots=True)
class QualityIssue:
    code: str
    severity: str
    message: str
    location: dict[str, Any] | None = None
    suggestion: str | None = None


@dataclass(frozen=True, slots=True)
class QualityReport:
    id: UUID
    work_id: UUID
    chapter_id: UUID
    version_id: UUID
    status: str
    score: int
    issues: list[QualityIssue]
    metrics: dict[str, Any]
    created_at: datetime
    stage: str = "chapter"


class QualityService(Protocol):
    async def check_chapter(self, work_id: UUID, chapter_id: UUID) -> QualityReport: ...

    async def start_review(self, work_id: UUID, chapter_id: UUID) -> QualityReport: ...

    async def get_report(self, report_id: UUID) -> QualityReport: ...

    async def list_reports(self, work_id: UUID) -> list[QualityReport]: ...
