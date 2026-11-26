from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True, slots=True)
class Chapter:
    id: UUID
    work_id: UUID
    number: int
    title: str
    current_version_id: UUID | None
    lock_version: int
    word_count: int
    created_at: datetime
    updated_at: datetime
    volume_id: UUID | None = None


@dataclass(frozen=True, slots=True)
class ChapterVersion:
    id: UUID
    chapter_id: UUID
    parent_version_id: UUID | None
    content: str
    content_hash: str
    source: str
    created_at: datetime


class ChapterService(Protocol):
    async def create(
        self, work_id: UUID, number: int, title: str, content: str = ""
    ) -> Chapter: ...

    async def list(self, work_id: UUID) -> Sequence[Chapter]: ...

    async def get(self, chapter_id: UUID) -> Chapter: ...

    async def save(
        self, chapter_id: UUID, base_version: int, content: str, title: str | None = None
    ) -> Chapter: ...

    async def versions(self, chapter_id: UUID) -> Sequence[ChapterVersion]: ...

    async def get_version(self, chapter_id: UUID, version_id: UUID) -> ChapterVersion: ...

    async def assign_volume(self, chapter_id: UUID, volume_id: UUID | None) -> Chapter: ...
