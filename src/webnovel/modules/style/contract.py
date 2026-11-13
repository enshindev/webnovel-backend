from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID


@dataclass(frozen=True, slots=True)
class StyleProfile:
    id: UUID
    work_id: UUID
    version: int
    status: str
    features: dict[str, Any]
    qualitative: dict[str, Any]
    summary: str
    do_list: list[str]
    dont_list: list[str]
    created_at: datetime


@dataclass(frozen=True, slots=True)
class StyleCheck:
    id: UUID
    work_id: UUID
    profile_id: UUID
    score: float
    dimensions: dict[str, Any]
    issues: list[dict[str, Any]]
    created_at: datetime


class StyleProfileReader(Protocol):
    async def get_active(self, work_id: UUID) -> StyleProfile | None: ...


@dataclass(frozen=True, slots=True)
class StyleRewrite:
    content: str
    check: StyleCheck


class StyleService(Protocol):
    async def create_profile(self, work_id: UUID, chapter_ids: list[UUID]) -> StyleProfile: ...

    async def get_profile(self, work_id: UUID, profile_id: UUID) -> StyleProfile: ...

    async def update_profile(
        self,
        work_id: UUID,
        profile_id: UUID,
        *,
        summary: str | None = None,
        status: str | None = None,
        do_list: list[str] | None = None,
        dont_list: list[str] | None = None,
    ) -> StyleProfile: ...

    async def check(self, work_id: UUID, profile_id: UUID, content: str) -> StyleCheck: ...

    async def get_active(self, work_id: UUID) -> StyleProfile | None: ...

    async def add_character_sample(
        self, work_id: UUID, profile_id: UUID, character_name: str, text: str
    ) -> None: ...

    async def check_character(
        self, work_id: UUID, profile_id: UUID, character_name: str, content: str
    ) -> StyleCheck: ...

    async def rewrite(self, work_id: UUID, profile_id: UUID, content: str) -> StyleRewrite: ...
