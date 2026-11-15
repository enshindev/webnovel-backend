from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from webnovel.kernel.errors import NotFoundError, ValidationError
from webnovel.modules.graphrag.service import GraphRagService
from webnovel.modules.memory.contract import (
    Entity,
    EntityRelation,
    StoryEvent,
)


class FakeMemory:
    def __init__(self) -> None:
        self.entities = [
            _entity("A", ["甲"]),
            _entity("B"),
            _entity("C"),
            _entity("D"),
        ]
        self.relations = [
            _relation(self.entities[0].id, self.entities[1].id, "认识"),
            _relation(self.entities[1].id, self.entities[2].id, "同门"),
            _relation(self.entities[2].id, self.entities[3].id, "敌对"),
        ]
        self.events = [
            StoryEvent(
                id=uuid4(),
                work_id=uuid4(),
                chapter_id=uuid4(),
                chapter_number=1,
                event_index=1,
                summary="A 遇见 B",
                time_text=None,
                location=None,
                participants=[{"name": "A", "role": "主角"}],
                changes={},
                confidence=0.9,
                status="inferred",
            ),
            StoryEvent(
                id=uuid4(),
                work_id=uuid4(),
                chapter_id=uuid4(),
                chapter_number=2,
                event_index=1,
                summary="D 独自离开",
                time_text=None,
                location=None,
                participants=[{"name": "D", "role": "配角"}],
                changes={},
                confidence=0.9,
                status="inferred",
            ),
        ]

    async def list_entities(self, work_id: UUID) -> list[Entity]:
        return self.entities

    async def list_relations(
        self, work_id: UUID, entity_id: UUID | None = None
    ) -> list[EntityRelation]:
        return self.relations

    async def list_story_events(
        self, work_id: UUID, *, from_chapter: int | None = None, to_chapter: int | None = None
    ) -> list[StoryEvent]:
        return self.events


def _entity(name: str, aliases: list[str] | None = None) -> Entity:
    return Entity(
        id=uuid4(),
        work_id=uuid4(),
        type="character",
        name=name,
        aliases=aliases or [],
        attributes={},
        version=1,
        first_chapter_id=None,
    )


def _relation(a: UUID, b: UUID, relation_type: str) -> EntityRelation:
    return EntityRelation(
        id=uuid4(),
        work_id=uuid4(),
        from_entity_id=a,
        to_entity_id=b,
        relation_type=relation_type,
        since_chapter_id=None,
    )


async def test_depth_one_returns_seed_and_neighbors() -> None:
    memory = FakeMemory()
    graph = await GraphRagService(memory).subgraph(  # type: ignore[arg-type]
        uuid4(), entity_id=memory.entities[0].id, depth=1
    )
    assert {node.name for node in graph.nodes} == {"A", "B"}
    assert len(graph.edges) == 1
    assert [event.summary for event in graph.events] == ["A 遇见 B"]


async def test_depth_two_expands_one_more_hop() -> None:
    memory = FakeMemory()
    graph = await GraphRagService(memory).subgraph(  # type: ignore[arg-type]
        uuid4(), entity_id=memory.entities[0].id, depth=2
    )
    assert {node.name for node in graph.nodes} == {"A", "B", "C"}
    assert len(graph.edges) == 2


async def test_alias_resolves_seed() -> None:
    memory = FakeMemory()
    graph = await GraphRagService(memory).subgraph(  # type: ignore[arg-type]
        uuid4(), name="甲", depth=1
    )
    assert graph.seed_id == memory.entities[0].id


async def test_missing_seed_raises_not_found() -> None:
    memory = FakeMemory()
    with pytest.raises(NotFoundError):
        await GraphRagService(memory).subgraph(uuid4(), name="不存在")  # type: ignore[arg-type]


async def test_invalid_depth_raises_validation_error() -> None:
    memory = FakeMemory()
    with pytest.raises(ValidationError):
        await GraphRagService(memory).subgraph(  # type: ignore[arg-type]
            uuid4(), entity_id=memory.entities[0].id, depth=3
        )
