from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from webnovel.kernel.errors import ConflictError
from webnovel.modules.chapters_versions.contract import Chapter
from webnovel.modules.export.contract import ExportJob, ExportStatus
from webnovel.modules.export.service import ExportServiceImpl
from webnovel.modules.quality.contract import QualityReport
from webnovel.modules.works.contract import Work


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


class FakeWorkService:
    async def get(self, work_id: UUID) -> Work:
        now = datetime.now(UTC)
        return Work(work_id, "长夜灯火", "悬疑", "active", now, now)


class FakeExportRepository:
    async def create(self, work_id: UUID, fmt: str) -> ExportJob:
        return ExportJob(
            id=uuid4(),
            work_id=work_id,
            format=fmt,
            status=ExportStatus.QUEUED,
            file_path=None,
            created_at=datetime.now(UTC),
        )

    async def get(self, job_id: UUID) -> ExportJob | None:
        return None

    async def finish(
        self, job_id: UUID, status: ExportStatus, file_path: str | None = None
    ) -> None:
        return None


async def test_create_export_requires_gate() -> None:
    work_id = uuid4()
    chapter = Chapter(
        id=uuid4(),
        work_id=work_id,
        number=1,
        title="雨夜",
        current_version_id=uuid4(),
        lock_version=1,
        word_count=2_000,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    service = ExportServiceImpl(
        FakeExportRepository(),
        chapter_service=FakeChapterService([chapter]),
        quality_service=FakeQualityService([]),
        work_service=FakeWorkService(),
    )
    try:
        await service.create(work_id, "txt")
    except ConflictError as exc:
        assert exc.code == "export.gate_blocked"
    else:
        raise AssertionError("expected ConflictError")
