from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any
from uuid import UUID

import structlog

from webnovel.kernel.errors import NotFoundError, ValidationError
from webnovel.modules.memory.contract import (
    ChangeProposal,
    Entity,
    ExtractionRun,
    Foreshadow,
    MemoryIndexer,
    MemoryService,
    ProposalStatus,
    ResolvedProposal,
    Summary,
    TimelineEvent,
)
from webnovel.modules.memory.repository import MemoryRepository

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
        self, work_id: UUID, chapter_id: UUID, version_id: UUID
    ) -> ExtractionRun:
        run = await self._repository.create_run(work_id, chapter_id, version_id, trigger="accept")
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

    async def list_entities(self, work_id: UUID) -> list[Entity]:
        return await self._repository.list_entities(work_id)

    async def get_summary(self, chapter_id: UUID) -> Summary:
        summary = await self._repository.get_summary(chapter_id)
        if summary is None:
            raise NotFoundError(f"summary not found: {chapter_id}", code="summary.not_found")
        return summary

    async def list_foreshadows(self, work_id: UUID) -> list[Foreshadow]:
        return await self._repository.list_foreshadows(work_id)

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
