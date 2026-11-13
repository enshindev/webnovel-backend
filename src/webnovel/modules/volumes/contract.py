from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True, slots=True)
class Volume:
    id: UUID
    work_id: UUID
    number: int
    title: str
    created_at: datetime


class VolumeService(Protocol):
    async def create(self, work_id: UUID, number: int, title: str) -> Volume: ...

    async def list(self, work_id: UUID) -> list[Volume]: ...

    async def get(self, volume_id: UUID) -> Volume: ...

    async def update(self, volume_id: UUID, number: int | None, title: str | None) -> Volume: ...

    async def delete(self, volume_id: UUID) -> None: ...
