from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field

from webnovel.entrypoints.api.deps import MemoryServiceDep
from webnovel.modules.memory.contract import ProposalStatus

router = APIRouter(tags=["memory"])


class ProposalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    work_id: UUID
    run_id: UUID
    kind: str
    target_entity_id: UUID | None
    after: dict[str, Any]
    confidence: float | None
    source_span: dict[str, Any] | None
    base_entity_version: int | None
    status: str
    created_at: datetime


class ProposalList(BaseModel):
    items: list[ProposalOut]


class EntityOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    work_id: UUID
    type: str
    name: str
    aliases: list[str]
    attributes: dict[str, Any]
    version: int
    first_chapter_id: UUID | None


class EntityList(BaseModel):
    items: list[EntityOut]


class EntityCreate(BaseModel):
    type: str
    name: str = Field(min_length=1, max_length=200)
    aliases: list[str] = Field(default_factory=list)
    attributes: dict[str, Any] = Field(default_factory=dict)


class EntityPatch(BaseModel):
    base_version: int = Field(ge=0)
    type: str | None = None
    name: str | None = None
    aliases: list[str] | None = None
    attributes: dict[str, Any] | None = None


class TimelineEventCreate(BaseModel):
    description: str = Field(min_length=1, max_length=4_000)
    event_time: str | None = Field(default=None, max_length=128)
    chapter_id: UUID | None = None


class TimelineEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    work_id: UUID
    chapter_id: UUID | None
    event_time: str | None
    description: str
    entity_ids: list[str]


class TimelineEventList(BaseModel):
    items: list[TimelineEventOut]


class StoryEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

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


class StoryEventList(BaseModel):
    items: list[StoryEventOut]


class KnowledgeStateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

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


class KnowledgeStateList(BaseModel):
    items: list[KnowledgeStateOut]


class ContradictionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    kind: str
    severity: str
    message: str
    chapter_number: int
    evidence: list[dict[str, Any]]


class ContradictionList(BaseModel):
    items: list[ContradictionOut]


class ForeshadowCreate(BaseModel):
    description: str = Field(min_length=1, max_length=4_000)
    planted_chapter_id: UUID | None = None
    expected_recover_chapter_id: UUID | None = None


class ForeshadowOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    work_id: UUID
    description: str
    planted_chapter_id: UUID | None
    expected_recover_chapter_id: UUID | None
    status: str


class ForeshadowList(BaseModel):
    items: list[ForeshadowOut]


class SummaryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    work_id: UUID
    chapter_id: UUID
    content: str
    based_on_version_id: UUID
    status: str


class ResolveBody(BaseModel):
    action: Literal["accept", "modify", "reject"]
    base_entity_version: int = Field(default=0, ge=0)
    payload: dict[str, Any] | None = None


class ResolvedOut(BaseModel):
    proposal: ProposalOut
    entity: EntityOut | None


@router.get("/works/{work_id}/proposals", response_model=ProposalList)
async def list_proposals(
    work_id: UUID, service: MemoryServiceDep, status: ProposalStatus | None = None
) -> ProposalList:
    proposals = await service.list_proposals(work_id, status)
    return ProposalList(items=[ProposalOut.model_validate(proposal) for proposal in proposals])


@router.post("/proposals/{proposal_id}/resolve", response_model=ResolvedOut)
async def resolve_proposal(
    proposal_id: UUID, body: ResolveBody, service: MemoryServiceDep
) -> ResolvedOut:
    resolved = await service.resolve_proposal(
        proposal_id,
        body.action,
        base_entity_version=body.base_entity_version,
        modified_payload=body.payload,
    )
    return ResolvedOut(
        proposal=ProposalOut.model_validate(resolved.proposal),
        entity=EntityOut.model_validate(resolved.entity) if resolved.entity else None,
    )


@router.post("/works/{work_id}/entities", response_model=EntityOut, status_code=201)
async def create_entity(work_id: UUID, body: EntityCreate, service: MemoryServiceDep) -> EntityOut:
    entity = await service.create_entity(
        work_id, body.type, body.name, body.aliases, body.attributes
    )
    return EntityOut.model_validate(entity)


@router.get("/entities/{entity_id}", response_model=EntityOut)
async def get_entity(entity_id: UUID, service: MemoryServiceDep) -> EntityOut:
    return EntityOut.model_validate(await service.get_entity(entity_id))


@router.patch("/entities/{entity_id}", response_model=EntityOut)
async def patch_entity(entity_id: UUID, body: EntityPatch, service: MemoryServiceDep) -> EntityOut:
    entity = await service.patch_entity(
        entity_id,
        body.base_version,
        type=body.type,
        name=body.name,
        aliases=body.aliases,
        attributes=body.attributes,
    )
    return EntityOut.model_validate(entity)


@router.get("/works/{work_id}/entities", response_model=EntityList)
async def list_entities(work_id: UUID, service: MemoryServiceDep) -> EntityList:
    entities = await service.list_entities(work_id)
    return EntityList(items=[EntityOut.model_validate(entity) for entity in entities])


@router.get("/works/{work_id}/timeline", response_model=TimelineEventList)
async def list_timeline(work_id: UUID, service: MemoryServiceDep) -> TimelineEventList:
    events = await service.list_timeline(work_id)
    return TimelineEventList(items=[TimelineEventOut.model_validate(event) for event in events])


@router.post(
    "/works/{work_id}/timeline",
    response_model=TimelineEventOut,
    status_code=201,
)
async def create_timeline_event(
    work_id: UUID, body: TimelineEventCreate, service: MemoryServiceDep
) -> TimelineEventOut:
    event = await service.add_timeline_event(
        work_id, body.description, body.event_time, body.chapter_id
    )
    return TimelineEventOut.model_validate(event)


@router.get("/works/{work_id}/story-state/events", response_model=StoryEventList)
async def list_story_events(
    work_id: UUID,
    service: MemoryServiceDep,
    from_chapter: int | None = None,
    to_chapter: int | None = None,
) -> StoryEventList:
    events = await service.list_story_events(
        work_id, from_chapter=from_chapter, to_chapter=to_chapter
    )
    return StoryEventList(items=[StoryEventOut.model_validate(event) for event in events])


@router.get("/works/{work_id}/story-state/contradictions", response_model=ContradictionList)
async def list_contradictions(work_id: UUID, service: MemoryServiceDep) -> ContradictionList:
    contradictions = await service.contradictions(work_id)
    return ContradictionList(
        items=[ContradictionOut.model_validate(item) for item in contradictions]
    )


@router.get("/works/{work_id}/story-state/knowledge", response_model=KnowledgeStateList)
async def list_knowledge(
    work_id: UUID,
    service: MemoryServiceDep,
    character_id: UUID | None = None,
    at_chapter: int | None = None,
) -> KnowledgeStateList:
    states = await service.list_knowledge(work_id, character_id=character_id, at_chapter=at_chapter)
    return KnowledgeStateList(items=[KnowledgeStateOut.model_validate(state) for state in states])


@router.get("/works/{work_id}/story-state/who-knows", response_model=KnowledgeStateList)
async def who_knows(
    work_id: UUID,
    service: MemoryServiceDep,
    fact_key: str,
    at_chapter: int | None = None,
) -> KnowledgeStateList:
    states = await service.who_knows(work_id, fact_key, at_chapter)
    return KnowledgeStateList(items=[KnowledgeStateOut.model_validate(state) for state in states])


@router.get("/works/{work_id}/foreshadows", response_model=ForeshadowList)
async def list_foreshadows(work_id: UUID, service: MemoryServiceDep) -> ForeshadowList:
    foreshadows = await service.list_foreshadows(work_id)
    return ForeshadowList(
        items=[ForeshadowOut.model_validate(foreshadow) for foreshadow in foreshadows]
    )


@router.post(
    "/works/{work_id}/foreshadows",
    response_model=ForeshadowOut,
    status_code=201,
)
async def create_foreshadow(
    work_id: UUID, body: ForeshadowCreate, service: MemoryServiceDep
) -> ForeshadowOut:
    foreshadow = await service.create_foreshadow(
        work_id,
        body.description,
        body.planted_chapter_id,
        body.expected_recover_chapter_id,
    )
    return ForeshadowOut.model_validate(foreshadow)


@router.get("/chapters/{chapter_id}/summary", response_model=SummaryOut)
async def get_summary(chapter_id: UUID, service: MemoryServiceDep) -> SummaryOut:
    return SummaryOut.model_validate(await service.get_summary(chapter_id))
