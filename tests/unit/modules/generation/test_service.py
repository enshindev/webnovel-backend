from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from webnovel.kernel.errors import ValidationError
from webnovel.modules.chapters_versions.contract import Chapter, ChapterVersion
from webnovel.modules.generation.contract import (
    AcceptedDraft,
    Draft,
    DraftStatus,
    Generation,
    GenerationCreate,
    GenerationStatus,
    TaskType,
)
from webnovel.modules.generation.service import GenerationsService, payload_hash


class FakeChapterService:
    def __init__(self, chapter: Chapter, version: ChapterVersion) -> None:
        self.chapter = chapter
        self.version = version
        self.saved: tuple[UUID, int, str] | None = None

    async def get(self, chapter_id: UUID) -> Chapter:
        return self.chapter

    async def save(
        self, chapter_id: UUID, base_version: int, content: str, title: str | None = None
    ) -> Chapter:
        self.saved = (chapter_id, base_version, content)
        return self.chapter

    async def get_version(self, chapter_id: UUID, version_id: UUID) -> ChapterVersion:
        return self.version


class FakeGenerationRepository:
    def __init__(self, chapter: Chapter, draft: Draft) -> None:
        self.chapter = chapter
        self.draft = draft
        self.created: GenerationCreate | None = None
        self.accepted: tuple[UUID, UUID, float] | None = None

    async def add(
        self, command: GenerationCreate, idempotency_key: str, payload: str
    ) -> tuple[Generation, bool]:
        self.created = command
        return (
            Generation(
                id=uuid4(),
                work_id=command.work_id,
                chapter_id=command.chapter_id,
                task_type=command.task_type,
                status=GenerationStatus.QUEUED,
                draft_id=self.draft.id,
                prompt_name=None,
                prompt_version=None,
                instruction=command.instruction,
                target_words=command.target_words,
                created_at=datetime.now(UTC),
            ),
            True,
        )

    async def get(self, generation_id: UUID) -> Generation | None:
        return None

    async def cancel(self, generation_id: UUID) -> Generation | None:
        return None

    async def get_draft(self, draft_id: UUID) -> Draft | None:
        return self.draft

    async def accept_draft(
        self, draft_id: UUID, chapter_version_id: UUID, edit_distance: float
    ) -> Draft | None:
        self.accepted = (draft_id, chapter_version_id, edit_distance)
        return Draft(
            id=self.draft.id,
            generation_id=self.draft.generation_id,
            chapter_id=self.draft.chapter_id,
            content=self.draft.content,
            status=DraftStatus.ACCEPTED,
        )

    async def claim(self, generation_id: UUID) -> Generation | None:
        return None

    async def mark_streaming(self, generation_id: UUID) -> None:
        return None

    async def append_draft(self, draft_id: UUID, text: str) -> None:
        return None

    async def finish(
        self, generation_id: UUID, status: GenerationStatus, draft_status: DraftStatus
    ) -> None:
        return None

    async def record_context(self, generation_id: UUID, snapshot: dict[str, Any]) -> None:
        return None

    async def record_prompt(
        self,
        generation_id: UUID,
        prompt_name: str,
        prompt_version: int,
        snapshot: dict[str, Any] | None = None,
    ) -> None:
        return None

    async def discard_draft(self, draft_id: UUID) -> Draft | None:
        return Draft(
            id=self.draft.id,
            generation_id=self.draft.generation_id,
            chapter_id=self.draft.chapter_id,
            content=self.draft.content,
            status=DraftStatus.DISCARDED,
        )


def _chapter(work_id: UUID) -> Chapter:
    now = datetime.now(UTC)
    return Chapter(
        id=uuid4(),
        work_id=work_id,
        number=1,
        title="雨夜",
        current_version_id=uuid4(),
        lock_version=1,
        word_count=2,
        created_at=now,
        updated_at=now,
    )


def _version(chapter: Chapter) -> ChapterVersion:
    return ChapterVersion(
        id=chapter.current_version_id or uuid4(),
        chapter_id=chapter.id,
        parent_version_id=None,
        content="正文",
        content_hash="hash",
        source="ai_accepted",
        created_at=datetime.now(UTC),
    )


def _draft(chapter: Chapter) -> Draft:
    return Draft(
        id=uuid4(),
        generation_id=uuid4(),
        chapter_id=chapter.id,
        content="正文",
        status=DraftStatus.READY,
    )


async def test_create_calls_enqueue_and_returns_generation() -> None:
    work_id = uuid4()
    chapter = _chapter(work_id)
    draft = _draft(chapter)
    repo = FakeGenerationRepository(chapter, draft)
    enqueued: list[UUID] = []

    async def enqueue(generation_id: UUID) -> None:
        enqueued.append(generation_id)

    service = GenerationsService(repo, FakeChapterService(chapter, _version(chapter)), enqueue)
    generation = await service.create(
        GenerationCreate(
            work_id=work_id,
            chapter_id=chapter.id,
            task_type=TaskType.CONTINUE,
            instruction="继续",
        ),
        "idem-1",
    )
    assert generation.status is GenerationStatus.QUEUED
    assert len(enqueued) == 1


async def test_create_rejects_work_mismatch() -> None:
    chapter = _chapter(uuid4())
    repo = FakeGenerationRepository(chapter, _draft(chapter))
    service = GenerationsService(repo, FakeChapterService(chapter, _version(chapter)))
    try:
        await service.create(
            GenerationCreate(work_id=uuid4(), chapter_id=chapter.id, task_type=TaskType.CONTINUE),
            "idem-2",
        )
    except ValidationError as exc:
        assert exc.code == "generation.work_mismatch"
    else:
        raise AssertionError("expected ValidationError")


async def test_accept_draft_saves_version_and_records_event() -> None:
    work_id = uuid4()
    chapter = _chapter(work_id)
    draft = _draft(chapter)
    version = _version(chapter)
    repo = FakeGenerationRepository(chapter, draft)
    service = GenerationsService(repo, FakeChapterService(chapter, version))
    accepted: AcceptedDraft = await service.accept_draft(draft.id, base_version=1)
    assert accepted.chapter_version.id == version.id
    assert accepted.draft.status is DraftStatus.ACCEPTED
    assert repo.accepted is not None


async def test_discard_draft_marks_discarded() -> None:
    work_id = uuid4()
    chapter = _chapter(work_id)
    draft = _draft(chapter)
    service = GenerationsService(
        FakeGenerationRepository(chapter, draft), FakeChapterService(chapter, _version(chapter))
    )
    discarded = await service.discard_draft(draft.id)
    assert discarded.status is DraftStatus.DISCARDED


def test_payload_hash_is_stable() -> None:
    command = GenerationCreate(work_id=uuid4(), chapter_id=uuid4(), task_type=TaskType.CONTINUE)
    assert payload_hash(command) == payload_hash(command)
