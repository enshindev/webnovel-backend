from __future__ import annotations

from types import SimpleNamespace
from uuid import UUID, uuid4

from webnovel.modules.memory.contract import KnowledgeState, StoryEvent
from webnovel.modules.memory.extraction import ExtractionRunner
from webnovel.modules.memory.service import MemoryServiceImpl


class FakeRepository:
    def __init__(self) -> None:
        self.events: list[StoryEvent] = []
        self.states: list[KnowledgeState] = []

    async def find_entity(
        self, work_id: UUID, entity_type: str, name: str, aliases: list[str]
    ) -> None:
        return None

    async def list_story_events(
        self, work_id: UUID, *, from_chapter: int | None = None, to_chapter: int | None = None
    ) -> list[StoryEvent]:
        return self.events

    async def list_knowledge(
        self, work_id: UUID, *, character_id: UUID | None = None, at_chapter: int | None = None
    ) -> list[KnowledgeState]:
        return self.states

    async def who_knows(
        self, work_id: UUID, fact_key: str, at_chapter: int | None = None
    ) -> list[KnowledgeState]:
        return self.states


def _runner() -> ExtractionRunner:
    return ExtractionRunner(
        repository=FakeRepository(),  # type: ignore[arg-type]
        chapter_service=object(),  # type: ignore[arg-type]
        model_client=object(),  # type: ignore[arg-type]
        settings=SimpleNamespace(prompts_dir=None),  # type: ignore[arg-type]
    )


async def test_event_payload_normalizes_knowledge_changes() -> None:
    runner = _runner()
    payload = await runner._event_payload(
        uuid4(),
        {
            "index": 1,
            "summary": "沈砚在旧巷听见钟声",
            "time_text": "雨夜",
            "location": "旧巷",
            "participants": [{"name": "沈砚", "role": "主角"}],
            "knowledge_changes": [
                {"character": "沈砚", "fact": "钟声来自地下", "state": "suspects"}
            ],
            "entity_changes": [],
            "confidence": 0.8,
            "quote": "第二声钟响",
        },
    )
    assert payload["summary"] == "沈砚在旧巷听见钟声"
    assert payload["knowledge_changes"][0]["fact_key"] == "钟声来自地下"
    assert payload["knowledge_changes"][0]["state"] == "suspects"
    assert payload["source_span"] == {"quote": "第二声钟响"}


async def test_event_payload_skips_incomplete_knowledge_changes() -> None:
    runner = _runner()
    payload = await runner._event_payload(
        uuid4(),
        {"summary": "一件小事", "knowledge_changes": [{"character": "沈砚"}]},
    )
    assert payload["knowledge_changes"] == []


async def test_service_delegates_story_queries() -> None:
    repository = FakeRepository()
    service = MemoryServiceImpl(repository)  # type: ignore[arg-type]
    work_id = uuid4()
    assert await service.list_story_events(work_id) == []
    assert await service.list_knowledge(work_id) == []
    assert await service.who_knows(work_id, "钟声来自地下") == []
