from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from webnovel.entrypoints.api.app import create_app
from webnovel.entrypoints.api.deps import get_assistant_service
from webnovel.modules.assistant.contract import Conversation


class FakeAssistantService:
    async def create_conversation(
        self, scope: str, mode: str, title: str | None, work_id: UUID | None
    ) -> Conversation:
        return Conversation(
            id=uuid4(),
            scope=scope,
            work_id=work_id,
            mode=mode,
            title=title,
            summary=None,
            created_at=datetime.now(UTC),
        )

    async def get_conversation(self, conversation_id: UUID) -> Conversation:
        return Conversation(
            id=conversation_id,
            scope="ideation",
            work_id=None,
            mode="world",
            title="世界",
            summary=None,
            created_at=datetime.now(UTC),
        )


def test_create_conversation() -> None:
    app = create_app()
    app.dependency_overrides[get_assistant_service] = lambda: FakeAssistantService()
    client = TestClient(app)
    response = client.post(
        "/api/v1/experiments/assistant/conversations",
        json={"scope": "ideation", "mode": "world", "title": "世界"},
    )
    assert response.status_code == 201
    assert response.json()["scope"] == "ideation"
    conversation_id = response.json()["id"]
    fetched = client.get(f"/api/v1/experiments/assistant/conversations/{conversation_id}")
    assert fetched.status_code == 200
