from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from webnovel.entrypoints.api.app import create_app
from webnovel.entrypoints.api.deps import get_memory_service
from webnovel.modules.memory.contract import Summary


class FakeMemoryService:
    async def list_proposals(self, work_id: UUID, status: Any = None) -> list[Any]:
        return []

    async def list_entities(self, work_id: UUID) -> list[Any]:
        return []

    async def get_summary(self, chapter_id: UUID) -> Summary:
        return Summary(
            id=uuid4(),
            work_id=uuid4(),
            chapter_id=chapter_id,
            content="摘要",
            based_on_version_id=uuid4(),
            status="fresh",
        )


def test_memory_endpoints() -> None:
    fake = FakeMemoryService()
    app = create_app()
    app.dependency_overrides[get_memory_service] = lambda: fake
    client = TestClient(app)

    work_id = uuid4()
    chapter_id = uuid4()
    proposals = client.get(f"/api/v1/works/{work_id}/proposals")
    assert proposals.status_code == 200
    assert proposals.json() == {"items": []}

    summary = client.get(f"/api/v1/chapters/{chapter_id}/summary")
    assert summary.status_code == 200
    assert summary.json()["content"] == "摘要"
