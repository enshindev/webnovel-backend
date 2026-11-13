from __future__ import annotations

from typing import Any, Protocol, cast
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from webnovel.modules.assistant.contract import (
    Conversation,
    Idea,
    Message,
    ProjectBrief,
    WorldDraft,
)
from webnovel.modules.assistant.models import (
    ConversationModel,
    IdeaModel,
    MessageModel,
    ProjectBriefModel,
    WorldDraftModel,
)


class AssistantRepository(Protocol):
    async def create_conversation(
        self, scope: str, mode: str, title: str | None, work_id: UUID | None
    ) -> Conversation: ...

    async def get_conversation(self, conversation_id: UUID) -> Conversation | None: ...

    async def list_conversations(
        self, scope: str | None, work_id: UUID | None, limit: int, offset: int
    ) -> list[Conversation]: ...

    async def add_message(
        self,
        conversation_id: UUID,
        role: str,
        content: str,
        citations: list[dict[str, Any]],
        tool_calls: list[dict[str, Any]],
        usage: dict[str, Any] | None,
    ) -> Message: ...

    async def list_messages(
        self, conversation_id: UUID, limit: int, offset: int = 0
    ) -> list[Message]: ...

    async def add_idea(
        self,
        conversation_id: UUID,
        scope: str,
        work_id: UUID | None,
        kind: str,
        content: str,
        tags: list[str],
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
        self, draft_id: UUID, summary: str, nodes: list[dict[str, Any]], edges: list[dict[str, Any]]
    ) -> WorldDraft | None: ...

    async def get_world_draft(self, draft_id: UUID) -> WorldDraft | None: ...

    async def create_brief(self, conversation_id: UUID, values: dict[str, Any]) -> ProjectBrief: ...

    async def get_brief(self, brief_id: UUID) -> ProjectBrief | None: ...

    async def mark_brief_created(self, brief_id: UUID, work_id: UUID) -> None: ...


def _conversation(model: ConversationModel) -> Conversation:
    return Conversation(
        id=model.id,
        scope=model.scope,
        work_id=model.work_id,
        mode=model.mode,
        title=model.title,
        summary=model.summary,
        created_at=model.created_at,
    )


def _message(model: MessageModel) -> Message:
    return Message(
        id=model.id,
        conversation_id=model.conversation_id,
        role=model.role,
        content=model.content,
        citations=cast(list[dict[str, Any]], model.citations),
        tool_calls=cast(list[dict[str, Any]], model.tool_calls),
        usage=cast(dict[str, Any] | None, model.usage),
        created_at=model.created_at,
    )


def _idea(model: IdeaModel) -> Idea:
    return Idea(
        id=model.id,
        scope=model.scope,
        work_id=model.work_id,
        conversation_id=model.conversation_id,
        kind=model.kind,
        content=model.content,
        tags=model.tags,
        status=model.status,
        created_at=model.created_at,
    )


def _draft(model: WorldDraftModel) -> WorldDraft:
    return WorldDraft(
        id=model.id,
        conversation_id=model.conversation_id,
        version=model.version,
        status=model.status,
        summary=model.summary,
        nodes=cast(list[dict[str, Any]], model.nodes),
        edges=cast(list[dict[str, Any]], model.edges),
        created_at=model.created_at,
    )


def _brief(model: ProjectBriefModel) -> ProjectBrief:
    return ProjectBrief(
        id=model.id,
        conversation_id=model.conversation_id,
        world_draft_id=model.world_draft_id,
        title_candidates=model.title_candidates,
        premise=model.premise,
        genre=model.genre,
        target_reader=cast(dict[str, Any], model.target_reader),
        selling_points=model.selling_points,
        core_conflict=model.core_conflict,
        character_core=cast(dict[str, Any], model.character_core),
        tone=model.tone,
        pov=model.pov,
        planned_length=model.planned_length,
        update_cadence=model.update_cadence,
        opening_plan=cast(list[dict[str, Any]], model.opening_plan),
        risks=model.risks,
        sources=cast(list[dict[str, Any]], model.sources),
        status=model.status,
        created_work_id=model.created_work_id,
        created_at=model.created_at,
    )


class SqlAlchemyAssistantRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_conversation(
        self, scope: str, mode: str, title: str | None, work_id: UUID | None
    ) -> Conversation:
        model = ConversationModel(scope=scope, mode=mode, title=title, work_id=work_id)
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return _conversation(model)

    async def get_conversation(self, conversation_id: UUID) -> Conversation | None:
        model = await self._session.get(ConversationModel, conversation_id)
        return _conversation(model) if model is not None else None

    async def list_conversations(
        self, scope: str | None, work_id: UUID | None, limit: int, offset: int
    ) -> list[Conversation]:
        stmt = select(ConversationModel)
        if scope is not None:
            stmt = stmt.where(ConversationModel.scope == scope)
        if work_id is not None:
            stmt = stmt.where(ConversationModel.work_id == work_id)
        stmt = stmt.order_by(ConversationModel.updated_at.desc()).offset(offset).limit(limit)
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_conversation(row) for row in rows]

    async def add_message(
        self,
        conversation_id: UUID,
        role: str,
        content: str,
        citations: list[dict[str, Any]],
        tool_calls: list[dict[str, Any]],
        usage: dict[str, Any] | None,
    ) -> Message:
        model = MessageModel(
            conversation_id=conversation_id,
            role=role,
            content=content,
            citations=citations,
            tool_calls=tool_calls,
            usage=usage,
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return _message(model)

    async def list_messages(
        self, conversation_id: UUID, limit: int, offset: int = 0
    ) -> list[Message]:
        stmt = (
            select(MessageModel)
            .where(MessageModel.conversation_id == conversation_id)
            .order_by(MessageModel.created_at.asc())
            .offset(offset)
            .limit(limit)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_message(row) for row in rows]

    async def add_idea(
        self,
        conversation_id: UUID,
        scope: str,
        work_id: UUID | None,
        kind: str,
        content: str,
        tags: list[str],
    ) -> Idea:
        model = IdeaModel(
            conversation_id=conversation_id,
            scope=scope,
            work_id=work_id,
            kind=kind,
            content=content,
            tags=tags,
            status="draft",
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return _idea(model)

    async def list_ideas(self, conversation_id: UUID) -> list[Idea]:
        stmt = (
            select(IdeaModel)
            .where(IdeaModel.conversation_id == conversation_id)
            .order_by(IdeaModel.created_at.desc())
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_idea(row) for row in rows]

    async def create_world_draft(
        self,
        conversation_id: UUID,
        summary: str,
        nodes: list[dict[str, Any]],
        edges: list[dict[str, Any]],
    ) -> WorldDraft:
        model = WorldDraftModel(
            conversation_id=conversation_id,
            version=1,
            status="draft",
            summary=summary,
            nodes=nodes,
            edges=edges,
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return _draft(model)

    async def add_world_draft_version(
        self, draft_id: UUID, summary: str, nodes: list[dict[str, Any]], edges: list[dict[str, Any]]
    ) -> WorldDraft | None:
        previous = await self._session.get(WorldDraftModel, draft_id)
        if previous is None:
            return None
        version = (
            await self._session.execute(
                select(func.max(WorldDraftModel.version)).where(
                    WorldDraftModel.conversation_id == previous.conversation_id
                )
            )
        ).scalar_one()
        model = WorldDraftModel(
            conversation_id=previous.conversation_id,
            version=int(version) + 1,
            status="draft",
            summary=summary,
            nodes=nodes,
            edges=edges,
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return _draft(model)

    async def get_world_draft(self, draft_id: UUID) -> WorldDraft | None:
        model = await self._session.get(WorldDraftModel, draft_id)
        return _draft(model) if model is not None else None

    async def create_brief(self, conversation_id: UUID, values: dict[str, Any]) -> ProjectBrief:
        model = ProjectBriefModel(conversation_id=conversation_id, **values)
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return _brief(model)

    async def get_brief(self, brief_id: UUID) -> ProjectBrief | None:
        model = await self._session.get(ProjectBriefModel, brief_id)
        return _brief(model) if model is not None else None

    async def mark_brief_created(self, brief_id: UUID, work_id: UUID) -> None:
        model = await self._session.get(ProjectBriefModel, brief_id)
        if model is not None:
            model.created_work_id = work_id
            model.status = "created"
            await self._session.flush()
