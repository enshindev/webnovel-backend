from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from webnovel.modules.memory.embedding_repository import EmbeddingHit
from webnovel.modules.memory.models import ChapterEmbeddingModel


class ChapterEmbeddingRepository(Protocol):
    async def replace_version(
        self,
        *,
        work_id: UUID,
        chapter_id: UUID,
        version_id: UUID,
        chunks: Sequence[tuple[str, list[float], str, str]],
    ) -> None: ...

    async def search(
        self, work_id: UUID, embedding: list[float], limit: int
    ) -> list[EmbeddingHit]: ...

    async def list_all(self, work_id: UUID) -> list[EmbeddingHit]: ...


class SqlAlchemyChapterEmbeddingRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def replace_version(
        self,
        *,
        work_id: UUID,
        chapter_id: UUID,
        version_id: UUID,
        chunks: Sequence[tuple[str, list[float], str, str]],
    ) -> None:
        await self._session.execute(
            delete(ChapterEmbeddingModel).where(ChapterEmbeddingModel.version_id == version_id)
        )
        for index, (text, embedding, content_hash, model) in enumerate(chunks):
            self._session.add(
                ChapterEmbeddingModel(
                    work_id=work_id,
                    chapter_id=chapter_id,
                    version_id=version_id,
                    chunk_index=index,
                    text=text,
                    embedding=embedding,
                    content_hash=content_hash,
                    status="fresh",
                    model=model,
                )
            )
        await self._session.flush()

    async def list_all(self, work_id: UUID) -> list[EmbeddingHit]:
        rows = (
            (
                await self._session.execute(
                    select(ChapterEmbeddingModel).where(ChapterEmbeddingModel.work_id == work_id)
                )
            )
            .scalars()
            .all()
        )
        return [
            EmbeddingHit("chapter", row.chapter_id, row.text, 0.0, row.chunk_index) for row in rows
        ]

    async def search(self, work_id: UUID, embedding: list[float], limit: int) -> list[EmbeddingHit]:
        distance = ChapterEmbeddingModel.embedding.cosine_distance(embedding)
        stmt = (
            select(ChapterEmbeddingModel, distance.label("distance"))
            .where(ChapterEmbeddingModel.work_id == work_id)
            .order_by(distance)
            .limit(limit)
        )
        rows = (await self._session.execute(stmt)).all()
        return [
            EmbeddingHit(
                source_type="chapter",
                source_id=row[0].chapter_id,
                content=row[0].text,
                distance=float(row[1]),
                chunk_no=row[0].chunk_index,
            )
            for row in rows
        ]
