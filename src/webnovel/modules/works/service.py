from __future__ import annotations

from uuid import UUID

from webnovel.kernel.errors import NotFoundError, ValidationError
from webnovel.modules.audit.contract import AuditRecorder
from webnovel.modules.works.contract import Work
from webnovel.modules.works.repository import WorkRepository


class WorksService:
    def __init__(self, repository: WorkRepository, audit: AuditRecorder | None = None) -> None:
        self._repository = repository
        self._audit = audit

    async def create(self, title: str, genre: str | None = None) -> Work:
        title = title.strip()
        if not title:
            raise ValidationError("title must not be empty", code="work.title_required")
        work = await self._repository.add(title=title, genre=genre)
        if self._audit is not None:
            await self._audit.record(
                "work.create",
                target_type="work",
                target_id=str(work.id),
                metadata={"title": work.title},
            )
        return work

    async def list(self, limit: int = 50) -> list[Work]:
        return await self._repository.list(limit=limit)

    async def get(self, work_id: UUID) -> Work:
        work = await self._repository.get(work_id)
        if work is None:
            raise NotFoundError(f"work not found: {work_id}", code="work.not_found")
        return work

    async def update(
        self, work_id: UUID, title: str | None, genre: str | None, status: str | None
    ) -> Work:
        if title is not None:
            title = title.strip()
            if not title:
                raise ValidationError("title must not be empty", code="work.title_required")
        work = await self._repository.update(work_id, title, genre, status)
        if work is None:
            raise NotFoundError(f"work not found: {work_id}", code="work.not_found")
        if self._audit is not None:
            await self._audit.record(
                "work.update",
                target_type="work",
                target_id=str(work.id),
                metadata={"title": work.title, "status": work.status},
            )
        return work

    async def delete(self, work_id: UUID) -> None:
        if not await self._repository.delete(work_id):
            raise NotFoundError(f"work not found: {work_id}", code="work.not_found")
        if self._audit is not None:
            await self._audit.record("work.delete", target_type="work", target_id=str(work_id))
