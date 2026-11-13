from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from webnovel.infra.config import Settings
from webnovel.modules.analysis.contract import AnalysisRun
from webnovel.modules.analysis.runner import AnalysisRunner
from webnovel.modules.chapters_versions.contract import Chapter, ChapterVersion


class FakeRepository:
    def __init__(self, run: AnalysisRun) -> None:
        self.run = run
        self.chapters: list[dict[str, Any]] = []

    async def get_run(self, run_id: UUID) -> AnalysisRun | None:
        return self.run

    async def set_status(
        self,
        run_id: UUID,
        status: str,
        report: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> None:
        self.run = AnalysisRun(
            id=self.run.id,
            work_id=self.run.work_id,
            kind=self.run.kind,
            status=status,
            params=self.run.params,
            report=report or self.run.report,
            error=error,
            created_at=self.run.created_at,
        )

    async def add_chapter(self, run_id: UUID, data: dict[str, Any]) -> None:
        self.chapters.append(data)


class FakeChapterService:
    def __init__(self, chapter: Chapter, version: ChapterVersion) -> None:
        self.chapter = chapter
        self.version = version

    async def list(self, work_id: UUID) -> list[Chapter]:
        return [self.chapter]

    async def get_version(self, chapter_id: UUID, version_id: UUID) -> ChapterVersion:
        return self.version


def _data():
    now = datetime.now(UTC)
    work_id = uuid4()
    chapter = Chapter(
        id=uuid4(),
        work_id=work_id,
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
        content="雨夜追捕。",
        content_hash="h",
        source="manual",
        created_at=now,
    )
    run = AnalysisRun(
        id=uuid4(),
        work_id=work_id,
        kind="reverse_outline",
        status="queued",
        params={},
        report={},
        error=None,
        created_at=now,
    )
    return run, chapter, version


async def test_analysis_runner_builds_report() -> None:
    run, chapter, version = _data()
    repo = FakeRepository(run)
    runner = AnalysisRunner(
        repository=repo,
        chapter_service=FakeChapterService(chapter, version),
        model_client=None,
        settings=Settings(),
    )
    await runner.run(run.id)
    assert repo.run.status == "ready"
    assert repo.run.report["chapter_count"] == 1
    assert repo.chapters[0]["summary"] == "雨夜追捕。"
