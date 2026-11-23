from __future__ import annotations

import hashlib
import json
from collections.abc import Awaitable, Callable
from uuid import UUID

import structlog

from webnovel.kernel.errors import ConflictError, NotFoundError, ValidationError
from webnovel.modules.audit.contract import AuditRecorder
from webnovel.modules.chapters_versions.contract import ChapterService
from webnovel.modules.generation.contract import (
    MAX_CANDIDATE_COUNT,
    AcceptedDraft,
    Draft,
    DraftStatus,
    Generation,
    GenerationCreate,
    GenerationStatus,
)
from webnovel.modules.generation.repository import GenerationRepository
from webnovel.modules.outbox.contract import OutboxService

logger = structlog.get_logger(__name__)


def payload_hash(command: GenerationCreate) -> str:
    payload = {
        "work_id": str(command.work_id),
        "chapter_id": str(command.chapter_id),
        "task_type": command.task_type.value,
        "instruction": command.instruction,
        "target_words": command.target_words,
        "candidate_count": command.candidate_count,
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class GenerationsService:
    def __init__(
        self,
        repository: GenerationRepository,
        chapter_service: ChapterService,
        enqueue: Callable[[UUID], Awaitable[None]] | None = None,
        on_accepted: Callable[[UUID, UUID, UUID], Awaitable[None]] | None = None,
        audit: AuditRecorder | None = None,
        outbox: OutboxService | None = None,
    ) -> None:
        self._repository = repository
        self._chapter_service = chapter_service
        self._enqueue = enqueue
        self._on_accepted = on_accepted
        self._audit = audit
        self._outbox = outbox

    async def create(self, command: GenerationCreate, idempotency_key: str) -> Generation:
        key = idempotency_key.strip()
        if not key or len(key) > 64:
            raise ValidationError(
                "Idempotency-Key must be 1..64 characters", code="idempotency.invalid_key"
            )
        if command.target_words is not None and not 100 <= command.target_words <= 20_000:
            raise ValidationError(
                "target_words must be between 100 and 20000",
                code="generation.invalid_target_words",
            )
        if not 1 <= command.candidate_count <= MAX_CANDIDATE_COUNT:
            raise ValidationError(
                "candidate_count must be between 1 and 4",
                code="generation.invalid_candidate_count",
            )

        chapter = await self._chapter_service.get(command.chapter_id)
        if chapter.work_id != command.work_id:
            raise ValidationError(
                "chapter does not belong to work", code="generation.work_mismatch"
            )
        generation, created = await self._repository.add(command, key, payload_hash(command))
        if created and self._enqueue is not None:
            await self._enqueue(generation.id)
        if created and self._audit is not None:
            await self._audit.record(
                "generation.create",
                target_type="generation",
                target_id=str(generation.id),
                metadata={"chapter_id": str(generation.chapter_id)},
            )
        if created and self._outbox is not None:
            await self._outbox.emit(
                "generation",
                generation.id,
                "generation.created",
                {"chapter_id": str(generation.chapter_id)},
            )
        return generation

    async def get(self, generation_id: UUID) -> Generation:
        generation = await self._repository.get(generation_id)
        if generation is None:
            raise NotFoundError(
                f"generation not found: {generation_id}", code="generation.not_found"
            )
        return generation

    async def cancel(self, generation_id: UUID) -> Generation:
        generation = await self._repository.cancel(generation_id)
        if generation is None:
            raise NotFoundError(
                f"generation not found: {generation_id}", code="generation.not_found"
            )
        if self._audit is not None:
            await self._audit.record(
                "generation.cancel",
                target_type="generation",
                target_id=str(generation.id),
            )
        if self._outbox is not None:
            await self._outbox.emit("generation", generation.id, "generation.cancelled", {})
        return generation

    async def get_draft(self, draft_id: UUID) -> Draft:
        draft = await self._repository.get_draft(draft_id)
        if draft is None:
            raise NotFoundError(f"draft not found: {draft_id}", code="draft.not_found")
        return draft

    async def list_drafts(self, generation_id: UUID) -> list[Draft]:
        await self.get(generation_id)
        return await self._repository.list_drafts(generation_id)

    async def clear_preferences(self, work_id: UUID) -> int:
        return int(await self._repository.delete_preferences(work_id))

    async def retry(self, generation_id: UUID) -> Generation:
        original = await self.get(generation_id)
        if original.status not in {
            GenerationStatus.FAILED,
            GenerationStatus.CANCELLED,
            GenerationStatus.EXPIRED,
        }:
            raise ConflictError(
                f"generation is not retryable: {original.status}",
                code="generation.not_retryable",
            )
        retried = await self._repository.reset_for_retry(original.id)
        if retried is None:
            raise NotFoundError(
                f"generation not found: {generation_id}", code="generation.not_found"
            )
        if self._enqueue is not None:
            await self._enqueue(retried.id)
        return retried

    async def discard_draft(self, draft_id: UUID) -> Draft:
        draft = await self._repository.discard_draft(draft_id)
        if draft is None:
            raise NotFoundError(f"draft not found: {draft_id}", code="draft.not_found")
        return draft

    async def accept_draft(self, draft_id: UUID, base_version: int) -> AcceptedDraft:
        draft = await self._repository.get_draft(draft_id)
        if draft is None:
            raise NotFoundError(f"draft not found: {draft_id}", code="draft.not_found")
        if draft.status not in {DraftStatus.READY, DraftStatus.PARTIAL}:
            raise ConflictError(
                f"draft is not acceptable: {draft.status}", code="draft.not_acceptable"
            )
        if not draft.content.strip():
            raise ValidationError("draft is empty", code="draft.empty")

        chapter = await self._chapter_service.save(
            chapter_id=draft.chapter_id,
            base_version=base_version,
            content=draft.content,
        )
        if chapter.current_version_id is None:
            raise ConflictError(
                "chapter has no current version after save", code="chapter.version_missing"
            )
        version = await self._chapter_service.get_version(chapter.id, chapter.current_version_id)
        accepted = await self._repository.accept_draft(
            draft_id=draft.id,
            chapter_version_id=version.id,
            edit_distance=_normalized_edit_distance(draft.content, version.content),
        )
        if accepted is None:
            raise NotFoundError(f"draft not found: {draft_id}", code="draft.not_found")
        if self._on_accepted is not None:
            try:
                await self._on_accepted(chapter.work_id, draft.chapter_id, version.id)
            except Exception:
                logger.exception("extraction.enqueue_failed", draft_id=str(draft.id))
        if self._audit is not None:
            await self._audit.record(
                "generation.accept",
                target_type="generation",
                target_id=str(accepted.generation_id),
                metadata={"draft_id": str(accepted.id), "chapter_id": str(chapter.id)},
            )
        if self._outbox is not None:
            await self._outbox.emit(
                "generation",
                accepted.generation_id,
                "generation.accepted",
                {"chapter_id": str(chapter.id), "version_id": str(version.id)},
            )
        return AcceptedDraft(draft=accepted, chapter_version=version)


def _normalized_edit_distance(left: str, right: str) -> float:
    if left == right:
        return 0.0
    if not left or not right:
        return 1.0
    previous = list(range(len(right) + 1))
    for i, left_char in enumerate(left, start=1):
        current = [i]
        for j, right_char in enumerate(right, start=1):
            current.append(
                min(
                    current[-1] + 1,
                    previous[j] + 1,
                    previous[j - 1] + (left_char != right_char),
                )
            )
        previous = current
    return previous[-1] / max(len(left), len(right))
