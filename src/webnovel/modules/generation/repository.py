from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any, Protocol
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from webnovel.kernel.errors import ConflictError
from webnovel.modules.generation.contract import (
    ACTIVE_STATUSES,
    TERMINAL,
    Draft,
    DraftStatus,
    Generation,
    GenerationCreate,
    GenerationStatus,
    TaskType,
)
from webnovel.modules.generation.models import (
    CandidateSetModel,
    DraftModel,
    GenerationModel,
    IdempotencyKeyModel,
    PreferenceEventModel,
)
from webnovel.modules.generation.state_machine import transition


class GenerationRepository(Protocol):
    async def add(
        self, command: GenerationCreate, idempotency_key: str, payload_hash: str
    ) -> tuple[Generation, bool]: ...

    async def get(self, generation_id: UUID) -> Generation | None: ...

    async def cancel(self, generation_id: UUID) -> Generation | None: ...

    async def get_draft(self, draft_id: UUID) -> Draft | None: ...

    async def accept_draft(
        self, draft_id: UUID, chapter_version_id: UUID, edit_distance: float
    ) -> Draft | None: ...

    async def claim(self, generation_id: UUID) -> Generation | None: ...

    async def mark_streaming(self, generation_id: UUID) -> None: ...

    async def append_draft(self, draft_id: UUID, text: str) -> None: ...

    async def finish(
        self, generation_id: UUID, status: GenerationStatus, draft_status: DraftStatus
    ) -> None: ...

    async def record_context(self, generation_id: UUID, snapshot: dict[str, Any]) -> None: ...

    async def record_prompt(
        self,
        generation_id: UUID,
        prompt_name: str,
        prompt_version: int,
        snapshot: dict[str, Any] | None = None,
    ) -> None: ...

    async def discard_draft(self, draft_id: UUID) -> Draft | None: ...


def _to_domain(model: GenerationModel) -> Generation:
    return Generation(
        id=model.id,
        work_id=model.work_id,
        chapter_id=model.chapter_id,
        task_type=TaskType(model.task_type),
        status=GenerationStatus(model.status),
        draft_id=model.draft_id,
        prompt_name=model.prompt_name,
        prompt_version=model.prompt_version,
        prompt_snapshot=model.prompt_snapshot,
        context_snapshot=model.context_snapshot,
        instruction=model.instruction,
        target_words=model.target_words,
        created_at=model.created_at,
    )


def _draft_to_domain(model: DraftModel) -> Draft:
    return Draft(
        id=model.id,
        generation_id=model.generation_id,
        chapter_id=model.chapter_id,
        content=model.content,
        status=DraftStatus(model.status),
    )


class SqlAlchemyGenerationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(
        self, command: GenerationCreate, idempotency_key: str, payload_hash: str
    ) -> tuple[Generation, bool]:
        existing_key = await self._session.get(IdempotencyKeyModel, idempotency_key)
        if existing_key is not None:
            if existing_key.payload_hash != payload_hash:
                raise ConflictError(
                    "idempotency key reused with different payload",
                    code="idempotency.payload_mismatch",
                )
            if existing_key.generation_id is None:
                raise ConflictError("idempotency key has no generation", code="idempotency.invalid")
            generation = await self.get(existing_key.generation_id)
            if generation is None:
                raise ConflictError("idempotent generation not found", code="idempotency.invalid")
            return generation, False

        last_stmt = (
            select(GenerationModel)
            .where(GenerationModel.chapter_id == command.chapter_id)
            .order_by(GenerationModel.created_at.desc())
            .limit(1)
        )
        last_generation = (await self._session.execute(last_stmt)).scalar_one_or_none()
        if last_generation is not None and GenerationStatus(last_generation.status) in TERMINAL:
            last_set_stmt = select(CandidateSetModel).where(
                CandidateSetModel.generation_id == last_generation.id
            )
            last_set = (await self._session.execute(last_set_stmt)).scalar_one_or_none()
            if last_set is not None:
                self._session.add(
                    PreferenceEventModel(
                        candidate_set_id=last_set.id,
                        candidate_id=str(last_generation.draft_id or last_generation.id),
                        event_type="regenerated",
                    )
                )

        active_stmt = (
            select(GenerationModel)
            .where(
                GenerationModel.chapter_id == command.chapter_id,
                GenerationModel.status.in_([status.value for status in ACTIVE_STATUSES]),
            )
            .with_for_update()
        )
        active = (await self._session.execute(active_stmt)).scalar_one_or_none()
        if active is not None:
            raise ConflictError(
                f"chapter already has active generation: {active.id}",
                code="generation.active_exists",
            )

        generation_model = GenerationModel(
            work_id=command.work_id,
            chapter_id=command.chapter_id,
            task_type=command.task_type.value,
            status=GenerationStatus.QUEUED.value,
            instruction=command.instruction,
            target_words=command.target_words,
        )
        self._session.add(generation_model)
        await self._session.flush()

        draft = DraftModel(
            work_id=command.work_id,
            chapter_id=command.chapter_id,
            generation_id=generation_model.id,
            content="",
            status=DraftStatus.GENERATING.value,
        )
        self._session.add(draft)
        await self._session.flush()

        generation_model.draft_id = draft.id
        candidate_set = CandidateSetModel(
            generation_id=generation_model.id,
            task_type=command.task_type.value,
            candidates=[
                {
                    "candidate_id": str(draft.id),
                    "text_ref": f"draft:{draft.id}",
                    "model": None,
                    "prompt_version": None,
                    "features": {},
                }
            ],
            shown_order=[0],
        )
        self._session.add(candidate_set)
        await self._session.flush()

        self._session.add(
            PreferenceEventModel(
                candidate_set_id=candidate_set.id,
                candidate_id=str(draft.id),
                event_type="shown",
            )
        )
        self._session.add(
            IdempotencyKeyModel(
                key=idempotency_key,
                scope="generation.create",
                payload_hash=payload_hash,
                generation_id=generation_model.id,
                expires_at=datetime.now(UTC) + timedelta(hours=24),
            )
        )
        await self._session.flush()
        await self._session.refresh(generation_model)
        return _to_domain(generation_model), True

    async def get(self, generation_id: UUID) -> Generation | None:
        model = await self._session.get(GenerationModel, generation_id)
        return _to_domain(model) if model is not None else None

    async def cancel(self, generation_id: UUID) -> Generation | None:
        stmt = select(GenerationModel).where(GenerationModel.id == generation_id).with_for_update()
        model = (await self._session.execute(stmt)).scalar_one_or_none()
        if model is None:
            return None
        current = GenerationStatus(model.status)
        if current in TERMINAL:
            return _to_domain(model)

        if current is GenerationStatus.QUEUED or current is GenerationStatus.CANCELLING:
            model.status = transition(current, GenerationStatus.CANCELLED).value
        else:
            model.status = transition(current, GenerationStatus.CANCELLING).value
            model.status = transition(GenerationStatus.CANCELLING, GenerationStatus.CANCELLED).value
        await self._session.flush()
        await self._session.refresh(model)
        return _to_domain(model)

    async def get_draft(self, draft_id: UUID) -> Draft | None:
        model = await self._session.get(DraftModel, draft_id)
        return _draft_to_domain(model) if model is not None else None

    async def accept_draft(
        self, draft_id: UUID, chapter_version_id: UUID, edit_distance: float
    ) -> Draft | None:
        stmt = select(DraftModel).where(DraftModel.id == draft_id).with_for_update()
        model = (await self._session.execute(stmt)).scalar_one_or_none()
        if model is None:
            return None
        if model.status == DraftStatus.ACCEPTED.value:
            raise ConflictError("draft already accepted", code="draft.already_accepted")
        if model.status == DraftStatus.DISCARDED.value:
            raise ConflictError("draft is discarded", code="draft.discarded")

        model.status = DraftStatus.ACCEPTED.value
        generation = await self._session.get(GenerationModel, model.generation_id)
        if generation is not None:
            generation.accepted_at = datetime.now(UTC)

        candidate_set_stmt = select(CandidateSetModel).where(
            CandidateSetModel.generation_id == model.generation_id
        )
        candidate_set = (await self._session.execute(candidate_set_stmt)).scalar_one_or_none()
        if candidate_set is not None:
            self._session.add(
                PreferenceEventModel(
                    candidate_set_id=candidate_set.id,
                    candidate_id=str(model.id),
                    event_type="accepted",
                    edit_distance=edit_distance,
                    event_metadata={"chapter_version_id": str(chapter_version_id)},
                )
            )
        await self._session.flush()
        await self._session.refresh(model)
        return _draft_to_domain(model)

    async def claim(self, generation_id: UUID) -> Generation | None:
        stmt = select(GenerationModel).where(GenerationModel.id == generation_id).with_for_update()
        model = (await self._session.execute(stmt)).scalar_one_or_none()
        if model is None or model.status != GenerationStatus.QUEUED.value:
            return None
        model.status = GenerationStatus.RUNNING.value
        await self._session.flush()
        await self._session.refresh(model)
        return _to_domain(model)

    async def mark_streaming(self, generation_id: UUID) -> None:
        model = await self._session.get(GenerationModel, generation_id)
        if model is None or model.status != GenerationStatus.RUNNING.value:
            return
        model.status = GenerationStatus.STREAMING.value
        await self._session.flush()

    async def append_draft(self, draft_id: UUID, text: str) -> None:
        model = await self._session.get(DraftModel, draft_id)
        if model is None:
            return
        model.content = f"{model.content}{text}"
        await self._session.flush()

    async def record_context(self, generation_id: UUID, snapshot: dict[str, Any]) -> None:
        model = await self._session.get(GenerationModel, generation_id)
        if model is None:
            return
        model.context_snapshot = snapshot
        await self._session.flush()

    async def record_prompt(
        self,
        generation_id: UUID,
        prompt_name: str,
        prompt_version: int,
        snapshot: dict[str, Any] | None = None,
    ) -> None:
        model = await self._session.get(GenerationModel, generation_id)
        if model is None:
            return
        model.prompt_name = prompt_name
        model.prompt_version = prompt_version
        model.prompt_snapshot = snapshot
        await self._session.flush()

    async def discard_draft(self, draft_id: UUID) -> Draft | None:
        stmt = select(DraftModel).where(DraftModel.id == draft_id).with_for_update()
        model = (await self._session.execute(stmt)).scalar_one_or_none()
        if model is None:
            return None
        if model.status == DraftStatus.ACCEPTED.value:
            raise ConflictError("draft already accepted", code="draft.already_accepted")
        if model.status != DraftStatus.DISCARDED.value:
            model.status = DraftStatus.DISCARDED.value
            candidate_set_stmt = select(CandidateSetModel).where(
                CandidateSetModel.generation_id == model.generation_id
            )
            candidate_set = (await self._session.execute(candidate_set_stmt)).scalar_one_or_none()
            if candidate_set is not None:
                self._session.add(
                    PreferenceEventModel(
                        candidate_set_id=candidate_set.id,
                        candidate_id=str(model.id),
                        event_type="rejected",
                    )
                )
        await self._session.flush()
        await self._session.refresh(model)
        return _draft_to_domain(model)

    async def finish(
        self, generation_id: UUID, status: GenerationStatus, draft_status: DraftStatus
    ) -> None:
        generation = await self._session.get(GenerationModel, generation_id)
        if generation is None:
            return
        generation.status = status.value
        if generation.draft_id is not None:
            draft = await self._session.get(DraftModel, generation.draft_id)
            if draft is not None:
                draft.status = draft_status.value
        await self._session.flush()
