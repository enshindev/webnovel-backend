from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any
from uuid import UUID

import structlog

from webnovel.kernel.errors import NotFoundError, ValidationError
from webnovel.modules.memory.contract import (
    ChangeProposal,
    Contradiction,
    Entity,
    EntityChangeStatus,
    EntityRelation,
    EntityStateChange,
    ExtractionRun,
    Foreshadow,
    KnowledgeState,
    KnowledgeStatus,
    MemoryIndexer,
    MemoryService,
    ProposalStatus,
    ResolvedProposal,
    StoryEvent,
    Summary,
    TimelineEvent,
)
from webnovel.modules.memory.repository import MemoryRepository
from webnovel.modules.memory.story_state import detect_contradictions

logger = structlog.get_logger(__name__)


class MemoryServiceImpl(MemoryService):
    def __init__(
        self,
        repository: MemoryRepository,
        enqueue: Callable[[UUID], Awaitable[None]] | None = None,
        indexer: MemoryIndexer | None = None,
    ) -> None:
        self._repository = repository
        self._enqueue = enqueue
        self._indexer = indexer

    async def start_extraction(
        self,
        work_id: UUID,
        chapter_id: UUID,
        version_id: UUID,
        trigger: str = "accept",
    ) -> ExtractionRun:
        run = await self._repository.create_run(work_id, chapter_id, version_id, trigger=trigger)
        if self._enqueue is not None:
            await self._enqueue(run.id)
        return run

    async def list_proposals(
        self, work_id: UUID, status: ProposalStatus | None = None
    ) -> list[ChangeProposal]:
        return await self._repository.list_proposals(work_id, status)

    async def resolve_proposal(
        self,
        proposal_id: UUID,
        action: str,
        *,
        base_entity_version: int,
        modified_payload: dict[str, object] | None = None,
    ) -> ResolvedProposal:
        if action not in {"accept", "modify", "reject"}:
            raise ValidationError(f"invalid action: {action}", code="proposal.invalid_action")
        resolved = await self._repository.resolve_proposal(
            proposal_id,
            action,
            base_entity_version=base_entity_version,
            modified_payload=modified_payload,
        )
        if resolved is None:
            raise NotFoundError(f"proposal not found: {proposal_id}", code="proposal.not_found")
        if resolved.entity is not None and self._indexer is not None:
            try:
                await self._indexer.index_entity(resolved.entity)
            except Exception:
                logger.exception("memory.entity_index_failed", proposal_id=str(proposal_id))
        return resolved

    async def list_entities(self, work_id: UUID, limit: int = 500, offset: int = 0) -> list[Entity]:
        return await self._repository.list_entities(work_id, limit=limit, offset=offset)

    async def list_relations_for_entities(
        self, work_id: UUID, entity_ids: list[UUID], limit: int = 500
    ) -> list[EntityRelation]:
        return await self._repository.list_relations_for_entities(work_id, entity_ids, limit)

    async def get_summary(self, chapter_id: UUID) -> Summary:
        summary = await self._repository.get_summary(chapter_id)
        if summary is None:
            raise NotFoundError(f"summary not found: {chapter_id}", code="summary.not_found")
        return summary

    async def list_foreshadows(self, work_id: UUID) -> list[Foreshadow]:
        return await self._repository.list_foreshadows(work_id)

    async def list_story_events(
        self,
        work_id: UUID,
        *,
        from_chapter: int | None = None,
        to_chapter: int | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[StoryEvent]:
        return await self._repository.list_story_events(
            work_id,
            from_chapter=from_chapter,
            to_chapter=to_chapter,
            limit=limit,
            offset=offset,
        )

    async def list_knowledge(
        self,
        work_id: UUID,
        *,
        character_id: UUID | None = None,
        at_chapter: int | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[KnowledgeState]:
        return await self._repository.list_knowledge(
            work_id,
            character_id=character_id,
            at_chapter=at_chapter,
            limit=limit,
            offset=offset,
        )

    async def who_knows(
        self,
        work_id: UUID,
        fact_key: str,
        at_chapter: int | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[KnowledgeState]:
        return await self._repository.who_knows(
            work_id, fact_key, at_chapter, limit=limit, offset=offset
        )

    async def contradictions(self, work_id: UUID) -> list[Contradiction]:
        events = []
        offset = 0
        while True:
            batch = await self._repository.list_story_events(work_id, limit=500, offset=offset)
            events.extend(batch)
            if len(batch) < 500:
                break
            offset += 500
        return detect_contradictions(events)

    async def list_relations(
        self, work_id: UUID, entity_id: UUID | None = None, limit: int = 100, offset: int = 0
    ) -> list[EntityRelation]:
        return await self._repository.list_relations(work_id, entity_id, limit=limit, offset=offset)

    async def list_entity_changes(
        self,
        work_id: UUID,
        entity_id: UUID | None = None,
        *,
        at_chapter: int | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[EntityStateChange]:
        return await self._repository.list_entity_changes(
            work_id,
            entity_id,
            at_chapter=at_chapter,
            limit=limit,
            offset=offset,
        )

    async def update_knowledge_status(
        self, work_id: UUID, knowledge_id: UUID, status: str
    ) -> KnowledgeState:
        if status not in {item.value for item in KnowledgeStatus}:
            raise ValidationError(
                f"invalid knowledge status: {status}",
                code="story_state.invalid_knowledge_status",
            )
        knowledge = await self._repository.update_knowledge_status(work_id, knowledge_id, status)
        if knowledge is None:
            raise NotFoundError(
                f"knowledge state not found: {knowledge_id}",
                code="story_state.knowledge_not_found",
            )
        return knowledge

    async def update_entity_change_status(
        self, work_id: UUID, change_id: UUID, status: str
    ) -> EntityStateChange:
        if status not in {item.value for item in EntityChangeStatus}:
            raise ValidationError(
                f"invalid entity change status: {status}",
                code="story_state.invalid_change_status",
            )
        change = await self._repository.update_entity_change_status(work_id, change_id, status)
        if change is None:
            raise NotFoundError(
                f"entity state change not found: {change_id}",
                code="story_state.change_not_found",
            )
        return change

    async def list_timeline(self, work_id: UUID) -> list[TimelineEvent]:
        return await self._repository.list_timeline(work_id)

    async def add_timeline_event(
        self, work_id: UUID, description: str, event_time: str | None, chapter_id: UUID | None
    ) -> TimelineEvent:
        if not description.strip():
            raise ValidationError("description required", code="timeline.description_required")
        return await self._repository.add_timeline_event(
            work_id, description.strip(), event_time, chapter_id
        )

    async def create_foreshadow(
        self,
        work_id: UUID,
        description: str,
        planted_chapter_id: UUID | None = None,
        expected_recover_chapter_id: UUID | None = None,
    ) -> Foreshadow:
        if not description.strip():
            raise ValidationError("description required", code="foreshadow.description_required")
        return await self._repository.add_foreshadow(
            work_id,
            description.strip(),
            planted_chapter_id,
            expected_recover_chapter_id,
        )

    async def get_entity(self, entity_id: UUID) -> Entity:
        entity = await self._repository.get_entity(entity_id)
        if entity is None:
            raise NotFoundError(f"entity not found: {entity_id}", code="entity.not_found")
        return entity

    async def create_entity(
        self,
        work_id: UUID,
        type: str,
        name: str,
        aliases: list[str],
        attributes: dict[str, Any],
    ) -> Entity:
        if type not in {"character", "faction", "location", "rule", "item"}:
            raise ValidationError("invalid entity type", code="entity.invalid_type")
        if not name.strip():
            raise ValidationError("entity name required", code="entity.name_required")
        return await self._repository.add_entity(work_id, type, name.strip(), aliases, attributes)

    async def patch_entity(
        self,
        entity_id: UUID,
        base_version: int,
        *,
        type: str | None = None,
        name: str | None = None,
        aliases: list[str] | None = None,
        attributes: dict[str, Any] | None = None,
    ) -> Entity:
        entity = await self._repository.patch_entity(
            entity_id,
            base_version,
            type=type,
            name=name,
            aliases=aliases,
            attributes=attributes,
        )
        if entity is None:
            raise NotFoundError(f"entity not found: {entity_id}", code="entity.not_found")
        return entity
