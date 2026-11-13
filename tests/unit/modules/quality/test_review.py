from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from webnovel.infra.config import Settings
from webnovel.modules.chapters_versions.contract import ChapterVersion
from webnovel.modules.quality.contract import QualityIssue, QualityReport
from webnovel.modules.quality.review import QualityReviewRunner


class FakeChapterService:
    def __init__(self, version: ChapterVersion) -> None:
        self.version = version

    async def get_version(self, chapter_id: UUID, version_id: UUID) -> ChapterVersion:
        return self.version


class FakeModelClient:
    async def complete(self, request: Any) -> str:
        assert "审稿" in request.messages[-1].content
        return (
            '{"score":86,"issues":[{"severity":"P1","type":"logic",'
            '"detail":"时间线冲突","suggestion":"补一句时间过渡"}]}'
        )


class FakeQualityRepository:
    def __init__(self, report: QualityReport) -> None:
        self.report = report
        self.saved: dict[str, Any] | None = None

    async def get(self, report_id: UUID) -> QualityReport | None:
        return self.report

    async def save_review(
        self,
        report_id: UUID,
        *,
        status: str,
        score: int,
        metrics: dict[str, Any],
        issues: list[QualityIssue],
    ) -> QualityReport | None:
        self.saved = {"status": status, "score": score, "metrics": metrics, "issues": issues}
        return self.report


async def test_review_runner_saves_llm_issues() -> None:
    now = datetime.now(UTC)
    report = QualityReport(
        id=uuid4(),
        work_id=uuid4(),
        chapter_id=uuid4(),
        version_id=uuid4(),
        status="queued",
        score=0,
        issues=[],
        metrics={},
        created_at=now,
    )
    version = ChapterVersion(
        id=report.version_id,
        chapter_id=report.chapter_id,
        parent_version_id=None,
        content="正文。" * 100,
        content_hash="hash",
        source="manual",
        created_at=now,
    )
    repo = FakeQualityRepository(report)
    runner = QualityReviewRunner(
        repository=repo,
        chapter_service=FakeChapterService(version),
        model_client=FakeModelClient(),
        settings=Settings(),
    )
    await runner.run(report.id)
    assert repo.saved is not None
    assert repo.saved["status"] == "warning"
    assert repo.saved["score"] == 86
    assert repo.saved["issues"][0].code == "logic"
