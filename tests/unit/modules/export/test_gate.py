from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from webnovel.modules.chapters_versions.contract import Chapter
from webnovel.modules.export.gate import evaluate_gate
from webnovel.modules.quality.contract import QualityIssue, QualityReport


class FakeChapterService:
    def __init__(self, chapters: list[Chapter]) -> None:
        self.chapters = chapters

    async def list(self, work_id: UUID) -> list[Chapter]:
        return self.chapters


class FakeQualityService:
    def __init__(self, reports: list[QualityReport]) -> None:
        self.reports = reports

    async def list_reports(self, work_id: UUID) -> list[QualityReport]:
        return self.reports


def _chapter(work_id: UUID, current: bool = True) -> Chapter:
    now = datetime.now(UTC)
    return Chapter(
        id=uuid4(),
        work_id=work_id,
        number=1,
        title="雨夜",
        current_version_id=uuid4() if current else None,
        lock_version=1,
        word_count=2_000,
        created_at=now,
        updated_at=now,
    )


def _report(
    chapter: Chapter,
    *,
    stage: str,
    status: str = "passed",
    issues: list[QualityIssue] | None = None,
) -> QualityReport:
    return QualityReport(
        id=uuid4(),
        work_id=chapter.work_id,
        chapter_id=chapter.id,
        version_id=chapter.current_version_id or uuid4(),
        status=status,
        score=90,
        issues=issues or [],
        metrics={},
        created_at=datetime.now(UTC),
        stage=stage,
    )


async def test_gate_blocks_missing_machine_check() -> None:
    work_id = uuid4()
    chapter = _chapter(work_id)
    result = await evaluate_gate(
        work_id,
        chapter_service=FakeChapterService([chapter]),
        quality_service=FakeQualityService([]),
    )
    assert any(issue.code == "quality.machine_missing" for issue in result.blocking)


async def test_gate_passes_with_machine_and_review() -> None:
    work_id = uuid4()
    chapter = _chapter(work_id)
    reports = [
        _report(chapter, stage="chapter"),
        _report(chapter, stage="polish"),
    ]
    result = await evaluate_gate(
        work_id,
        chapter_service=FakeChapterService([chapter]),
        quality_service=FakeQualityService(reports),
    )
    assert result.blocking == []


async def test_gate_blocks_p0_issue() -> None:
    work_id = uuid4()
    chapter = _chapter(work_id)
    reports = [
        _report(
            chapter,
            stage="chapter",
            status="failed",
            issues=[QualityIssue(code="logic", severity="P0", message="矛盾")],
        )
    ]
    result = await evaluate_gate(
        work_id,
        chapter_service=FakeChapterService([chapter]),
        quality_service=FakeQualityService(reports),
    )
    assert any(issue.code == "quality.failed" for issue in result.blocking)
    assert any(issue.severity == "P0" for issue in result.blocking)
