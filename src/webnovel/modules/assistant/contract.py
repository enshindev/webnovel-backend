from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID


@dataclass(frozen=True, slots=True)
class Conversation:
    id: UUID
    scope: str
    work_id: UUID | None
    mode: str
    title: str | None
    summary: str | None
    created_at: datetime


@dataclass(frozen=True, slots=True)
class Message:
    id: UUID
    conversation_id: UUID
    role: str
    content: str
    citations: list[dict[str, Any]]
    tool_calls: list[dict[str, Any]]
    usage: dict[str, Any] | None
    created_at: datetime


@dataclass(frozen=True, slots=True)
class AssistantEvent:
    type: str
    text: str = ""
    message: Message | None = None
    citations: list[dict[str, Any]] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class Idea:
    id: UUID
    scope: str
    work_id: UUID | None
    conversation_id: UUID
    kind: str
    content: str
    tags: list[str]
    status: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class WorldDraft:
    id: UUID
    conversation_id: UUID
    version: int
    status: str
    summary: str
    nodes: list[dict[str, Any]] = field(default_factory=list)
    edges: list[dict[str, Any]] = field(default_factory=list)
    created_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class ProjectBrief:
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


class ToolExecutor(Protocol):
    async def execute(self, name: str, work_id: UUID, arguments: str) -> Any: ...


class AssistantService(Protocol):
    async def create_conversation(
        self, scope: str, mode: str, title: str | None, work_id: UUID | None
    ) -> Conversation: ...

    async def get_conversation(self, conversation_id: UUID) -> Conversation: ...

    async def list_conversations(
        self, scope: str | None, work_id: UUID | None, limit: int, offset: int
    ) -> list[Conversation]: ...

    async def send_message(self, conversation_id: UUID, content: str) -> Message: ...

    def stream_message(
        self, conversation_id: UUID, content: str
    ) -> AsyncIterator[AssistantEvent]: ...

    async def list_messages(
        self, conversation_id: UUID, limit: int = 100, offset: int = 0
    ) -> list[Message]: ...

    async def save_idea(
        self,
        conversation_id: UUID,
        kind: str,
        content: str,
        tags: list[str] | None = None,
    ) -> Idea: ...

    async def list_ideas(self, conversation_id: UUID) -> list[Idea]: ...

    async def create_world_draft(
        self,
        conversation_id: UUID,
        summary: str,
        nodes: list[dict[str, Any]],
        edges: list[dict[str, Any]],
    ) -> WorldDraft: ...

    async def add_world_draft_version(
        self,
        draft_id: UUID,
        summary: str,
        nodes: list[dict[str, Any]],
        edges: list[dict[str, Any]],
    ) -> WorldDraft: ...

    async def get_world_draft(self, draft_id: UUID) -> WorldDraft: ...

    async def create_brief(self, conversation_id: UUID, values: dict[str, Any]) -> ProjectBrief: ...

    async def get_brief(self, brief_id: UUID) -> ProjectBrief: ...

    async def create_work(self, brief_id: UUID, idempotency_key: str) -> UUID: ...
