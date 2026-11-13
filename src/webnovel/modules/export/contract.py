from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Protocol
from uuid import UUID


class ExportStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    EXPIRED = "expired"


@dataclass(frozen=True, slots=True)
class GateIssue:
    code: str
    severity: str
    message: str
    chapter_id: UUID | None = None


@dataclass(frozen=True, slots=True)
class GateResult:
    blocking: list[GateIssue] = field(default_factory=list)
    warnings: list[GateIssue] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class ExportJob:
    id: UUID
    work_id: UUID
    format: str
    status: ExportStatus
    file_path: str | None
    created_at: datetime
    download_token: str | None = None
    expires_at: datetime | None = None


class ExportService(Protocol):
    async def create(self, work_id: UUID, fmt: str) -> ExportJob: ...

    async def get(self, job_id: UUID) -> ExportJob: ...
