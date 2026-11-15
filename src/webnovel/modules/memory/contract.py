from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any, Protocol
from uuid import UUID


class ExtractionStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    PARTIAL = "partial"
    FAILED = "failed"
    SUCCEEDED = "succeeded"


class ProposalStatus(StrEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    MODIFIED = "modified"
    REJECTED = "rejected"
    STALE = "stale"


@dataclass(frozen=True, slots=True)
class ExtractionRun:
    id: UUID
    work_id: UUID
    chapter_id: UUID
    version_id: UUID
    status: ExtractionStatus
    created_at: datetime


@dataclass(frozen=True, slots=True)
class Summary:
    id: UUID
    work_id: UUID
    chapter_id: UUID
    content: str
    based_on_version_id: UUID
    status: str


@dataclass(frozen=True, slots=True)
class Entity:
    id: UUID
    work_id: UUID
    type: str
    name: str
    aliases: list[str]
    attributes: dict[str, Any]
    version: int
    first_chapter_id: UUID | None


@dataclass(frozen=True, slots=True)
class ChangeProposal:
    id: UUID
    work_id: UUID
    run_id: UUID
    kind: str
    target_entity_id: UUID | None
    after: dict[str, Any]
    confidence: float | None
    source_span: dict[str, Any] | None
    base_entity_version: int | None
    status: ProposalStatus
    created_at: datetime


@dataclass(frozen=True, slots=True)
class ResolvedProposal:
    proposal: ChangeProposal
    entity: Entity | None


@dataclass(frozen=True, slots=True)
class EntityRelation:
    id: UUID
    work_id: UUID
    from_entity_id: UUID
    to_entity_id: UUID
    relation_type: str
    since_chapter_id: UUID | None


@dataclass(frozen=True, slots=True)
class StoryEvent:
    id: UUID
    work_id: UUID
    chapter_id: UUID
    chapter_number: int
    event_index: int
    summary: str
    time_text: str | None
    location: str | None
    participants: list[dict[str, Any]]
    changes: dict[str, Any]
    confidence: float | None
    status: str


@dataclass(frozen=True, slots=True)
class Contradiction:
    kind: str
    severity: str
    message: str
    chapter_number: int
    evidence: list[dict[str, Any]]


@dataclass(frozen=True, slots=True)
class KnowledgeState:
    id: UUID
    work_id: UUID
    character_id: UUID | None
    character_name: str
    fact_key: str
    fact_value: dict[str, Any]
    state: str
    chapter_number: int
    confidence: float | None
    status: str


@dataclass(frozen=True, slots=True)
class TimelineEvent:
    id: UUID
    work_id: UUID
    chapter_id: UUID | None
    event_time: str | None
    description: str
    entity_ids: list[str]


@dataclass(frozen=True, slots=True)
class Foreshadow:
    id: UUID
    work_id: UUID
    description: str
    planted_chapter_id: UUID | None
    expected_recover_chapter_id: UUID | None
    status: str


@dataclass(frozen=True, slots=True)
class MemoryChunk:
    source: str
    ref: str
    text: str
    tokens: int


class MemoryIndexer(Protocol):
    async def index_summary(self, summary: Summary) -> None: ...

    async def index_entity(self, entity: Entity) -> None: ...

    async def index_chapter(
        self, work_id: UUID, chapter_id: UUID, version_id: UUID, text: str
    ) -> None: ...


class EntityLookup(Protocol):
    async def list_entities(self, work_id: UUID) -> list[Entity]: ...


class EntityMaterializer(Protocol):
    async def materialize(
        self,
        work_id: UUID,
        nodes: list[dict[str, Any]],
        edges: list[dict[str, Any]],
    ) -> dict[str, UUID]: ...


class MemoryRetrievalService(Protocol):
    async def retrieve(self, work_id: UUID, query: str, limit: int = 6) -> list[MemoryChunk]: ...


class MemoryService(Protocol):
    async def start_extraction(
        self, work_id: UUID, chapter_id: UUID, version_id: UUID
    ) -> ExtractionRun: ...

    async def list_proposals(
        self, work_id: UUID, status: ProposalStatus | None = None
    ) -> list[ChangeProposal]: ...

    async def resolve_proposal(
        self,
        proposal_id: UUID,
        action: str,
        *,
        base_entity_version: int,
        modified_payload: dict[str, Any] | None = None,
    ) -> ResolvedProposal: ...

    async def list_entities(self, work_id: UUID) -> list[Entity]: ...

    async def get_summary(self, chapter_id: UUID) -> Summary: ...

    async def list_foreshadows(self, work_id: UUID) -> list[Foreshadow]: ...

    async def list_timeline(self, work_id: UUID) -> list[TimelineEvent]: ...

    async def add_timeline_event(
        self, work_id: UUID, description: str, event_time: str | None, chapter_id: UUID | None
    ) -> TimelineEvent: ...

    async def list_story_events(
        self,
        work_id: UUID,
        *,
        from_chapter: int | None = None,
        to_chapter: int | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[StoryEvent]: ...

    async def list_knowledge(
        self,
        work_id: UUID,
        *,
        character_id: UUID | None = None,
        at_chapter: int | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[KnowledgeState]: ...

    async def who_knows(
        self,
        work_id: UUID,
        fact_key: str,
        at_chapter: int | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[KnowledgeState]: ...

    async def contradictions(self, work_id: UUID) -> list[Contradiction]: ...

    async def list_relations(
        self, work_id: UUID, entity_id: UUID | None = None, limit: int = 100, offset: int = 0
    ) -> list[EntityRelation]: ...

    async def create_foreshadow(
        self,
        work_id: UUID,
        description: str,
        planted_chapter_id: UUID | None = None,
        expected_recover_chapter_id: UUID | None = None,
    ) -> Foreshadow: ...

    async def get_entity(self, entity_id: UUID) -> Entity: ...

    async def create_entity(
        self,
        work_id: UUID,
        type: str,
        name: str,
        aliases: list[str],
        attributes: dict[str, Any],
    ) -> Entity: ...

    async def patch_entity(
        self,
        entity_id: UUID,
        base_version: int,
        *,
        type: str | None = None,
        name: str | None = None,
        aliases: list[str] | None = None,
        attributes: dict[str, Any] | None = None,
    ) -> Entity: ...
