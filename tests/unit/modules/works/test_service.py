from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from webnovel.kernel.errors import NotFoundError, ValidationError
from webnovel.modules.works.contract import Work
from webnovel.modules.works.service import WorksService


class FakeWorkRepository:
    def __init__(self) -> None:
        self.items: dict[UUID, Work] = {}

    async def add(self, title: str, genre: str | None) -> Work:
        now = datetime.now(UTC)
        work = Work(
            id=uuid4(),
            title=title,
            genre=genre,
            status="active",
            created_at=now,
            updated_at=now,
        )
        self.items[work.id] = work
        return work

    async def list(self, limit: int) -> list[Work]:
        return list(self.items.values())[:limit]

    async def get(self, work_id: UUID) -> Work | None:
        return self.items.get(work_id)

    async def update(
        self, work_id: UUID, title: str | None, genre: str | None, status: str | None
    ) -> Work | None:
        current = self.items.get(work_id)
        if current is None:
            return None
        updated = Work(
            id=current.id,
            title=title or current.title,
            genre=genre if genre is not None else current.genre,
            status=status or current.status,
            created_at=current.created_at,
            updated_at=datetime.now(UTC),
        )
        self.items[work_id] = updated
        return updated

    async def delete(self, work_id: UUID) -> bool:
        return self.items.pop(work_id, None) is not None


async def test_create_trims_title() -> None:
    service = WorksService(FakeWorkRepository())
    work = await service.create("  长夜灯火  ", "悬疑")
    assert work.title == "长夜灯火"
    assert work.genre == "悬疑"


async def test_create_rejects_empty_title() -> None:
    service = WorksService(FakeWorkRepository())
    try:
        await service.create("   ")
    except ValidationError as exc:
        assert exc.code == "work.title_required"
    else:
        raise AssertionError("expected ValidationError")


async def test_get_missing_raises_not_found() -> None:
    service = WorksService(FakeWorkRepository())
    try:
        await service.get(uuid4())
    except NotFoundError as exc:
        assert exc.code == "work.not_found"
    else:
        raise AssertionError("expected NotFoundError")


async def test_update_and_delete_work() -> None:
    service = WorksService(FakeWorkRepository())
    work = await service.create("旧标题", "悬疑")
    updated = await service.update(work.id, "新标题", "都市", "archived")
    assert updated.title == "新标题"
    assert updated.status == "archived"
    await service.delete(work.id)
    try:
        await service.get(work.id)
    except NotFoundError:
        pass
    else:
        raise AssertionError("expected NotFoundError")
