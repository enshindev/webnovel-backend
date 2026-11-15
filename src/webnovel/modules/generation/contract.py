from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any, Protocol
from uuid import UUID

from webnovel.modules.chapters_versions.contract import ChapterVersion

MAX_CANDIDATE_COUNT = 4


class TaskType(StrEnum):
    CONTINUE = "continue"
    REWRITE = "rewrite"
    EXPAND = "expand"
    POLISH = "polish"
    OUTLINE = "outline"
    SUMMARY = "summary"
    EXTRACTION = "extraction"
    QUALITY = "quality"


class GenerationStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    STREAMING = "streaming"
    CANCELLING = "cancelling"
    CANCELLED = "cancelled"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    EXPIRED = "expired"


class DraftStatus(StrEnum):
    GENERATING = "generating"
    READY = "ready"
    PARTIAL = "partial"
    ACCEPTED = "accepted"
    DISCARDED = "discarded"


ACTIVE_STATUSES = {
    GenerationStatus.QUEUED,
    GenerationStatus.RUNNING,
    GenerationStatus.STREAMING,
    GenerationStatus.CANCELLING,
}

TERMINAL = {
    GenerationStatus.CANCELLED,
    GenerationStatus.SUCCEEDED,
    GenerationStatus.FAILED,
    GenerationStatus.EXPIRED,
}


@dataclass(frozen=True, slots=True)
class Generation:
    id: UUID
    work_id: UUID
    chapter_id: UUID
    task_type: TaskType
    status: GenerationStatus
    draft_id: UUID | None
    prompt_name: str | None
    prompt_version: int | None
    instruction: str | None
    target_words: int | None
    created_at: datetime
    prompt_snapshot: dict[str, Any] | None = None
    context_snapshot: dict[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class Draft:
    id: UUID
    generation_id: UUID
    chapter_id: UUID
    content: str
    status: DraftStatus
    candidate_index: int = 0


@dataclass(frozen=True, slots=True)
class GenerationCreate:
    work_id: UUID
    chapter_id: UUID
    task_type: TaskType
    instruction: str | None = None
    target_words: int | None = None
    candidate_count: int = 1


@dataclass(frozen=True, slots=True)
class AcceptedDraft:
    draft: Draft
    chapter_version: ChapterVersion


class GenerationService(Protocol):
    async def create(self, command: GenerationCreate, idempotency_key: str) -> Generation: ...

    async def get(self, generation_id: UUID) -> Generation: ...

    async def cancel(self, generation_id: UUID) -> Generation: ...

    async def get_draft(self, draft_id: UUID) -> Draft: ...

    async def list_drafts(self, generation_id: UUID) -> list[Draft]: ...

    async def retry(self, generation_id: UUID) -> Generation: ...

    async def discard_draft(self, draft_id: UUID) -> Draft: ...

    async def accept_draft(self, draft_id: UUID, base_version: int) -> AcceptedDraft: ...
