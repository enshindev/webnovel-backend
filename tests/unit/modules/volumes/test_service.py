from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from webnovel.modules.volumes.contract import Volume
from webnovel.modules.volumes.service import VolumeServiceImpl
from webnovel.modules.works.contract import Work


class FakeWorkService:
    async def get(self, work_id: UUID) -> Work:
        now = datetime.now(UTC)
        return Work(work_id, "t", None, "draft", now, now)


class FakeVolumeRepository:
    def __init__(self) -> None:
        self.items: dict[UUID, Volume] = {}

    async def create(self, work_id: UUID, number: int, title: str) -> Volume:
        volume = Volume(uuid4(), work_id, number, title, datetime.now(UTC))
        self.items[volume.id] = volume
        return volume

    async def list(self, work_id: UUID) -> list[Volume]:
        return list(self.items.values())

    async def get(self, volume_id: UUID) -> Volume | None:
        return self.items.get(volume_id)

    async def update(self, volume_id: UUID, number: int | None, title: str | None) -> Volume | None:
        old = self.items.get(volume_id)
        if old is None:
            return None
        new = Volume(
            old.id,
            old.work_id,
            number if number is not None else old.number,
            title if title is not None else old.title,
            old.created_at,
        )
        self.items[new.id] = new
        return new

    async def delete(self, volume_id: UUID) -> bool:
        return self.items.pop(volume_id, None) is not None


async def test_create_and_update_volume() -> None:
    repo = FakeVolumeRepository()
    service = VolumeServiceImpl(repo, FakeWorkService())  # type: ignore[arg-type]
    work_id = uuid4()
    volume = await service.create(work_id, 1, "第一卷")
    assert volume.number == 1
    assert [item.id for item in await service.list(work_id)] == [volume.id]
    updated = await service.update(volume.id, 2, "第二卷")
    assert updated.number == 2
    await service.delete(volume.id)
    assert not repo.items
