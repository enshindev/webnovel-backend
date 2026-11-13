from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True, slots=True)
class Work:
    id: UUID
    title: str
    genre: str | None
    status: str
    created_at: datetime
    updated_at: datetime


class WorkService(Protocol):
    async def create(self, title: str, genre: str | None = None) -> Work: ...

    async def list(self, limit: int = 50) -> list[Work]: ...

    async def get(self, work_id: UUID) -> Work: ...

    async def update(
        self, work_id: UUID, title: str | None, genre: str | None, status: str | None
    ) -> Work: ...

    async def delete(self, work_id: UUID) -> None: ...
