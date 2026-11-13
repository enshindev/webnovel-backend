from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from webnovel.entrypoints.api.app import create_app
from webnovel.entrypoints.api.deps import get_work_service
from webnovel.modules.works.contract import Work


class FakeWorkService:
    def __init__(self) -> None:
        self.items: dict[UUID, Work] = {}

    async def create(self, title: str, genre: str | None = None) -> Work:
        now = datetime.now(UTC)
        work = Work(uuid4(), title, genre, "active", now, now)
        self.items[work.id] = work
        return work

    async def list(self, limit: int = 50) -> list[Work]:
        return list(self.items.values())[:limit]

    async def get(self, work_id: UUID) -> Work:
        return self.items[work_id]


def test_create_and_get_work() -> None:
    fake = FakeWorkService()
    app = create_app()
    app.dependency_overrides[get_work_service] = lambda: fake
    client = TestClient(app)

    created = client.post("/api/v1/works", json={"title": "长夜灯火", "genre": "悬疑"})
    assert created.status_code == 201
    work_id = created.json()["id"]

    fetched = client.get(f"/api/v1/works/{work_id}")
    assert fetched.status_code == 200
    assert fetched.json()["title"] == "长夜灯火"
