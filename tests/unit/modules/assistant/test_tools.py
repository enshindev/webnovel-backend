from __future__ import annotations

from uuid import UUID, uuid4

from webnovel.modules.assistant.tools import AssistantTools
from webnovel.modules.memory.contract import (
    Entity,
    EntityRelation,
    KnowledgeState,
    StoryEvent,
)


class FakeMemory:
    def __init__(self, relations: list[EntityRelation] | None = None) -> None:
        self.relations = relations or []

    async def who_knows(
        self, work_id: UUID, fact_key: str, at_chapter: int | None = None
    ) -> list[KnowledgeState]:
        return [
            KnowledgeState(
                id=uuid4(),
                work_id=work_id,
                character_id=None,
                character_name="沈砚",
                fact_key=fact_key.casefold(),
                fact_value={"text": fact_key},
                state="knows",
                chapter_number=12,
                confidence=0.9,
                status="inferred",
            )
        ]

    async def list_relations(
        self, work_id: UUID, entity_id: UUID | None = None
    ) -> list[EntityRelation]:
        return self.relations

    async def list_story_events(
        self,
        work_id: UUID,
        *,
        from_chapter: int | None = None,
        to_chapter: int | None = None,
    ) -> list[StoryEvent]:
        return [
            StoryEvent(
                id=uuid4(),
                work_id=work_id,
                chapter_id=uuid4(),
                chapter_number=12,
                event_index=1,
                summary="沈砚在旧巷听见钟声",
                time_text="雨夜",
                location="旧巷",
                participants=[],
                changes={},
                confidence=0.9,
                status="inferred",
            )
        ]


class FakeLookup:
    def __init__(self, entities: list[Entity] | None = None) -> None:
        self.entities = entities or []

    async def list_entities(self, work_id: UUID) -> list[Entity]:
        return self.entities


def _entity(name: str, entity_id: UUID) -> Entity:
    return Entity(
        id=entity_id,
        work_id=uuid4(),
        type="character",
        name=name,
        aliases=[],
        attributes={},
        version=1,
        first_chapter_id=None,
    )


def _tools() -> AssistantTools:
    entity = _entity("沈砚", uuid4())
    target = _entity("师姐", uuid4())
    relation = EntityRelation(
        id=uuid4(),
        work_id=entity.work_id,
        from_entity_id=entity.id,
        to_entity_id=target.id,
        relation_type="同门",
        since_chapter_id=None,
    )
    return AssistantTools(
        retrieval=None,
        memory_repository=FakeLookup([entity, target]),  # type: ignore[arg-type]
        story_state=FakeMemory([relation]),  # type: ignore[arg-type]
    )


def test_tool_schemas_include_story_state_tools() -> None:
    names = {schema["function"]["name"] for schema in AssistantTools.schemas()}  # type: ignore[index]
    assert {"who_knows", "get_story_events", "get_relations"} <= names


async def test_who_knows_tool_returns_citations() -> None:
    result = await _tools().execute(
        "who_knows", uuid4(), '{"fact_key": "钟声来自地下", "at_chapter": 12}'
    )
    assert "沈砚" in result.text
    assert result.citations[0]["source"] == "knowledge"


async def test_story_events_tool_formats_events() -> None:
    result = await _tools().execute("get_story_events", uuid4(), '{"from_chapter": 1}')
    assert "第 12 章" in result.text
    assert result.citations[0]["source"] == "story_event"


async def test_story_tools_fail_closed_without_state() -> None:
    tools = AssistantTools(
        retrieval=None,
        memory_repository=FakeLookup(),  # type: ignore[arg-type]
    )
    result = await tools.execute("who_knows", uuid4(), '{"fact_key": "x"}')
    assert result.text == "故事状态暂不可用。"


async def test_get_relations_tool_formats_edges() -> None:
    result = await _tools().execute("get_relations", uuid4(), '{"name": "沈砚"}')
    assert "沈砚 -> 师姐（同门）" in result.text
    assert result.citations[0]["source"] == "entity_relation"
