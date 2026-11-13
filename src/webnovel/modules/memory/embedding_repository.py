from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from webnovel.modules.memory.models import MemoryEmbeddingModel


@dataclass(frozen=True, slots=True)
class EmbeddingHit:
    source_type: str
    source_id: UUID
    content: str
    distance: float
    chunk_no: int = 0


class EmbeddingRepository(Protocol):
    async def replace_source(
        self,
        *,
        work_id: UUID,
        source_type: str,
        source_id: UUID,
        chunks: Sequence[tuple[str, list[float], str, str]],
    ) -> None: ...

    async def search(
        self, work_id: UUID, embedding: list[float], limit: int
    ) -> list[EmbeddingHit]: ...

    async def list_all(self, work_id: UUID) -> list[EmbeddingHit]: ...


class SqlAlchemyEmbeddingRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def replace_source(
        self,
        *,
        work_id: UUID,
        source_type: str,
        source_id: UUID,
        chunks: Sequence[tuple[str, list[float], str, str]],
    ) -> None:
        await self._session.execute(
            delete(MemoryEmbeddingModel).where(
                MemoryEmbeddingModel.work_id == work_id,
                MemoryEmbeddingModel.source_type == source_type,
                MemoryEmbeddingModel.source_id == source_id,
            )
        )
        for index, (content, embedding, content_hash, model) in enumerate(chunks):
            self._session.add(
                MemoryEmbeddingModel(
                    work_id=work_id,
                    source_type=source_type,
                    source_id=source_id,
                    chunk_no=index,
                    content=content,
                    embedding=embedding,
                    content_hash=content_hash,
                    model=model,
                )
            )
        await self._session.flush()

    async def list_all(self, work_id: UUID) -> list[EmbeddingHit]:
        rows = (
            (
                await self._session.execute(
                    select(MemoryEmbeddingModel).where(MemoryEmbeddingModel.work_id == work_id)
                )
            )
            .scalars()
            .all()
        )
        return [
            EmbeddingHit(row.source_type, row.source_id, row.content, 0.0, row.chunk_no)
            for row in rows
        ]

    async def search(self, work_id: UUID, embedding: list[float], limit: int) -> list[EmbeddingHit]:
        distance = MemoryEmbeddingModel.embedding.cosine_distance(embedding)
        stmt = (
            select(MemoryEmbeddingModel, distance.label("distance"))
            .where(MemoryEmbeddingModel.work_id == work_id)
            .order_by(distance)
            .limit(limit)
        )
        rows = (await self._session.execute(stmt)).all()
        return [
            EmbeddingHit(
                source_type=row[0].source_type,
                source_id=row[0].source_id,
                content=row[0].content,
                distance=float(row[1]),
            )
            for row in rows
        ]
