from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from webnovel.modules.chapters_versions.contract import Chapter, ChapterVersion
from webnovel.modules.quality.contract import QualityReport
from webnovel.modules.quality.repository import QualityRepository
from webnovel.modules.quality.rules import PlatformRules
from webnovel.modules.quality.service import QualityServiceImpl


class FakeChapterService:
    def __init__(self, chapter: Chapter, version: ChapterVersion) -> None:
        self.chapter = chapter
        self.version = version

    async def get(self, chapter_id: UUID) -> Chapter:
        return self.chapter

    async def get_version(self, chapter_id: UUID, version_id: UUID) -> ChapterVersion:
        return self.version

    async def list(self, work_id: UUID) -> list[Chapter]:
        return [self.chapter]


class FakeQualityRepository(QualityRepository):
    async def save(self, report: QualityReport) -> QualityReport:
        return QualityReport(
            id=uuid4(),
            work_id=report.work_id,
            chapter_id=report.chapter_id,
            version_id=report.version_id,
            status=report.status,
            score=report.score,
            issues=report.issues,
            metrics=report.metrics,
            created_at=datetime.now(UTC),
        )

    async def get(self, report_id: UUID) -> QualityReport | None:
        return None

    async def list(self, work_id: UUID) -> list[QualityReport]:
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
        word_count=2_000,
        created_at=now,
        updated_at=now,
    )
    version = ChapterVersion(
        id=chapter.current_version_id or uuid4(),
        chapter_id=chapter.id,
        parent_version_id=None,
        content="正文。" * 800,
        content_hash="hash",
        source="manual",
        created_at=now,
    )
    return chapter, version


async def test_check_chapter_saves_passing_report() -> None:
    chapter, version = _chapter_and_version()
    service = QualityServiceImpl(
        FakeQualityRepository(), FakeChapterService(chapter, version), PlatformRules()
    )
    report = await service.check_chapter(chapter.work_id, chapter.id)
    assert report.status == "passed"
    assert report.score == 100


async def test_check_chapter_includes_story_contradictions() -> None:
    chapter, version = _chapter_and_version()

    async def contradictions(work_id: UUID) -> list[object]:
        return [
            type(
                "Contradiction",
                (),
                {
                    "kind": "knowledge.conflict",
                    "severity": "P1",
                    "message": "角色同时知道和不知道同一件事",
                    "chapter_number": chapter.number,
                },
            )()
        ]

    service = QualityServiceImpl(
        FakeQualityRepository(),
        FakeChapterService(chapter, version),
        PlatformRules(),
        contradictions=contradictions,
    )
    report = await service.check_chapter(chapter.work_id, chapter.id)
    assert report.status == "warning"
    assert report.metrics["contradictions"] == 1
    assert any(issue.code == "knowledge.conflict" for issue in report.issues)
