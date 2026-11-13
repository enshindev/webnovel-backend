from __future__ import annotations

from typing import Protocol
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from webnovel.modules.works.contract import Work
from webnovel.modules.works.models import WorkModel


class WorkRepository(Protocol):
    async def add(self, title: str, genre: str | None) -> Work: ...

    async def list(self, limit: int) -> list[Work]: ...

    async def get(self, work_id: UUID) -> Work | None: ...

    async def update(
        self, work_id: UUID, title: str | None, genre: str | None, status: str | None
    ) -> Work | None: ...

    async def delete(self, work_id: UUID) -> bool: ...


def _to_domain(model: WorkModel) -> Work:
    return Work(
        id=model.id,
        title=model.title,
        genre=model.genre,
        status=model.status,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


class SqlAlchemyWorkRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, title: str, genre: str | None) -> Work:
        model = WorkModel(title=title, genre=genre)
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return _to_domain(model)

    async def list(self, limit: int) -> list[Work]:
        stmt = select(WorkModel).order_by(WorkModel.created_at.desc()).limit(limit)
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_to_domain(row) for row in rows]

    async def get(self, work_id: UUID) -> Work | None:
        model = await self._session.get(WorkModel, work_id)
        return _to_domain(model) if model is not None else None

    async def update(
        self, work_id: UUID, title: str | None, genre: str | None, status: str | None
    ) -> Work | None:
        model = await self._session.get(WorkModel, work_id)
        if model is None:
            return None
        if title is not None:
            model.title = title
        if genre is not None:
            model.genre = genre
        if status is not None:
            model.status = status
        await self._session.flush()
        await self._session.refresh(model)
        return _to_domain(model)

    async def delete(self, work_id: UUID) -> bool:
        model = await self._session.get(WorkModel, work_id)
        if model is None:
            return False
        await self._session.delete(model)
        await self._session.flush()
        return True
