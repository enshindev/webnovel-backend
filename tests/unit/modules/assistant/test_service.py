from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from webnovel.modules.assistant.contract import Conversation, ProjectBrief, WorldDraft
from webnovel.modules.assistant.service import AssistantServiceImpl
from webnovel.modules.works.contract import Work


class FakeWorkService:
    async def create(self, title: str, genre: str | None = None) -> Work:
        now = datetime.now(UTC)
        return Work(uuid4(), title, genre, "active", now, now)


class FakeMaterializer:
    def __init__(self) -> None:
        self.calls: list[tuple[UUID, list[dict[str, Any]], list[dict[str, Any]]]] = []

    async def materialize(
        self, work_id: UUID, nodes: list[dict[str, Any]], edges: list[dict[str, Any]]
    ) -> dict[str, UUID]:
        self.calls.append((work_id, nodes, edges))
        return {}


class FakeAssistantRepository:
    def __init__(self) -> None:
        self.conversation = Conversation(
            id=uuid4(),
            scope="ideation",
            work_id=None,
            mode="world",
            title="世界",
            summary=None,
            created_at=datetime.now(UTC),
        )
        self.draft = WorldDraft(
            id=uuid4(),
            conversation_id=self.conversation.id,
            version=1,
            status="draft",
            summary="",
            nodes=[{"id": "char-1", "type": "character", "name": "沈砚"}],
            edges=[],
            created_at=datetime.now(UTC),
        )
        self.brief = ProjectBrief(
            id=uuid4(),
            conversation_id=self.conversation.id,
            world_draft_id=self.draft.id,
            title_candidates=["长夜灯火"],
            premise="捕快在雨夜追查失踪案",
            genre="悬疑",
            target_reader={},
            selling_points=[],
            core_conflict="",
            character_core={},
            tone=None,
            pov=None,
            planned_length=None,
            update_cadence=None,
            opening_plan=[],
            risks=[],
            sources=[],
            status="draft",
            created_work_id=None,
            created_at=datetime.now(UTC),
        )

    async def create_conversation(
        self, scope: str, mode: str, title: str | None, work_id: UUID | None
    ) -> Conversation:
        return self.conversation

    async def get_conversation(self, conversation_id: UUID) -> Conversation | None:
        return self.conversation

    async def create_world_draft(
        self,
        conversation_id: UUID,
        summary: str,
        nodes: list[dict[str, Any]],
        edges: list[dict[str, Any]],
    ) -> WorldDraft:
        return self.draft

    async def add_world_draft_version(
        self,
        draft_id: UUID,
        summary: str,
        nodes: list[dict[str, Any]],
        edges: list[dict[str, Any]],
    ) -> WorldDraft | None:
        return self.draft

    async def get_world_draft(self, draft_id: UUID) -> WorldDraft | None:
        return self.draft

    async def create_brief(self, conversation_id: UUID, values: dict[str, Any]) -> ProjectBrief:
        return self.brief

    async def get_brief(self, brief_id: UUID) -> ProjectBrief | None:
        return self.brief

    async def mark_brief_created(self, brief_id: UUID, work_id: UUID) -> None:
        self.brief = replace(self.brief, created_work_id=work_id, status="created")


async def test_create_work_materializes_and_is_idempotent() -> None:
    repo = FakeAssistantRepository()
    materializer = FakeMaterializer()
    service = AssistantServiceImpl(repo, FakeWorkService(), materializer)
    work_id = await service.create_work(repo.brief.id, "idem-1")
    assert work_id is not None
    assert len(materializer.calls) == 1
    again = await service.create_work(repo.brief.id, "idem-2")
    assert again == work_id
    assert len(materializer.calls) == 1
