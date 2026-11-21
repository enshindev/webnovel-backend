from __future__ import annotations

from types import SimpleNamespace
from uuid import UUID, uuid4

from webnovel.modules.memory.contract import EntityStateChange, KnowledgeState, StoryEvent
from webnovel.modules.memory.extraction import ExtractionRunner
from webnovel.modules.memory.service import MemoryServiceImpl
from webnovel.modules.memory.story_state import detect_contradictions


class FakeRepository:
    def __init__(self) -> None:
        self.events: list[StoryEvent] = []
        self.states: list[KnowledgeState] = []

    async def find_entity(
        self, work_id: UUID, entity_type: str, name: str, aliases: list[str]
    ) -> None:
        return None

    async def list_story_events(
        self,
        work_id: UUID,
        *,
        from_chapter: int | None = None,
        to_chapter: int | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[StoryEvent]:
        return self.events

    async def list_knowledge(
        self,
        work_id: UUID,
        *,
        character_id: UUID | None = None,
        at_chapter: int | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[KnowledgeState]:
        return self.states

    async def who_knows(
        self,
        work_id: UUID,
        fact_key: str,
        at_chapter: int | None = None,
        limit: int = 100,
        offset: int = 0,
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


def _event(chapter: int, changes: dict[str, object]) -> StoryEvent:
    return StoryEvent(
        id=uuid4(),
        work_id=uuid4(),
        chapter_id=uuid4(),
        chapter_number=chapter,
        event_index=1,
        summary="事件",
        time_text=None,
        location=None,
        participants=[],
        changes=changes,
        confidence=0.8,
        status="inferred",
    )


def test_detects_knowledge_conflict_in_same_chapter() -> None:
    event = _event(
        3,
        {
            "knowledge_changes": [
                {"character_name": "沈砚", "fact_key": "钟声来自地下", "state": "knows"},
                {"character_name": "沈砚", "fact_key": "钟声来自地下", "state": "does_not_know"},
            ]
        },
    )
    result = detect_contradictions([event])
    assert len(result) == 1
    assert result[0].kind == "knowledge.conflict"
    assert result[0].severity == "P1"


def test_detects_entity_state_conflict_in_same_chapter() -> None:
    event = _event(
        3,
        {
            "entity_changes": [
                {"entity": "玉佩", "field": "holder", "after": "沈砚"},
                {"entity": "玉佩", "field": "holder", "after": "师姐"},
            ]
        },
    )
    result = detect_contradictions([event])
    assert len(result) == 1
    assert result[0].kind == "entity.state_conflict"
    assert result[0].severity == "P2"


def test_no_contradiction_for_normal_events() -> None:
    event = _event(
        3,
        {
            "knowledge_changes": [
                {"character_name": "沈砚", "fact_key": "钟声来自地下", "state": "knows"}
            ]
        },
    )
    assert detect_contradictions([event]) == []


async def test_event_payload_normalizes_entity_changes() -> None:
    payload = await _runner()._event_payload(
        uuid4(),
        {
            "summary": "玉佩换了主人",
            "entity_changes": [
                {"entity": "玉佩", "field": "holder", "before": "沈砚", "after": "师姐"}
            ],
        },
    )
    assert payload["entity_changes"] == [
        {
            "entity_id": "",
            "entity_name": "玉佩",
            "field": "holder",
            "before": {"value": "沈砚"},
            "after": {"value": "师姐"},
        }
    ]


class FakeChangeRepository:
    async def update_entity_change_status(
        self, work_id: UUID, change_id: UUID, status: str
    ) -> EntityStateChange | None:
        return EntityStateChange(
            id=change_id,
            work_id=work_id,
            entity_id=None,
            entity_name="玉佩",
            field="holder",
            before={"value": "沈砚"},
            after={"value": "师姐"},
            chapter_number=3,
            status=status,
        )


async def test_entity_change_status_can_be_corrected() -> None:
    service = MemoryServiceImpl(FakeChangeRepository())  # type: ignore[arg-type]
    change = await service.update_entity_change_status(uuid4(), uuid4(), "corrected")
    assert change.status == "corrected"


def test_detects_entity_state_sequence_conflict() -> None:
    first = _event(
        3,
        {
            "entity_changes": [
                {"entity_name": "玉佩", "field": "holder", "before": "沈砚", "after": "师姐"}
            ]
        },
    )
    second = _event(
        4,
        {
            "entity_changes": [
                {"entity_name": "玉佩", "field": "holder", "before": "掌柜", "after": "师姐"}
            ]
        },
    )
    result = detect_contradictions([first, second])
    assert [item.kind for item in result] == ["entity.state_sequence"]


def test_detects_knowledge_regression() -> None:
    first = _event(
        3,
        {
            "knowledge_changes": [
                {"character_name": "沈砚", "fact_key": "钟声来自地下", "state": "knows"}
            ]
        },
    )
    second = _event(
        4,
        {
            "knowledge_changes": [
                {"character_name": "沈砚", "fact_key": "钟声来自地下", "state": "does_not_know"}
            ]
        },
    )
    result = detect_contradictions([first, second])
    assert [item.kind for item in result] == ["knowledge.regression"]
