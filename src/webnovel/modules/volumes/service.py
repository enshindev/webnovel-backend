from __future__ import annotations

from uuid import UUID

from webnovel.kernel.errors import NotFoundError, ValidationError
from webnovel.modules.volumes.contract import Volume, VolumeService
from webnovel.modules.volumes.repository import VolumeRepository
from webnovel.modules.works.contract import WorkService


class VolumeServiceImpl(VolumeService):
    def __init__(self, repository: VolumeRepository, work_service: WorkService) -> None:
        self._repository = repository
        self._work_service = work_service

    async def create(self, work_id: UUID, number: int, title: str) -> Volume:
        await self._work_service.get(work_id)
        if number < 1:
            raise ValidationError("volume number must be positive", code="volume.number_invalid")
        return await self._repository.create(work_id, number, title.strip())

    async def list(self, work_id: UUID) -> list[Volume]:
        await self._work_service.get(work_id)
        return await self._repository.list(work_id)

    async def get(self, volume_id: UUID) -> Volume:
        volume = await self._repository.get(volume_id)
        if volume is None:
            raise NotFoundError(f"volume not found: {volume_id}", code="volume.not_found")
        return volume

    async def update(self, volume_id: UUID, number: int | None, title: str | None) -> Volume:
        if number is not None and number < 1:
            raise ValidationError("volume number must be positive", code="volume.number_invalid")
        volume = await self._repository.update(volume_id, number, title.strip() if title else title)
        if volume is None:
            raise NotFoundError(f"volume not found: {volume_id}", code="volume.not_found")
        return volume

    async def delete(self, volume_id: UUID) -> None:
        if not await self._repository.delete(volume_id):
            raise NotFoundError(f"volume not found: {volume_id}", code="volume.not_found")
