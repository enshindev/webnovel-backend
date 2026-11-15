from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from webnovel.kernel.errors import NotFoundError, ValidationError
from webnovel.modules.graphrag.contract import GraphEdge, GraphEvent, GraphNode, GraphSubgraph
from webnovel.modules.memory.contract import Entity, EntityRelation, MemoryService


class GraphRagService:
    """实验：从实体关系出发做一跳/两跳扩展，拼一个小型故事子图。"""

    def __init__(self, memory: MemoryService) -> None:
        self._memory = memory

    async def subgraph(
        self,
        work_id: UUID,
        *,
        entity_id: UUID | None = None,
        name: str | None = None,
        depth: int = 1,
    ) -> GraphSubgraph:
        if depth not in {1, 2}:
            raise ValidationError("depth must be 1 or 2", code="graphrag.invalid_depth")
        entities = await self._memory.list_entities(work_id)
        seed = self._resolve_seed(entities, entity_id=entity_id, name=name)
        if seed is None:
            raise NotFoundError("seed entity not found", code="graphrag.seed_not_found")

        by_id = {entity.id: entity for entity in entities}
        relations = await self._memory.list_relations(work_id)
        selected_edges = self._walk(seed.id, relations, by_id, depth)
        node_ids = {seed.id}
        for edge in selected_edges:
            node_ids.add(edge.from_entity_id)
            node_ids.add(edge.to_entity_id)
        nodes = [
            GraphNode(
                id=entity.id,
                type=entity.type,
                name=entity.name,
                aliases=list(entity.aliases),
            )
            for entity_id in sorted(node_ids, key=str)
            if (entity := by_id.get(entity_id)) is not None
        ]
        names = {node.name for node in nodes}
        events = [
            GraphEvent(id=event.id, chapter_number=event.chapter_number, summary=event.summary)
            for event in await self._memory.list_story_events(work_id)
            if self._event_touches(event, names)
        ][:50]
        return GraphSubgraph(
            seed_id=seed.id,
            depth=depth,
            nodes=nodes,
            edges=[
                GraphEdge(
                    id=edge.id,
                    from_entity_id=edge.from_entity_id,
                    to_entity_id=edge.to_entity_id,
                    relation_type=edge.relation_type,
                )
                for edge in selected_edges
            ],
            events=events,
        )

    @staticmethod
    def _resolve_seed(
        entities: list[Entity], *, entity_id: UUID | None, name: str | None
    ) -> Entity | None:
        if entity_id is not None:
            return next((entity for entity in entities if entity.id == entity_id), None)
        wanted = (name or "").strip().casefold()
        if not wanted:
            return None
        exact = next(
            (
                entity
                for entity in entities
                if entity.name.casefold() == wanted
                or any(alias.casefold() == wanted for alias in entity.aliases)
            ),
            None,
        )
        if exact is not None:
            return exact
        return next((entity for entity in entities if wanted in entity.name.casefold()), None)

    @staticmethod
    def _walk(
        seed_id: UUID,
        relations: Sequence[EntityRelation],
        by_id: dict[UUID, Entity],
        depth: int,
    ) -> list[EntityRelation]:
        selected: list[EntityRelation] = []
        frontier = {seed_id}
        seen_edges: set[UUID] = set()
        for _ in range(depth):
            next_frontier: set[UUID] = set()
            for relation in relations:
                if relation.id in seen_edges:
                    continue
                if (
                    relation.from_entity_id not in frontier
                    and relation.to_entity_id not in frontier
                ):
                    continue
                if relation.from_entity_id not in by_id or relation.to_entity_id not in by_id:
                    continue
                selected.append(relation)
                seen_edges.add(relation.id)
                next_frontier.add(relation.from_entity_id)
                next_frontier.add(relation.to_entity_id)
            frontier = next_frontier
            if not frontier:
                break
        return selected

    @staticmethod
    def _event_touches(event: object, names: set[str]) -> bool:
        participants = getattr(event, "participants", []) or []
        for participant in participants:
            if isinstance(participant, dict) and str(participant.get("name", "")).strip() in names:
                return True
        return any(name in getattr(event, "summary", "") for name in names)
