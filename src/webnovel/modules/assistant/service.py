from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any
from uuid import UUID

from webnovel.kernel.errors import ConflictError, NotFoundError, ValidationError
from webnovel.modules.assistant.chat import AssistantChatRunner
from webnovel.modules.assistant.contract import (
    AssistantEvent,
    AssistantService,
    Conversation,
    Idea,
    Message,
    ProjectBrief,
    WorldDraft,
)
from webnovel.modules.assistant.repository import AssistantRepository
from webnovel.modules.audit.contract import AuditRecorder
from webnovel.modules.generation.contract import PreferenceRecorder
from webnovel.modules.memory.contract import EntityMaterializer
from webnovel.modules.outbox.contract import OutboxService
from webnovel.modules.works.contract import WorkService

SCOPES = {"work", "ideation"}
MODES = {
    "ideation": {"direction", "world", "cast"},
    "work": {"inspiration", "story_qa", "revision"},
}


class AssistantServiceImpl(AssistantService):
    def __init__(
        self,
        repository: AssistantRepository,
        work_service: WorkService,
        materializer: EntityMaterializer | None = None,
        chat: AssistantChatRunner | None = None,
        audit: AuditRecorder | None = None,
        outbox: OutboxService | None = None,
        preference: PreferenceRecorder | None = None,
    ) -> None:
        self._repository = repository
        self._work_service = work_service
        self._materializer = materializer
        self._chat = chat
        self._audit = audit
        self._outbox = outbox
        self._preference = preference

    async def create_conversation(
        self, scope: str, mode: str, title: str | None, work_id: UUID | None
    ) -> Conversation:
        if scope not in SCOPES:
            raise ValidationError(f"invalid scope: {scope}", code="assistant.invalid_scope")
        if mode not in MODES[scope]:
            raise ValidationError(f"invalid mode: {mode}", code="assistant.invalid_mode")
        if scope == "work" and work_id is None:
            raise ValidationError("work scope requires work_id", code="assistant.work_required")
        if scope == "ideation" and work_id is not None:
            raise ValidationError(
                "ideation scope must not bind a work", code="assistant.work_not_allowed"
            )
        return await self._repository.create_conversation(scope, mode, title, work_id)

    async def get_conversation(self, conversation_id: UUID) -> Conversation:
        conversation = await self._repository.get_conversation(conversation_id)
        if conversation is None:
            raise NotFoundError(
                f"conversation not found: {conversation_id}",
                code="assistant.conversation_not_found",
            )
        return conversation

    async def list_conversations(
        self, scope: str | None, work_id: UUID | None, limit: int = 50, offset: int = 0
    ) -> list[Conversation]:
        return await self._repository.list_conversations(scope, work_id, limit, offset)

    async def send_message(self, conversation_id: UUID, content: str) -> Message:
        await self.get_conversation(conversation_id)
        if self._chat is None:
            raise ValidationError(
                "assistant model is not configured", code="assistant.not_configured"
            )
        try:
            return await self._chat.run(conversation_id, content)
        except ValueError as exc:
            raise ValidationError(str(exc), code="assistant.invalid_message") from exc

    async def stream_message(
        self, conversation_id: UUID, content: str
    ) -> AsyncIterator[AssistantEvent]:
        await self.get_conversation(conversation_id)
        if self._chat is None:
            raise ValidationError(
                "assistant model is not configured", code="assistant.not_configured"
            )
        async for event in self._chat.stream(conversation_id, content):
            yield event

    async def list_messages(
        self, conversation_id: UUID, limit: int = 100, offset: int = 0
    ) -> list[Message]:
        await self.get_conversation(conversation_id)
        return await self._repository.list_messages(conversation_id, limit, offset)

    async def save_idea(
        self,
        conversation_id: UUID,
        kind: str,
        content: str,
        tags: list[str] | None = None,
    ) -> Idea:
        conversation = await self.get_conversation(conversation_id)
        if not content.strip():
            raise ValidationError("idea content required", code="assistant.idea_empty")
        idea = await self._repository.add_idea(
            conversation_id,
            conversation.scope,
            conversation.work_id,
            kind,
            content,
            tags or [],
        )
        if self._preference is not None:
            try:
                await self._preference.saved_idea(idea.id, conversation.scope)
            except Exception:
                import logging

                logging.getLogger(__name__).exception("assistant.saved_idea_event_failed")
        return idea

    async def list_ideas(self, conversation_id: UUID) -> list[Idea]:
        await self.get_conversation(conversation_id)
        return await self._repository.list_ideas(conversation_id)

    async def create_world_draft(
        self,
        conversation_id: UUID,
        summary: str,
        nodes: list[dict[str, Any]],
        edges: list[dict[str, Any]],
    ) -> WorldDraft:
        await self.get_conversation(conversation_id)
        return await self._repository.create_world_draft(conversation_id, summary, nodes, edges)

    async def add_world_draft_version(
        self,
        draft_id: UUID,
        summary: str,
        nodes: list[dict[str, Any]],
        edges: list[dict[str, Any]],
    ) -> WorldDraft:
        draft = await self._repository.add_world_draft_version(draft_id, summary, nodes, edges)
        if draft is None:
            raise NotFoundError(
                f"world draft not found: {draft_id}", code="assistant.draft_not_found"
            )
        return draft

    async def get_world_draft(self, draft_id: UUID) -> WorldDraft:
        draft = await self._repository.get_world_draft(draft_id)
        if draft is None:
            raise NotFoundError(
                f"world draft not found: {draft_id}", code="assistant.draft_not_found"
            )
        return draft

    async def create_brief(self, conversation_id: UUID, values: dict[str, Any]) -> ProjectBrief:
        conversation = await self.get_conversation(conversation_id)
        if conversation.scope != "ideation":
            raise ValidationError("brief is ideation-only", code="assistant.brief_scope")
        if not str(values.get("premise", "")).strip():
            raise ValidationError("premise is required", code="assistant.premise_required")
        payload = {
            "world_draft_id": values.get("world_draft_id"),
            "title_candidates": values.get("title_candidates", []),
            "premise": values["premise"],
            "genre": values.get("genre"),
            "target_reader": values.get("target_reader", {}),
            "selling_points": values.get("selling_points", []),
            "core_conflict": values.get("core_conflict", ""),
            "character_core": values.get("character_core", {}),
            "tone": values.get("tone"),
            "pov": values.get("pov"),
            "planned_length": values.get("planned_length"),
            "update_cadence": values.get("update_cadence"),
            "opening_plan": values.get("opening_plan", []),
            "risks": values.get("risks", []),
            "sources": values.get("sources", []),
            "status": "draft",
        }
        return await self._repository.create_brief(conversation_id, payload)

    async def get_brief(self, brief_id: UUID) -> ProjectBrief:
        brief = await self._repository.get_brief(brief_id)
        if brief is None:
            raise NotFoundError(f"brief not found: {brief_id}", code="assistant.brief_not_found")
        return brief

    async def create_work(self, brief_id: UUID, idempotency_key: str) -> UUID:
        if not idempotency_key.strip():
            raise ValidationError("idempotency key required", code="assistant.idempotency_required")
        brief = await self.get_brief(brief_id)
        if brief.created_work_id is not None:
            return brief.created_work_id
        if brief.status == "created":
            raise ConflictError("brief already created", code="assistant.brief_created")

        title = brief.title_candidates[0] if brief.title_candidates else brief.premise[:40]
        work = await self._work_service.create(title=title, genre=brief.genre)
        if brief.world_draft_id is not None and self._materializer is not None:
            draft = await self.get_world_draft(brief.world_draft_id)
            await self._materializer.materialize(work.id, draft.nodes, draft.edges)
        await self._repository.mark_brief_created(brief.id, work.id)
        if self._audit is not None:
            await self._audit.record(
                "assistant.create_work",
                target_type="work",
                target_id=str(work.id),
                metadata={"brief_id": str(brief.id)},
            )
        if self._outbox is not None:
            await self._outbox.emit(
                "work", work.id, "assistant.work_created", {"brief_id": str(brief.id)}
            )
        return work.id
