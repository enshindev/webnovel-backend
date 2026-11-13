from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from webnovel.modules.assistant.knowledge_models import KnowledgeEmbeddingModel
from webnovel.modules.assistant.knowledge_types import KnowledgeChunk


class KnowledgeRepository(Protocol):
    async def replace_all(
        self, rows: Sequence[tuple[str, str, str, list[float], str, str]]
    ) -> None: ...

    async def search(self, embedding: list[float], limit: int) -> list[KnowledgeChunk]: ...


class SqlAlchemyKnowledgeRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def replace_all(
        self, rows: Sequence[tuple[str, str, str, list[float], str, str]]
    ) -> None:
        await self._session.execute(delete(KnowledgeEmbeddingModel))
        for source, ref, content, embedding, content_hash, model in rows:
            self._session.add(
                KnowledgeEmbeddingModel(
                    source=source,
                    ref=ref,
                    content=content,
                    embedding=embedding,
                    content_hash=content_hash,
                    model=model,
                )
            )
        await self._session.flush()

    async def search(self, embedding: list[float], limit: int) -> list[KnowledgeChunk]:
        distance = KnowledgeEmbeddingModel.embedding.cosine_distance(embedding)
        stmt = (
            select(KnowledgeEmbeddingModel, distance.label("distance"))
            .order_by(distance)
            .limit(limit)
        )
        rows = (await self._session.execute(stmt)).all()
        return [
            KnowledgeChunk(
                source=row[0].source,
                ref=row[0].ref,
                text=row[0].content,
                score=max(0, int((1 - float(row[1])) * 100)),
            )
            for row in rows
        ]
