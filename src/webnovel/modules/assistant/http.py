from __future__ import annotations

import json
from collections.abc import AsyncIterator
from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from webnovel.entrypoints.api.deps import AssistantServiceDep, require_assistant

router = APIRouter(
    prefix="/experiments/assistant",
    tags=["assistant"],
    dependencies=[Depends(require_assistant)],
)


class ConversationCreate(BaseModel):
    scope: Literal["work", "ideation"]
    mode: str
    title: str | None = Field(default=None, max_length=200)
    work_id: UUID | None = None


class MessageCreate(BaseModel):
    content: str = Field(min_length=1, max_length=20_000)


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    conversation_id: UUID
    role: str
    content: str
    citations: list[dict[str, Any]]
    tool_calls: list[dict[str, Any]]
    usage: dict[str, Any] | None
    created_at: datetime


class MessageList(BaseModel):
    items: list[MessageOut]


class IdeaCreate(BaseModel):
    kind: str = "premise"
    content: str = Field(min_length=1, max_length=20_000)
    tags: list[str] = Field(default_factory=list)


class IdeaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    scope: str
    work_id: UUID | None
    conversation_id: UUID
    kind: str
    content: str
    tags: list[str]
    status: str
    created_at: datetime


class IdeaList(BaseModel):
    items: list[IdeaOut]


class ConversationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    scope: str
    work_id: UUID | None
    mode: str
    title: str | None
    summary: str | None
    created_at: datetime


class WorldDraftCreate(BaseModel):
    summary: str = ""
    nodes: list[dict[str, Any]] = Field(default_factory=list)
    edges: list[dict[str, Any]] = Field(default_factory=list)


class WorldDraftOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    conversation_id: UUID
    version: int
    status: str
    summary: str
    nodes: list[dict[str, Any]]
    edges: list[dict[str, Any]]
    created_at: datetime | None


class BriefCreate(BaseModel):
    world_draft_id: UUID | None = None
    title_candidates: list[str] = Field(default_factory=list)
    premise: str
    genre: str | None = None
    target_reader: dict[str, Any] = Field(default_factory=dict)
    selling_points: list[str] = Field(default_factory=list)
    core_conflict: str = ""
    character_core: dict[str, Any] = Field(default_factory=dict)
    tone: str | None = None
    pov: str | None = None
    planned_length: str | None = None
    update_cadence: str | None = None
    opening_plan: list[dict[str, Any]] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    sources: list[dict[str, Any]] = Field(default_factory=list)


class BriefOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    conversation_id: UUID
    world_draft_id: UUID | None
    title_candidates: list[str]
    premise: str
    genre: str | None
    target_reader: dict[str, Any]
    selling_points: list[str]
    core_conflict: str
    character_core: dict[str, Any]
    tone: str | None
    pov: str | None
    planned_length: str | None
    update_cadence: str | None
    opening_plan: list[dict[str, Any]]
    risks: list[str]
    sources: list[dict[str, Any]]
    status: str
    created_work_id: UUID | None
    created_at: datetime


class CreatedWorkOut(BaseModel):
    work_id: UUID


@router.post("/conversations", response_model=ConversationOut, status_code=status.HTTP_201_CREATED)
async def create_conversation(
    body: ConversationCreate, service: AssistantServiceDep
) -> ConversationOut:
    conversation = await service.create_conversation(
        body.scope, body.mode, body.title, body.work_id
    )
    return ConversationOut.model_validate(conversation)


@router.get("/conversations", response_model=list[ConversationOut])
async def list_conversations(
    service: AssistantServiceDep,
    scope: Literal["work", "ideation"] | None = None,
    work_id: UUID | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[ConversationOut]:
    conversations = await service.list_conversations(
        scope, work_id, min(max(limit, 1), 200), max(offset, 0)
    )
    return [ConversationOut.model_validate(item) for item in conversations]


@router.get("/conversations/{conversation_id}", response_model=ConversationOut)
async def get_conversation(conversation_id: UUID, service: AssistantServiceDep) -> ConversationOut:
    return ConversationOut.model_validate(await service.get_conversation(conversation_id))


@router.post(
    "/conversations/{conversation_id}/messages",
    response_model=MessageOut,
    status_code=status.HTTP_201_CREATED,
)
async def send_message(
    conversation_id: UUID, body: MessageCreate, service: AssistantServiceDep
) -> MessageOut:
    message = await service.send_message(conversation_id, body.content)
    return MessageOut.model_validate(message)


@router.post("/conversations/{conversation_id}/messages/stream")
async def stream_message(
    conversation_id: UUID, body: MessageCreate, service: AssistantServiceDep
) -> StreamingResponse:
    async def events() -> AsyncIterator[str]:
        async for event in service.stream_message(conversation_id, body.content):
            if event.type == "delta":
                payload = json.dumps({"text": event.text}, ensure_ascii=False)
                yield f"event: delta\ndata: {payload}\n\n"
            elif event.type == "done":
                payload = json.dumps(
                    {
                        "message_id": str(event.message.id) if event.message else None,
                        "citations": event.citations,
                    },
                    ensure_ascii=False,
                )
                yield f"event: done\ndata: {payload}\n\n"
                return
            else:
                payload = json.dumps({"error": event.text}, ensure_ascii=False)
                yield f"event: error\ndata: {payload}\n\n"
                return

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/conversations/{conversation_id}/messages", response_model=MessageList)
async def list_messages(
    conversation_id: UUID,
    service: AssistantServiceDep,
    limit: int = 100,
    offset: int = 0,
) -> MessageList:
    messages = await service.list_messages(conversation_id, min(max(limit, 1), 500), max(offset, 0))
    return MessageList(items=[MessageOut.model_validate(message) for message in messages])


@router.post(
    "/conversations/{conversation_id}/ideas",
    response_model=IdeaOut,
    status_code=status.HTTP_201_CREATED,
)
async def save_idea(
    conversation_id: UUID, body: IdeaCreate, service: AssistantServiceDep
) -> IdeaOut:
    idea = await service.save_idea(conversation_id, body.kind, body.content, body.tags)
    return IdeaOut.model_validate(idea)


@router.get("/conversations/{conversation_id}/ideas", response_model=IdeaList)
async def list_ideas(conversation_id: UUID, service: AssistantServiceDep) -> IdeaList:
    ideas = await service.list_ideas(conversation_id)
    return IdeaList(items=[IdeaOut.model_validate(idea) for idea in ideas])


@router.post(
    "/conversations/{conversation_id}/world-drafts",
    response_model=WorldDraftOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_world_draft(
    conversation_id: UUID, body: WorldDraftCreate, service: AssistantServiceDep
) -> WorldDraftOut:
    draft = await service.create_world_draft(conversation_id, body.summary, body.nodes, body.edges)
    return WorldDraftOut.model_validate(draft)


@router.post(
    "/world-drafts/{draft_id}/versions",
    response_model=WorldDraftOut,
    status_code=status.HTTP_201_CREATED,
)
async def add_world_draft_version(
    draft_id: UUID, body: WorldDraftCreate, service: AssistantServiceDep
) -> WorldDraftOut:
    draft = await service.add_world_draft_version(draft_id, body.summary, body.nodes, body.edges)
    return WorldDraftOut.model_validate(draft)


@router.get("/world-drafts/{draft_id}", response_model=WorldDraftOut)
async def get_world_draft(draft_id: UUID, service: AssistantServiceDep) -> WorldDraftOut:
    return WorldDraftOut.model_validate(await service.get_world_draft(draft_id))


@router.post(
    "/conversations/{conversation_id}/briefs",
    response_model=BriefOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_brief(
    conversation_id: UUID, body: BriefCreate, service: AssistantServiceDep
) -> BriefOut:
    brief = await service.create_brief(conversation_id, body.model_dump())
    return BriefOut.model_validate(brief)


@router.get("/briefs/{brief_id}", response_model=BriefOut)
async def get_brief(brief_id: UUID, service: AssistantServiceDep) -> BriefOut:
    return BriefOut.model_validate(await service.get_brief(brief_id))


@router.post("/briefs/{brief_id}/create-work", response_model=CreatedWorkOut)
async def create_work(
    brief_id: UUID,
    service: AssistantServiceDep,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
) -> CreatedWorkOut:
    work_id = await service.create_work(brief_id, idempotency_key)
    return CreatedWorkOut(work_id=work_id)
