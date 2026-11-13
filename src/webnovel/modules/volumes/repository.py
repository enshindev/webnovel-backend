from __future__ import annotations

from typing import Protocol
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from webnovel.modules.volumes.contract import Volume
from webnovel.modules.volumes.models import VolumeModel


class VolumeRepository(Protocol):
    async def create(self, work_id: UUID, number: int, title: str) -> Volume: ...

    async def list(self, work_id: UUID) -> list[Volume]: ...

    async def get(self, volume_id: UUID) -> Volume | None: ...

    async def update(
        self, volume_id: UUID, number: int | None, title: str | None
    ) -> Volume | None: ...

    async def delete(self, volume_id: UUID) -> bool: ...


def _domain(model: VolumeModel) -> Volume:
    return Volume(model.id, model.work_id, model.number, model.title, model.created_at)


class SqlAlchemyVolumeRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, work_id: UUID, number: int, title: str) -> Volume:
        model = VolumeModel(work_id=work_id, number=number, title=title)
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return _domain(model)

    async def list(self, work_id: UUID) -> list[Volume]:
        rows = (
            (
                await self._session.execute(
                    select(VolumeModel)
                    .where(VolumeModel.work_id == work_id)
                    .order_by(VolumeModel.number.asc())
                )
            )
            .scalars()
            .all()
        )
        return [_domain(row) for row in rows]

    async def get(self, volume_id: UUID) -> Volume | None:
        model = await self._session.get(VolumeModel, volume_id)
        return _domain(model) if model is not None else None

    async def update(self, volume_id: UUID, number: int | None, title: str | None) -> Volume | None:
        model = await self._session.get(VolumeModel, volume_id)
        if model is None:
            return None
        if number is not None:
            model.number = number
        if title is not None:
            model.title = title
        await self._session.flush()
        await self._session.refresh(model)
        return _domain(model)

    async def delete(self, volume_id: UUID) -> bool:
        model = await self._session.get(VolumeModel, volume_id)
        if model is None:
            return False
        await self._session.delete(model)
        await self._session.flush()
        return True
