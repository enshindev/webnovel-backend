from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from webnovel.infra.config import Settings
from webnovel.modules.chapters_versions.contract import Chapter, ChapterVersion
from webnovel.modules.memory.contract import (
    ChangeProposal,
    Entity,
    ExtractionRun,
    ExtractionStatus,
    ProposalStatus,
    Summary,
)
from webnovel.modules.memory.extraction import ExtractionRunner, parse_json


class FakeChapterService:
    def __init__(self, chapter: Chapter, version: ChapterVersion) -> None:
        self.chapter = chapter
        self.version = version

    async def get(self, chapter_id: UUID) -> Chapter:
        return self.chapter

    async def get_version(self, chapter_id: UUID, version_id: UUID) -> ChapterVersion:
        return self.version


class FakeModelClient:
    async def complete(self, request: Any) -> str:
        content = request.messages[-1].content
        if "摘要" in content:
            return '{"summary":"本章摘要"}'
        return (
            '{"entities":[{"type":"character","name":"沈砚","aliases":[],'
            '"attributes":{"身份":"捕快"},"confidence":0.9,"quote":"沈砚抬头"}]}'
        )


class FakeMemoryRepository:
    def __init__(self, run: ExtractionRun, existing: Entity | None = None) -> None:
        self.run = run
        self.existing = existing
        self.summaries: list[dict[str, Any]] = []
        self.proposals: list[ChangeProposal] = []
        self.steps: dict[UUID, dict[str, Any]] = {}

    async def create_run(
        self, work_id: UUID, chapter_id: UUID, version_id: UUID, trigger: str
    ) -> ExtractionRun:
        return self.run

    async def get_run(self, run_id: UUID) -> ExtractionRun | None:
        return self.run

    async def set_run_status(
        self, run_id: UUID, status: ExtractionStatus, error: str | None = None
    ) -> None:
        return None

    async def create_step(self, run_id: UUID, kind: str) -> UUID:
        step_id = uuid4()
        self.steps[step_id] = {"kind": kind, "status": "running"}
        return step_id

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
        self.steps[step_id]["status"] = status

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
    ) -> None:
        self.summaries.append({"content": content, "content_hash": content_hash})
        return Summary(
            id=uuid4(),
            work_id=work_id,
            chapter_id=chapter_id,
            content=content,
            based_on_version_id=version_id,
            status="fresh",
        )

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
        proposal = ChangeProposal(
            id=uuid4(),
            work_id=work_id,
            run_id=run_id,
            kind=kind,
            target_entity_id=target_entity_id,
            after=after,
            confidence=confidence,
            source_span=source_span,
            base_entity_version=base_entity_version,
            status=ProposalStatus.PENDING,
            created_at=datetime.now(UTC),
        )
        self.proposals.append(proposal)
        return proposal

    async def find_entity(
        self, work_id: UUID, entity_type: str, name: str, aliases: list[str]
    ) -> Entity | None:
        return self.existing

    async def list_proposals(
        self, work_id: UUID, status: ProposalStatus | None = None
    ) -> list[ChangeProposal]:
        return self.proposals

    async def get_proposal(self, proposal_id: UUID) -> ChangeProposal | None:
        return None

    async def resolve_proposal(
        self,
        proposal_id: UUID,
        action: str,
        *,
        base_entity_version: int,
        modified_payload: dict[str, Any] | None = None,
    ) -> Any:
        return None

    async def list_entities(self, work_id: UUID) -> list[Any]:
        return []


def _chapter_and_version() -> tuple[Chapter, ChapterVersion]:
    now = datetime.now(UTC)
    chapter = Chapter(
        id=uuid4(),
        work_id=uuid4(),
        number=1,
        title="雨夜",
        current_version_id=uuid4(),
        lock_version=1,
        word_count=10,
        created_at=now,
        updated_at=now,
    )
    version = ChapterVersion(
        id=chapter.current_version_id or uuid4(),
        chapter_id=chapter.id,
        parent_version_id=None,
        content="沈砚抬头，看见雨幕里站着一个人。",
        content_hash="hash",
        source="manual",
        created_at=now,
    )
    return chapter, version


async def test_extraction_runner_creates_summary_and_entity_proposals() -> None:
    chapter, version = _chapter_and_version()
    run = ExtractionRun(
        id=uuid4(),
        work_id=chapter.work_id,
        chapter_id=chapter.id,
        version_id=version.id,
        status=ExtractionStatus.PENDING,
        created_at=datetime.now(UTC),
    )
    repo = FakeMemoryRepository(run)
    runner = ExtractionRunner(
        repository=repo,
        chapter_service=FakeChapterService(chapter, version),
        model_client=FakeModelClient(),
        settings=Settings(),
    )
    await runner.run(run.id)
    assert len(repo.summaries) == 1
    assert repo.summaries[0]["content"] == "本章摘要"
    assert len(repo.proposals) == 1
    assert repo.proposals[0].after["name"] == "沈砚"


async def test_extraction_uses_entity_update_when_entity_exists() -> None:
    chapter, version = _chapter_and_version()
    run = ExtractionRun(
        id=uuid4(),
        work_id=chapter.work_id,
        chapter_id=chapter.id,
        version_id=version.id,
        status=ExtractionStatus.PENDING,
        created_at=datetime.now(UTC),
    )
    existing = Entity(
        id=uuid4(),
        work_id=chapter.work_id,
        type="character",
        name="沈砚",
        aliases=[],
        attributes={"身份": "捕快"},
        version=1,
        first_chapter_id=None,
    )
    repo = FakeMemoryRepository(run, existing)
    runner = ExtractionRunner(
        repository=repo,
        chapter_service=FakeChapterService(chapter, version),
        model_client=FakeModelClient(),
        settings=Settings(),
    )
    await runner.run(run.id)
    assert repo.proposals[0].kind == "entity_update"
    assert repo.proposals[0].target_entity_id == existing.id


def test_parse_json_accepts_code_fence() -> None:
    assert parse_json('```json\n{"summary":"ok"}\n```') == {"summary": "ok"}
