from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID, uuid4

from webnovel.kernel.errors import ConflictError, NotFoundError
from webnovel.modules.chapters_versions.contract import Chapter, ChapterVersion
from webnovel.modules.chapters_versions.service import ChaptersService, count_words, hash_content
from webnovel.modules.works.contract import Work


class FakeWorkService:
    async def get(self, work_id: UUID) -> Work:
        now = datetime.now(UTC)
        return Work(work_id, "长夜灯火", "悬疑", "active", now, now)


class FakeChapterRepository:
    def __init__(self) -> None:
        self.chapters: dict[UUID, Chapter] = {}
        self.versions: dict[UUID, list[ChapterVersion]] = {}
        self.next_save_conflict = False

    async def add(
        self,
        *,
        work_id: UUID,
        number: int,
        title: str,
        content: str,
        content_hash: str,
        word_count: int,
    ) -> Chapter:
        now = datetime.now(UTC)
        chapter = Chapter(
            id=uuid4(),
            work_id=work_id,
            number=number,
            title=title,
            current_version_id=None,
            lock_version=1 if content else 0,
            word_count=word_count,
            created_at=now,
            updated_at=now,
        )
        self.chapters[chapter.id] = chapter
        self.versions[chapter.id] = []
        if content:
            version = ChapterVersion(
                id=uuid4(),
                chapter_id=chapter.id,
                parent_version_id=None,
                content=content,
                content_hash=content_hash,
                source="manual",
                created_at=now,
            )
            self.versions[chapter.id].append(version)
            chapter = replace(chapter, current_version_id=version.id)
            self.chapters[chapter.id] = chapter
        return chapter

    async def list(self, work_id: UUID) -> list[Chapter]:
        return [c for c in self.chapters.values() if c.work_id == work_id]

    async def get(self, chapter_id: UUID) -> Chapter | None:
        return self.chapters.get(chapter_id)

    async def save(
        self,
        *,
        chapter_id: UUID,
        base_version: int,
        content: str,
        content_hash: str,
        word_count: int,
        title: str | None,
    ) -> Chapter | None:
        if self.next_save_conflict:
            raise ConflictError("conflict", code="chapter.version_conflict")
        chapter = self.chapters[chapter_id]
        now = datetime.now(UTC)
        version = ChapterVersion(
            id=uuid4(),
            chapter_id=chapter_id,
            parent_version_id=chapter.current_version_id,
            content=content,
            content_hash=content_hash,
            source="manual",
            created_at=now,
        )
        self.versions[chapter_id].insert(0, version)
        updated = Chapter(
            id=chapter.id,
            work_id=chapter.work_id,
            number=chapter.number,
            title=title or chapter.title,
            current_version_id=version.id,
            lock_version=chapter.lock_version + 1,
            word_count=word_count,
            created_at=chapter.created_at,
            updated_at=now,
        )
        self.chapters[chapter_id] = updated
        return updated

    async def versions(self, chapter_id: UUID) -> list[ChapterVersion]:
        return self.versions[chapter_id]

    async def get_version(self, chapter_id: UUID, version_id: UUID) -> ChapterVersion | None:
        return next((v for v in self.versions[chapter_id] if v.id == version_id), None)


async def test_hash_and_count() -> None:
    assert hash_content("abc") == hash_content("abc")
    assert count_words("长夜灯火") == 4


async def test_create_chapter_with_content() -> None:
    repo = FakeChapterRepository()
    service = ChaptersService(repo, FakeWorkService())
    chapter = await service.create(uuid4(), 1, "雨夜", "正文")
    assert chapter.lock_version == 1
    assert chapter.current_version_id is not None
    assert chapter.word_count == 2


async def test_save_bumps_version_and_keeps_parent() -> None:
    repo = FakeChapterRepository()
    service = ChaptersService(repo, FakeWorkService())
    chapter = await service.create(uuid4(), 1, "雨夜", "一")
    updated = await service.save(chapter.id, chapter.lock_version, "二")
    assert updated.lock_version == chapter.lock_version + 1
    assert updated.current_version_id != chapter.current_version_id


async def test_get_missing_chapter() -> None:
    service = ChaptersService(FakeChapterRepository(), FakeWorkService())
    try:
        await service.get(uuid4())
    except NotFoundError as exc:
        assert exc.code == "chapter.not_found"
    else:
        raise AssertionError("expected NotFoundError")


class FakeVolumeService:
    def __init__(self, work_id: UUID) -> None:
        self.work_id = work_id

    async def get(self, volume_id: UUID):
        from webnovel.modules.volumes.contract import Volume

        return Volume(volume_id, self.work_id, 1, "卷", datetime.now(UTC))


async def test_assign_volume_rejects_other_work() -> None:
    from webnovel.kernel.errors import ValidationError

    class Repo(FakeChapterRepository):
        async def set_volume(self, chapter_id: UUID, volume_id: UUID | None):
            return self.chapters[chapter_id]

    repo = Repo()
    works = FakeWorkService()
    chapter = await ChaptersService(repo, works).create(uuid4(), 1, "第一章", "正文")
    service = ChaptersService(repo, works, FakeVolumeService(uuid4()))  # type: ignore[arg-type]
    try:
        await service.assign_volume(chapter.id, uuid4())
    except ValidationError as exc:
        assert exc.code == "chapter.volume_work_mismatch"
    else:
        raise AssertionError("expected validation error")
