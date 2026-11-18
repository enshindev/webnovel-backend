from __future__ import annotations

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
        if entity_id is None and not (name or "").strip():
            raise ValidationError("entity_id or name is required", code="graphrag.seed_required")

        seed: Entity | None = None
        if entity_id is not None:
            try:
                seed = await self._memory.get_entity(entity_id)
            except NotFoundError:
                seed = None
        else:
            candidates = await self._memory.list_entities(work_id, limit=200)
            seed = self._resolve_seed(candidates, entity_id=None, name=name)
        if seed is None:
            raise NotFoundError("seed entity not found", code="graphrag.seed_not_found")

        by_id: dict[UUID, Entity] = {seed.id: seed}
        selected_edges: list[EntityRelation] = []
        seen_edges: set[UUID] = set()
        frontier: set[UUID] = {seed.id}
        for _ in range(depth):
            relations = await self._memory.list_relations_for_entities(
                work_id, sorted(frontier, key=str), limit=500
            )
            next_frontier: set[UUID] = set()
            for relation in relations:
                if relation.id in seen_edges:
                    continue
                endpoints = {relation.from_entity_id, relation.to_entity_id}
                loaded = True
                for endpoint in endpoints:
                    if endpoint in by_id:
                        continue
                    try:
                        by_id[endpoint] = await self._memory.get_entity(endpoint)
                    except NotFoundError:
                        loaded = False
                        break
                if not loaded:
                    continue
                selected_edges.append(relation)
                seen_edges.add(relation.id)
                next_frontier |= endpoints
            frontier = next_frontier
            if not frontier:
                break

        nodes = [
            GraphNode(
                id=entity.id,
                type=entity.type,
                name=entity.name,
                aliases=list(entity.aliases),
            )
            for entity_id in sorted(by_id, key=str)
            if (entity := by_id.get(entity_id)) is not None
        ]
        names = {node.name for node in nodes}
        events = [
            GraphEvent(id=event.id, chapter_number=event.chapter_number, summary=event.summary)
            for event in await self._memory.list_story_events(work_id, limit=200)
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
    def _event_touches(event: object, names: set[str]) -> bool:
        participants = getattr(event, "participants", []) or []
        for participant in participants:
            if isinstance(participant, dict) and str(participant.get("name", "")).strip() in names:
                return True
        return any(name in getattr(event, "summary", "") for name in names)
