from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from webnovel.kernel.errors import ConflictError
from webnovel.modules.chapters_versions.contract import Chapter, ChapterVersion
from webnovel.modules.chapters_versions.models import ChapterModel, ChapterVersionModel


class ChapterRepository(Protocol):
    async def add(
        self,
        *,
        work_id: UUID,
        number: int,
        title: str,
        content: str,
        content_hash: str,
        word_count: int,
    ) -> Chapter: ...

    async def list(self, work_id: UUID) -> Sequence[Chapter]: ...

    async def get(self, chapter_id: UUID) -> Chapter | None: ...

    async def save(
        self,
        *,
        chapter_id: UUID,
        base_version: int,
        content: str,
        content_hash: str,
        word_count: int,
        title: str | None,
    ) -> Chapter | None: ...

    async def versions(self, chapter_id: UUID) -> Sequence[ChapterVersion]: ...

    async def get_version(self, chapter_id: UUID, version_id: UUID) -> ChapterVersion | None: ...

    async def set_volume(self, chapter_id: UUID, volume_id: UUID | None) -> Chapter | None: ...


def _to_domain(model: ChapterModel) -> Chapter:
    return Chapter(
        id=model.id,
        work_id=model.work_id,
        number=model.number,
        title=model.title,
        current_version_id=model.current_version_id,
        lock_version=model.lock_version,
        word_count=model.word_count,
        created_at=model.created_at,
        updated_at=model.updated_at,
        volume_id=model.volume_id,
    )


def _version_to_domain(model: ChapterVersionModel) -> ChapterVersion:
    return ChapterVersion(
        id=model.id,
        chapter_id=model.chapter_id,
        parent_version_id=model.parent_version_id,
        content=model.content,
        content_hash=model.content_hash,
        source=model.source,
        created_at=model.created_at,
    )


class SqlAlchemyChapterRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

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
        model = ChapterModel(
            work_id=work_id,
            number=number,
            title=title,
            lock_version=1 if content else 0,
            word_count=word_count,
        )
        self._session.add(model)
        try:
            await self._session.flush()
        except IntegrityError as exc:
            raise ConflictError(
                f"chapter number already exists: {number}", code="chapter.number_exists"
            ) from exc

        if content:
            version = ChapterVersionModel(
                chapter_id=model.id,
                parent_version_id=None,
                content=content,
                content_hash=content_hash,
                source="manual",
            )
            self._session.add(version)
            await self._session.flush()
            model.current_version_id = version.id

        await self._session.flush()
        await self._session.refresh(model)
        return _to_domain(model)

    async def list(self, work_id: UUID) -> Sequence[Chapter]:
        stmt = (
            select(ChapterModel)
            .where(ChapterModel.work_id == work_id)
            .order_by(ChapterModel.number.asc())
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_to_domain(row) for row in rows]

    async def get(self, chapter_id: UUID) -> Chapter | None:
        model = await self._session.get(ChapterModel, chapter_id)
        return _to_domain(model) if model is not None else None

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
        stmt = select(ChapterModel).where(ChapterModel.id == chapter_id).with_for_update()
        model = (await self._session.execute(stmt)).scalar_one_or_none()
        if model is None:
            return None
        if model.lock_version != base_version:
            raise ConflictError(
                f"chapter version conflict: expected {model.lock_version}, got {base_version}",
                code="chapter.version_conflict",
            )

        version = ChapterVersionModel(
            chapter_id=model.id,
            parent_version_id=model.current_version_id,
            content=content,
            content_hash=content_hash,
            source="manual",
        )
        self._session.add(version)
        await self._session.flush()

        model.current_version_id = version.id
        model.lock_version += 1
        model.word_count = word_count
        if title is not None:
            model.title = title
        await self._session.flush()
        await self._session.refresh(model)
        return _to_domain(model)

    async def versions(self, chapter_id: UUID) -> Sequence[ChapterVersion]:
        stmt = (
            select(ChapterVersionModel)
            .where(ChapterVersionModel.chapter_id == chapter_id)
            .order_by(ChapterVersionModel.created_at.desc())
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_version_to_domain(row) for row in rows]

    async def set_volume(self, chapter_id: UUID, volume_id: UUID | None) -> Chapter | None:
        model = await self._session.get(ChapterModel, chapter_id)
        if model is None:
            return None
        model.volume_id = volume_id
        await self._session.flush()
        await self._session.refresh(model)
        return _to_domain(model)

    async def get_version(self, chapter_id: UUID, version_id: UUID) -> ChapterVersion | None:
        stmt = select(ChapterVersionModel).where(
            ChapterVersionModel.id == version_id,
            ChapterVersionModel.chapter_id == chapter_id,
        )
        model = (await self._session.execute(stmt)).scalar_one_or_none()
        return _version_to_domain(model) if model is not None else None
