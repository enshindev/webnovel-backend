from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

from webnovel.infra.config import Settings
from webnovel.modules.chapters_versions.contract import Chapter, ChapterVersion
from webnovel.modules.export.contract import ExportJob, ExportStatus
from webnovel.modules.export.runner import ExportRunner
from webnovel.modules.works.contract import Work


class FakeRepository:
    def __init__(self, job: ExportJob) -> None:
        self.job = job
        self.finished: tuple[ExportStatus, str | None] | None = None

    async def get(self, job_id: UUID) -> ExportJob | None:
        return self.job

    async def finish(
        self, job_id: UUID, status: ExportStatus, file_path: str | None = None
    ) -> None:
        self.finished = (status, file_path)


class FakeChapters:
    def __init__(self, chapter: Chapter, version: ChapterVersion) -> None:
        self.chapter = chapter
        self.version = version

    async def list(self, work_id: UUID) -> list[Chapter]:
        return [self.chapter]

    async def get_version(self, chapter_id: UUID, version_id: UUID) -> ChapterVersion:
        return self.version


class FakeWorks:
    async def get(self, work_id: UUID) -> Work:
        now = datetime.now(UTC)
        return Work(work_id, "长夜灯火", "悬疑", "active", now, now)


class FakeSpeech:
    async def synthesize(self, text: str, voice: str | None = None) -> bytes:
        assert "雨夜" in text
        return b"ID3audio"


class FakeCover:
    async def generate(self, prompt: str, size: str = "1024x1024") -> bytes:
        assert "长夜灯火" in prompt
        return b"\x89PNGcover"


async def test_mp3_export_writes_audio_file(tmp_path: Path) -> None:
    now = datetime.now(UTC)
    work_id = uuid4()
    chapter = Chapter(
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
    version = ChapterVersion(
        id=chapter.current_version_id or uuid4(),
        chapter_id=chapter.id,
        parent_version_id=None,
        content="雨夜。",
        content_hash="hash",
        source="manual",
        created_at=now,
    )
    job = ExportJob(
        id=uuid4(),
        work_id=work_id,
        format="mp3",
        status=ExportStatus.QUEUED,
        file_path=None,
        created_at=now,
    )
    repository = FakeRepository(job)
    runner = ExportRunner(
        repository=repository,  # type: ignore[arg-type]
        chapter_service=FakeChapters(chapter, version),  # type: ignore[arg-type]
        work_service=FakeWorks(),  # type: ignore[arg-type]
        settings=Settings(export_dir=tmp_path),
        speech=FakeSpeech(),
    )

    await runner.run(job.id)

    assert repository.finished is not None
    status, path = repository.finished
    assert status is ExportStatus.SUCCEEDED
    assert path is not None and Path(path).read_bytes() == b"ID3audio"


async def test_cover_export_writes_image_file(tmp_path: Path) -> None:
    now = datetime.now(UTC)
    work_id = uuid4()
    job = ExportJob(
        id=uuid4(),
        work_id=work_id,
        format="cover",
        status=ExportStatus.QUEUED,
        file_path=None,
        created_at=now,
    )
    repository = FakeRepository(job)
    runner = ExportRunner(
        repository=repository,  # type: ignore[arg-type]
        chapter_service=FakeChapters(_chapter(), _version()),  # type: ignore[arg-type]
        work_service=FakeWorks(),  # type: ignore[arg-type]
        settings=Settings(export_dir=tmp_path),
        cover=FakeCover(),
    )

    await runner.run(job.id)

    assert repository.finished is not None
    status, path = repository.finished
    assert status is ExportStatus.SUCCEEDED
    assert path is not None and Path(path).read_bytes() == b"\x89PNGcover"


def _chapter() -> Chapter:
    now = datetime.now(UTC)
    return Chapter(
        id=uuid4(),
        work_id=uuid4(),
        number=1,
        title="雨夜",
        current_version_id=uuid4(),
        lock_version=1,
        word_count=2,
        created_at=now,
        updated_at=now,
    )


def _version() -> ChapterVersion:
    now = datetime.now(UTC)
    return ChapterVersion(
        id=uuid4(),
        chapter_id=uuid4(),
        parent_version_id=None,
        content="雨夜。",
        content_hash="hash",
        source="manual",
        created_at=now,
    )
