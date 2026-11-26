from __future__ import annotations

import hashlib
from collections.abc import Awaitable, Callable, Sequence
from uuid import UUID

from webnovel.kernel.errors import NotFoundError, ValidationError
from webnovel.modules.chapters_versions.contract import Chapter, ChapterVersion
from webnovel.modules.chapters_versions.repository import ChapterRepository
from webnovel.modules.volumes.contract import VolumeService
from webnovel.modules.works.contract import WorkService


def hash_content(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def count_words(content: str) -> int:
    return len(content)


class ChaptersService:
    def __init__(
        self,
        repository: ChapterRepository,
        work_service: WorkService,
        volume_service: VolumeService | None = None,
        on_saved: Callable[[UUID, str], Awaitable[None]] | None = None,
    ) -> None:
        self._repository = repository
        self._work_service = work_service
        self._volume_service = volume_service
        self._on_saved = on_saved

    async def create(self, work_id: UUID, number: int, title: str, content: str = "") -> Chapter:
        if number <= 0:
            raise ValidationError("chapter number must be positive", code="chapter.invalid_number")
        await self._work_service.get(work_id)
        content_hash = hash_content(content)
        return await self._repository.add(
            work_id=work_id,
            number=number,
            title=title,
            content=content,
            content_hash=content_hash,
            word_count=count_words(content),
        )

    async def list(self, work_id: UUID) -> Sequence[Chapter]:
        await self._work_service.get(work_id)
        return await self._repository.list(work_id)

    async def get(self, chapter_id: UUID) -> Chapter:
        chapter = await self._repository.get(chapter_id)
        if chapter is None:
            raise NotFoundError(f"chapter not found: {chapter_id}", code="chapter.not_found")
        return chapter

    async def save(
        self, chapter_id: UUID, base_version: int, content: str, title: str | None = None
    ) -> Chapter:
        if base_version < 0:
            raise ValidationError("base_version must be >= 0", code="chapter.invalid_version")
        chapter = await self._repository.save(
            chapter_id=chapter_id,
            base_version=base_version,
            content=content,
            content_hash=hash_content(content),
            word_count=count_words(content),
            title=title,
        )
        if chapter is None:
            raise NotFoundError(f"chapter not found: {chapter_id}", code="chapter.not_found")
        if self._on_saved is not None:
            try:
                await self._on_saved(chapter_id, content)
            except Exception:
                import logging

                logging.getLogger(__name__).exception("chapter.save_observer_failed")
        return chapter

    async def assign_volume(self, chapter_id: UUID, volume_id: UUID | None) -> Chapter:
        chapter = await self.get(chapter_id)
        if volume_id is not None:
            if self._volume_service is None:
                raise ValidationError(
                    "volume validation unavailable", code="chapter.volume_validation_unavailable"
                )
            volume = await self._volume_service.get(volume_id)
            if volume.work_id != chapter.work_id:
                raise ValidationError(
                    "volume does not belong to chapter work", code="chapter.volume_work_mismatch"
                )
        updated = await self._repository.set_volume(chapter_id, volume_id)
        if updated is None:
            raise NotFoundError(f"chapter not found: {chapter_id}", code="chapter.not_found")
        return updated

    async def versions(self, chapter_id: UUID) -> Sequence[ChapterVersion]:
        await self.get(chapter_id)
        return await self._repository.versions(chapter_id)

    async def get_version(self, chapter_id: UUID, version_id: UUID) -> ChapterVersion:
        version = await self._repository.get_version(chapter_id, version_id)
        if version is None:
            raise NotFoundError(
                f"chapter version not found: {version_id}", code="chapter.version_not_found"
            )
        return version
