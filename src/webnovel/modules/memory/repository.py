from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any, Protocol, cast
from uuid import UUID

from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from webnovel.kernel.errors import ConflictError
from webnovel.modules.memory.contract import (
    ChangeProposal,
    Entity,
    EntityRelation,
    EntityStateChange,
    ExtractionRun,
    ExtractionStatus,
    Foreshadow,
    KnowledgeState,
    ProposalStatus,
    ResolvedProposal,
    StoryEvent,
    Summary,
    TimelineEvent,
)
from webnovel.modules.memory.models import (
    ChangeProposalModel,
    EntityModel,
    EntityRelationModel,
    EntityRevisionModel,
    EntityStateChangeModel,
    ExtractionRunModel,
    ExtractionStepModel,
    ForeshadowModel,
    KnowledgeStateModel,
    StoryEventModel,
    SummaryModel,
    TimelineEventModel,
)


class MemoryRepository(Protocol):
    async def create_run(
        self, work_id: UUID, chapter_id: UUID, version_id: UUID, trigger: str
    ) -> ExtractionRun: ...

    async def get_run(self, run_id: UUID) -> ExtractionRun | None: ...

    async def set_run_status(
        self, run_id: UUID, status: ExtractionStatus, error: str | None = None
    ) -> None: ...

    async def create_step(self, run_id: UUID, kind: str) -> UUID: ...

    async def finish_step(
        self,
        step_id: UUID,
        status: str,
        *,
        model: str | None = None,
        prompt_version: int | None = None,
        tokens: dict[str, object] | None = None,
        error: str | None = None,
    ) -> None: ...

    async def save_summary(
        self,
        *,
        work_id: UUID,
        chapter_id: UUID,
        version_id: UUID,
        content: str,
        content_hash: str,
        model: str | None,
        prompt_version: int | None,
    ) -> Summary: ...

    async def add_proposal(
        self,
        *,
        work_id: UUID,
        run_id: UUID,
        step_id: UUID,
        kind: str,
        after: dict[str, Any],
        confidence: float | None,
        source_span: dict[str, Any] | None,
        target_entity_id: UUID | None = None,
        base_entity_version: int | None = None,
        before: dict[str, Any] | None = None,
    ) -> ChangeProposal: ...

    async def find_entity(
        self, work_id: UUID, entity_type: str, name: str, aliases: list[str]
    ) -> Entity | None: ...

    async def list_proposals(
        self, work_id: UUID, status: ProposalStatus | None = None
    ) -> list[ChangeProposal]: ...

    async def get_proposal(self, proposal_id: UUID) -> ChangeProposal | None: ...

    async def resolve_proposal(
        self,
        proposal_id: UUID,
        action: str,
        *,
        base_entity_version: int,
        modified_payload: dict[str, Any] | None = None,
    ) -> ResolvedProposal | None: ...

    async def list_entities(
        self, work_id: UUID, limit: int = 500, offset: int = 0
    ) -> list[Entity]: ...

    async def list_relations_for_entities(
        self, work_id: UUID, entity_ids: list[UUID], limit: int = 500
    ) -> list[EntityRelation]: ...

    async def get_summary(self, chapter_id: UUID) -> Summary | None: ...

    async def list_foreshadows(self, work_id: UUID) -> list[Foreshadow]: ...

    async def list_timeline(self, work_id: UUID) -> list[TimelineEvent]: ...

    async def add_timeline_event(
        self, work_id: UUID, description: str, event_time: str | None, chapter_id: UUID | None
    ) -> TimelineEvent: ...

    async def replace_story_events(
        self,
        work_id: UUID,
        chapter_id: UUID,
        version_id: UUID,
        chapter_number: int,
        events: list[dict[str, Any]],
        run_id: UUID | None = None,
    ) -> list[StoryEvent]: ...

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

    async def list_relations(
        self, work_id: UUID, entity_id: UUID | None = None, limit: int = 100, offset: int = 0
    ) -> list[EntityRelation]: ...

    async def list_entity_changes(
        self,
        work_id: UUID,
        entity_id: UUID | None = None,
        *,
        at_chapter: int | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[EntityStateChange]: ...

    async def update_entity_change_status(
        self, work_id: UUID, change_id: UUID, status: str
    ) -> EntityStateChange | None: ...

    async def update_knowledge_status(
        self, work_id: UUID, knowledge_id: UUID, status: str
    ) -> KnowledgeState | None: ...

    async def add_foreshadow(
        self,
        work_id: UUID,
        description: str,
        planted_chapter_id: UUID | None,
        expected_recover_chapter_id: UUID | None,
    ) -> Foreshadow: ...

    async def get_entity(self, entity_id: UUID) -> Entity | None: ...

    async def add_entity(
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
    ) -> Entity | None: ...


def _run_to_domain(model: ExtractionRunModel) -> ExtractionRun:
    return ExtractionRun(
        id=model.id,
        work_id=model.work_id,
        chapter_id=model.chapter_id,
        version_id=model.version_id,
        status=ExtractionStatus(model.status),
        created_at=model.created_at,
    )


def _proposal_to_domain(model: ChangeProposalModel) -> ChangeProposal:
    return ChangeProposal(
        id=model.id,
        work_id=model.work_id,
        run_id=model.run_id,
        kind=model.kind,
        target_entity_id=model.target_entity_id,
        after=cast(dict[str, Any], model.after),
        confidence=model.confidence,
        source_span=cast(dict[str, Any] | None, model.source_span),
        base_entity_version=model.base_entity_version,
        status=ProposalStatus(model.status),
        created_at=model.created_at,
    )


def _timeline_to_domain(model: TimelineEventModel) -> TimelineEvent:
    return TimelineEvent(
        id=model.id,
        work_id=model.work_id,
        chapter_id=model.chapter_id,
        event_time=model.event_time,
        description=model.description,
        entity_ids=list(model.entity_ids),
    )


def _foreshadow_to_domain(model: ForeshadowModel) -> Foreshadow:
    return Foreshadow(
        id=model.id,
        work_id=model.work_id,
        description=model.description,
        planted_chapter_id=model.planted_chapter_id,
        expected_recover_chapter_id=model.expected_recover_chapter_id,
        status=model.status,
    )


def _summary_to_domain(model: SummaryModel) -> Summary:
    return Summary(
        id=model.id,
        work_id=model.work_id,
        chapter_id=model.scope_id,
        content=model.content,
        based_on_version_id=model.based_on_version_id,
        status=model.status,
    )


def _entity_to_domain(model: EntityModel) -> Entity:
    return Entity(
        id=model.id,
        work_id=model.work_id,
        type=model.type,
        name=model.name,
        aliases=list(model.aliases),
        attributes=cast(dict[str, Any], model.attributes),
        version=model.version,
        first_chapter_id=model.first_chapter_id,
    )


class SqlAlchemyMemoryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_run(
        self, work_id: UUID, chapter_id: UUID, version_id: UUID, trigger: str
    ) -> ExtractionRun:
        model = ExtractionRunModel(
            work_id=work_id,
            chapter_id=chapter_id,
            version_id=version_id,
            status=ExtractionStatus.PENDING.value,
            trigger=trigger,
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return _run_to_domain(model)

    async def get_run(self, run_id: UUID) -> ExtractionRun | None:
        model = await self._session.get(ExtractionRunModel, run_id)
        return _run_to_domain(model) if model is not None else None

    async def set_run_status(
        self, run_id: UUID, status: ExtractionStatus, error: str | None = None
    ) -> None:
        model = await self._session.get(ExtractionRunModel, run_id)
        if model is None:
            return
        model.status = status.value
        if error is not None:
            model.error = error
        if status is ExtractionStatus.RUNNING:
            model.started_at = datetime.now(UTC)
        if status in {
            ExtractionStatus.SUCCEEDED,
            ExtractionStatus.PARTIAL,
            ExtractionStatus.FAILED,
        }:
            model.finished_at = datetime.now(UTC)
        await self._session.flush()

    async def create_step(self, run_id: UUID, kind: str) -> UUID:
        model = ExtractionStepModel(run_id=run_id, kind=kind, status="running")
        self._session.add(model)
        await self._session.flush()
        return model.id

    async def finish_step(
        self,
        step_id: UUID,
        status: str,
        *,
        model: str | None = None,
        prompt_version: int | None = None,
        tokens: dict[str, object] | None = None,
        error: str | None = None,
    ) -> None:
        step = await self._session.get(ExtractionStepModel, step_id)
        if step is None:
            return
        step.status = status
        step.model = model
        step.prompt_version = prompt_version
        step.tokens = tokens
        step.error = error
        step.finished_at = datetime.now(UTC)
        await self._session.flush()

    async def save_summary(
        self,
        *,
        work_id: UUID,
        chapter_id: UUID,
        version_id: UUID,
        content: str,
        content_hash: str,
        model: str | None,
        prompt_version: int | None,
    ) -> Summary:
        stmt = select(SummaryModel).where(
            SummaryModel.level == "chapter",
            SummaryModel.scope_id == chapter_id,
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        if row is None:
            row = SummaryModel(
                work_id=work_id,
                level="chapter",
                scope_id=chapter_id,
                content=content,
                based_on_version_id=version_id,
                status="fresh",
                content_hash=content_hash,
                model=model,
                prompt_version=prompt_version,
            )
            self._session.add(row)
        else:
            row.content = content
            row.based_on_version_id = version_id
            row.status = "fresh"
            row.content_hash = content_hash
            row.model = model
            row.prompt_version = prompt_version
        await self._session.flush()
        await self._session.refresh(row)
        return _summary_to_domain(row)

    async def add_proposal(
        self,
        *,
        work_id: UUID,
        run_id: UUID,
        step_id: UUID,
        kind: str,
        after: dict[str, Any],
        confidence: float | None,
        source_span: dict[str, Any] | None,
        target_entity_id: UUID | None = None,
        base_entity_version: int | None = None,
        before: dict[str, Any] | None = None,
    ) -> ChangeProposal:
        model = ChangeProposalModel(
            work_id=work_id,
            run_id=run_id,
            step_id=step_id,
            kind=kind,
            target_entity_id=target_entity_id,
            before=before,
            after=after,
            confidence=confidence,
            source_span=source_span,
            base_entity_version=base_entity_version,
            status=ProposalStatus.PENDING.value,
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return _proposal_to_domain(model)

    async def find_entity(
        self, work_id: UUID, entity_type: str, name: str, aliases: list[str]
    ) -> Entity | None:
        stmt = select(EntityModel).where(
            EntityModel.work_id == work_id,
            EntityModel.type == entity_type,
        )
        candidates = (await self._session.execute(stmt)).scalars().all()
        wanted = {name.casefold(), *(alias.casefold() for alias in aliases)}
        for candidate in candidates:
            names = {
                candidate.name.casefold(),
                *(str(alias).casefold() for alias in candidate.aliases),
            }
            if wanted & names:
                return _entity_to_domain(candidate)
        return None

    async def list_proposals(
        self, work_id: UUID, status: ProposalStatus | None = None
    ) -> list[ChangeProposal]:
        stmt = select(ChangeProposalModel).where(ChangeProposalModel.work_id == work_id)
        if status is not None:
            stmt = stmt.where(ChangeProposalModel.status == status.value)
        stmt = stmt.order_by(ChangeProposalModel.created_at.desc())
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_proposal_to_domain(row) for row in rows]

    async def get_proposal(self, proposal_id: UUID) -> ChangeProposal | None:
        model = await self._session.get(ChangeProposalModel, proposal_id)
        return _proposal_to_domain(model) if model is not None else None

    async def resolve_proposal(
        self,
        proposal_id: UUID,
        action: str,
        *,
        base_entity_version: int,
        modified_payload: dict[str, Any] | None = None,
    ) -> ResolvedProposal | None:
        stmt = (
            select(ChangeProposalModel)
            .where(ChangeProposalModel.id == proposal_id)
            .with_for_update()
        )
        proposal = (await self._session.execute(stmt)).scalar_one_or_none()
        if proposal is None:
            return None
        if proposal.status != ProposalStatus.PENDING.value:
            raise ConflictError("proposal already resolved", code="proposal.already_resolved")

        if action == "reject":
            proposal.status = ProposalStatus.REJECTED.value
            proposal.resolved_at = datetime.now(UTC)
            await self._session.flush()
            return ResolvedProposal(proposal=_proposal_to_domain(proposal), entity=None)

        payload = dict(cast(dict[str, Any], proposal.after))
        if modified_payload is not None:
            payload.update(modified_payload)
        entity_type = str(payload.get("type", "")).strip()
        name = str(payload.get("name", "")).strip()
        if not entity_type or not name:
            raise ConflictError(
                "proposal payload requires type and name", code="proposal.invalid_payload"
            )
        aliases = [str(alias) for alias in cast(list[Any], payload.get("aliases", []))]
        attributes = cast(dict[str, Any], payload.get("attributes", {}))

        entity: EntityModel
        if proposal.kind == "entity_create":
            run = await self._session.get(ExtractionRunModel, proposal.run_id)
            entity = EntityModel(
                work_id=proposal.work_id,
                type=entity_type,
                name=name,
                aliases=aliases,
                attributes=attributes,
                version=1,
                first_chapter_id=run.chapter_id if run is not None else None,
            )
            self._session.add(entity)
            await self._session.flush()
            proposal.target_entity_id = entity.id
            revision = 1
            before: dict[str, Any] | None = None
        elif proposal.kind == "entity_update":
            if proposal.target_entity_id is None:
                raise ConflictError("entity_update requires target", code="proposal.missing_target")
            entity_result = await self._session.execute(
                select(EntityModel)
                .where(EntityModel.id == proposal.target_entity_id)
                .with_for_update()
            )
            entity = entity_result.scalar_one()
            if entity.version != base_entity_version:
                raise ConflictError("entity version conflict", code="entity.version_conflict")
            before = {
                "type": entity.type,
                "name": entity.name,
                "aliases": list(entity.aliases),
                "attributes": cast(dict[str, Any], entity.attributes),
            }
            entity.type = entity_type
            entity.name = name
            entity.aliases = aliases
            entity.attributes = attributes
            entity.version += 1
            revision = entity.version
        else:
            raise ConflictError("unsupported proposal kind", code="proposal.unsupported_kind")

        self._session.add(
            EntityRevisionModel(
                entity_id=entity.id,
                revision=revision,
                before=before,
                after=payload,
                source_proposal_id=proposal.id,
                action=action,
            )
        )
        proposal.status = (
            ProposalStatus.MODIFIED.value
            if modified_payload is not None
            else ProposalStatus.ACCEPTED.value
        )
        proposal.resolved_at = datetime.now(UTC)
        await self._session.flush()
        await self._session.refresh(proposal)
        await self._session.refresh(entity)
        return ResolvedProposal(
            proposal=_proposal_to_domain(proposal), entity=_entity_to_domain(entity)
        )

    async def list_entities(self, work_id: UUID, limit: int = 500, offset: int = 0) -> list[Entity]:
        stmt = (
            select(EntityModel)
            .where(EntityModel.work_id == work_id)
            .order_by(EntityModel.type.asc(), EntityModel.name.asc())
            .limit(limit)
            .offset(offset)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_entity_to_domain(row) for row in rows]

    async def list_relations_for_entities(
        self, work_id: UUID, entity_ids: list[UUID], limit: int = 500
    ) -> list[EntityRelation]:
        if not entity_ids:
            return []
        stmt = (
            select(EntityRelationModel)
            .where(
                EntityRelationModel.work_id == work_id,
                or_(
                    EntityRelationModel.from_entity_id.in_(entity_ids),
                    EntityRelationModel.to_entity_id.in_(entity_ids),
                ),
            )
            .order_by(EntityRelationModel.created_at, EntityRelationModel.id)
            .limit(limit)
        )
        models = (await self._session.scalars(stmt)).all()
        return [_relation_to_domain(model) for model in models]

    async def get_summary(self, chapter_id: UUID) -> Summary | None:
        stmt = select(SummaryModel).where(
            SummaryModel.level == "chapter",
            SummaryModel.scope_id == chapter_id,
        )
        model = (await self._session.execute(stmt)).scalar_one_or_none()
        return _summary_to_domain(model) if model is not None else None

    async def list_timeline(self, work_id: UUID) -> list[TimelineEvent]:
        rows = (
            (
                await self._session.execute(
                    select(TimelineEventModel)
                    .where(TimelineEventModel.work_id == work_id)
                    .order_by(TimelineEventModel.created_at.asc())
                )
            )
            .scalars()
            .all()
        )
        return [_timeline_to_domain(row) for row in rows]

    async def add_timeline_event(
        self, work_id: UUID, description: str, event_time: str | None, chapter_id: UUID | None
    ) -> TimelineEvent:
        model = TimelineEventModel(
            work_id=work_id,
            description=description,
            event_time=event_time,
            chapter_id=chapter_id,
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return _timeline_to_domain(model)

    async def list_foreshadows(self, work_id: UUID) -> list[Foreshadow]:
        stmt = (
            select(ForeshadowModel)
            .where(ForeshadowModel.work_id == work_id)
            .order_by(ForeshadowModel.created_at.desc())
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_foreshadow_to_domain(row) for row in rows]

    async def add_foreshadow(
        self,
        work_id: UUID,
        description: str,
        planted_chapter_id: UUID | None,
        expected_recover_chapter_id: UUID | None,
    ) -> Foreshadow:
        model = ForeshadowModel(
            work_id=work_id,
            description=description,
            planted_chapter_id=planted_chapter_id,
            expected_recover_chapter_id=expected_recover_chapter_id,
            status="planted",
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return _foreshadow_to_domain(model)

    async def replace_story_events(
        self,
        work_id: UUID,
        chapter_id: UUID,
        version_id: UUID,
        chapter_number: int,
        events: list[dict[str, Any]],
        run_id: UUID | None = None,
    ) -> list[StoryEvent]:
        old_run_ids = select(ExtractionRunModel.id).where(
            ExtractionRunModel.chapter_id == chapter_id
        )
        if run_id is not None:
            old_run_ids = old_run_ids.where(ExtractionRunModel.id != run_id)
        await self._session.execute(
            delete(ChangeProposalModel).where(
                ChangeProposalModel.work_id == work_id,
                ChangeProposalModel.status == "pending",
                ChangeProposalModel.run_id.in_(old_run_ids),
            )
        )
        await self._session.execute(
            delete(EntityStateChangeModel).where(EntityStateChangeModel.chapter_id == chapter_id)
        )
        await self._session.execute(
            delete(KnowledgeStateModel).where(KnowledgeStateModel.chapter_id == chapter_id)
        )
        await self._session.execute(
            delete(StoryEventModel).where(StoryEventModel.chapter_id == chapter_id)
        )
        saved: list[StoryEvent] = []
        for index, item in enumerate(events, 1):
            event = StoryEventModel(
                work_id=work_id,
                chapter_id=chapter_id,
                version_id=version_id,
                chapter_number=chapter_number,
                event_index=int(item.get("index", index)),
                summary=str(item["summary"]),
                time_text=cast(str | None, item.get("time_text")),
                location=cast(str | None, item.get("location")),
                participants=cast(list[dict[str, object]], item.get("participants", [])),
                changes={
                    "knowledge_changes": item.get("knowledge_changes", []),
                    "entity_changes": item.get("entity_changes", []),
                },
                source_span=cast(dict[str, object], item.get("source_span", {})),
                confidence=cast(float | None, item.get("confidence")),
                status="inferred",
            )
            self._session.add(event)
            await self._session.flush()
            for change in cast(list[dict[str, Any]], item.get("knowledge_changes", [])):
                raw_character_id = change.get("character_id")
                character_id = UUID(str(raw_character_id)) if raw_character_id else None
                self._session.add(
                    KnowledgeStateModel(
                        work_id=work_id,
                        character_id=character_id,
                        character_name=str(change["character_name"]),
                        fact_key=str(change["fact_key"]),
                        fact_value=cast(dict[str, object], change.get("fact_value", {})),
                        state=str(change.get("state", "knows")),
                        learned_event_id=event.id,
                        chapter_id=chapter_id,
                        chapter_number=chapter_number,
                        source_span=cast(dict[str, object], item.get("source_span", {})),
                        confidence=cast(float | None, item.get("confidence")),
                        status="inferred",
                    )
                )
            for change in cast(list[dict[str, Any]], item.get("entity_changes", [])):
                raw_entity_id = change.get("entity_id")
                self._session.add(
                    EntityStateChangeModel(
                        work_id=work_id,
                        entity_id=UUID(str(raw_entity_id)) if raw_entity_id else None,
                        entity_name=str(change["entity_name"]),
                        field=str(change["field"]),
                        before=cast(dict[str, object], change.get("before", {})),
                        after=cast(dict[str, object], change.get("after", {})),
                        event_id=event.id,
                        chapter_id=chapter_id,
                        chapter_number=chapter_number,
                        source_span=cast(dict[str, object], item.get("source_span", {})),
                        confidence=cast(float | None, item.get("confidence")),
                        status="inferred",
                    )
                )
            saved.append(_story_event_to_domain(event))
        await self._session.flush()
        return saved

    async def list_story_events(
        self,
        work_id: UUID,
        *,
        from_chapter: int | None = None,
        to_chapter: int | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[StoryEvent]:
        stmt = select(StoryEventModel).where(StoryEventModel.work_id == work_id)
        if from_chapter is not None:
            stmt = stmt.where(StoryEventModel.chapter_number >= from_chapter)
        if to_chapter is not None:
            stmt = stmt.where(StoryEventModel.chapter_number <= to_chapter)
        stmt = (
            stmt.order_by(StoryEventModel.chapter_number, StoryEventModel.event_index)
            .limit(limit)
            .offset(offset)
        )
        models = (await self._session.scalars(stmt)).all()
        return [_story_event_to_domain(model) for model in models]

    async def list_knowledge(
        self,
        work_id: UUID,
        *,
        character_id: UUID | None = None,
        at_chapter: int | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[KnowledgeState]:
        stmt = select(KnowledgeStateModel).where(KnowledgeStateModel.work_id == work_id)
        if character_id is not None:
            stmt = stmt.where(KnowledgeStateModel.character_id == character_id)
        if at_chapter is not None:
            stmt = stmt.where(KnowledgeStateModel.chapter_number <= at_chapter)
        stmt = stmt.order_by(
            KnowledgeStateModel.chapter_number.desc(),
            KnowledgeStateModel.created_at.desc(),
        ).limit(limit + offset)
        models = (await self._session.scalars(stmt)).all()
        latest = _latest_knowledge(models)
        return latest[offset : offset + limit]

    async def who_knows(
        self,
        work_id: UUID,
        fact_key: str,
        at_chapter: int | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[KnowledgeState]:
        stmt = select(KnowledgeStateModel).where(
            KnowledgeStateModel.work_id == work_id,
            KnowledgeStateModel.fact_key == fact_key.strip().casefold(),
        )
        if at_chapter is not None:
            stmt = stmt.where(KnowledgeStateModel.chapter_number <= at_chapter)
        stmt = stmt.order_by(
            KnowledgeStateModel.chapter_number.desc(),
            KnowledgeStateModel.created_at.desc(),
        ).limit(limit + offset)
        models = (await self._session.scalars(stmt)).all()
        states = [
            state for state in _latest_knowledge(models) if state.state in {"knows", "suspects"}
        ]
        return states[offset : offset + limit]

    async def list_relations(
        self, work_id: UUID, entity_id: UUID | None = None, limit: int = 100, offset: int = 0
    ) -> list[EntityRelation]:
        stmt = select(EntityRelationModel).where(EntityRelationModel.work_id == work_id)
        if entity_id is not None:
            stmt = stmt.where(
                or_(
                    EntityRelationModel.from_entity_id == entity_id,
                    EntityRelationModel.to_entity_id == entity_id,
                )
            )
        stmt = (
            stmt.order_by(EntityRelationModel.created_at, EntityRelationModel.id)
            .limit(limit)
            .offset(offset)
        )
        models = (await self._session.scalars(stmt)).all()
        return [_relation_to_domain(model) for model in models]

    async def list_entity_changes(
        self,
        work_id: UUID,
        entity_id: UUID | None = None,
        *,
        at_chapter: int | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[EntityStateChange]:
        stmt = select(EntityStateChangeModel).where(EntityStateChangeModel.work_id == work_id)
        if entity_id is not None:
            stmt = stmt.where(EntityStateChangeModel.entity_id == entity_id)
        if at_chapter is not None:
            stmt = stmt.where(EntityStateChangeModel.chapter_number <= at_chapter)
        stmt = (
            stmt.order_by(EntityStateChangeModel.chapter_number, EntityStateChangeModel.created_at)
            .limit(limit)
            .offset(offset)
        )
        models = (await self._session.scalars(stmt)).all()
        return [_entity_change_to_domain(model) for model in models]

    async def update_knowledge_status(
        self, work_id: UUID, knowledge_id: UUID, status: str
    ) -> KnowledgeState | None:
        model = await self._session.get(KnowledgeStateModel, knowledge_id)
        if model is None or model.work_id != work_id:
            return None
        model.status = status
        await self._session.flush()
        return _knowledge_to_domain(model)

    async def update_entity_change_status(
        self, work_id: UUID, change_id: UUID, status: str
    ) -> EntityStateChange | None:
        model = await self._session.get(EntityStateChangeModel, change_id)
        if model is None or model.work_id != work_id:
            return None
        model.status = status
        await self._session.flush()
        return _entity_change_to_domain(model)

    async def get_entity(self, entity_id: UUID) -> Entity | None:
        model = await self._session.get(EntityModel, entity_id)
        return _entity_to_domain(model) if model is not None else None

    async def add_entity(
        self,
        work_id: UUID,
        type: str,
        name: str,
        aliases: list[str],
        attributes: dict[str, Any],
    ) -> Entity:
        model = EntityModel(
            work_id=work_id,
            type=type,
            name=name,
            aliases=aliases,
            attributes=attributes,
            version=1,
        )
        self._session.add(model)
        await self._session.flush()
        self._session.add(
            EntityRevisionModel(
                entity_id=model.id,
                revision=1,
                before=None,
                after={
                    "type": type,
                    "name": name,
                    "aliases": aliases,
                    "attributes": attributes,
                },
                action="manual",
            )
        )
        await self._session.flush()
        await self._session.refresh(model)
        return _entity_to_domain(model)

    async def patch_entity(
        self,
        entity_id: UUID,
        base_version: int,
        *,
        type: str | None = None,
        name: str | None = None,
        aliases: list[str] | None = None,
        attributes: dict[str, Any] | None = None,
    ) -> Entity | None:
        stmt = select(EntityModel).where(EntityModel.id == entity_id).with_for_update()
        model = (await self._session.execute(stmt)).scalar_one_or_none()
        if model is None:
            return None
        if model.version != base_version:
            raise ConflictError("entity version conflict", code="entity.version_conflict")
        before = {
            "type": model.type,
            "name": model.name,
            "aliases": list(model.aliases),
            "attributes": dict(model.attributes),
        }
        if type is not None:
            model.type = type
        if name is not None:
            model.name = name
        if aliases is not None:
            model.aliases = aliases
        if attributes is not None:
            model.attributes = attributes
        model.version += 1
        await self._session.flush()
        self._session.add(
            EntityRevisionModel(
                entity_id=model.id,
                revision=model.version,
                before=before,
                after={
                    "type": model.type,
                    "name": model.name,
                    "aliases": list(model.aliases),
                    "attributes": dict(model.attributes),
                },
                action="manual",
            )
        )
        await self._session.flush()
        await self._session.refresh(model)
        return _entity_to_domain(model)


def _story_event_to_domain(model: StoryEventModel) -> StoryEvent:
    return StoryEvent(
        id=model.id,
        work_id=model.work_id,
        chapter_id=model.chapter_id,
        chapter_number=model.chapter_number,
        event_index=model.event_index,
        summary=model.summary,
        time_text=model.time_text,
        location=model.location,
        participants=list(model.participants),
        changes=dict(model.changes),
        confidence=model.confidence,
        status=model.status,
    )


def _knowledge_to_domain(model: KnowledgeStateModel) -> KnowledgeState:
    return KnowledgeState(
        id=model.id,
        work_id=model.work_id,
        character_id=model.character_id,
        character_name=model.character_name,
        fact_key=model.fact_key,
        fact_value=dict(model.fact_value),
        state=model.state,
        chapter_number=model.chapter_number,
        confidence=model.confidence,
        status=model.status,
    )


def _latest_knowledge(models: Sequence[KnowledgeStateModel]) -> list[KnowledgeState]:
    seen: set[tuple[str, str]] = set()
    result: list[KnowledgeState] = []
    for model in models:
        key = (str(model.character_id or model.character_name), model.fact_key)
        if key in seen:
            continue
        seen.add(key)
        result.append(_knowledge_to_domain(model))
    return result


def _relation_to_domain(model: EntityRelationModel) -> EntityRelation:
    return EntityRelation(
        id=model.id,
        work_id=model.work_id,
        from_entity_id=model.from_entity_id,
        to_entity_id=model.to_entity_id,
        relation_type=model.relation_type,
        since_chapter_id=model.since_chapter_id,
    )


def _entity_change_to_domain(model: EntityStateChangeModel) -> EntityStateChange:
    return EntityStateChange(
        id=model.id,
        work_id=model.work_id,
        entity_id=model.entity_id,
        entity_name=model.entity_name,
        field=model.field,
        before=dict(model.before),
        after=dict(model.after),
        chapter_number=model.chapter_number,
        status=model.status,
    )
