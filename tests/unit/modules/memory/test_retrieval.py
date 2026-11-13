from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

from webnovel.modules.memory.chapter_embedding_repository import (
    ChapterEmbeddingRepository,
)
from webnovel.modules.memory.contract import Entity, Summary
from webnovel.modules.memory.embedding_repository import EmbeddingHit
from webnovel.modules.memory.retrieval import MemoryVectorService


class FakeEmbeddingClient:
    dimensions = 3

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [[1.0, 0.0, 0.0] for _ in texts]


class FakeEmbeddingRepository:
    def __init__(self) -> None:
        self.replacements: list[dict[str, Any]] = []

    async def replace_source(
        self,
        *,
        work_id: UUID,
        source_type: str,
        source_id: UUID,
        chunks: list[tuple[str, list[float], str, str]],
    ) -> None:
        self.replacements.append(
            {
                "work_id": work_id,
                "source_type": source_type,
                "source_id": source_id,
                "chunks": chunks,
            }
        )

    async def search(self, work_id: UUID, embedding: list[float], limit: int) -> list[EmbeddingHit]:
        return [EmbeddingHit("summary", uuid4(), "旧摘要", 0.2)]


async def test_index_summary_and_retrieve() -> None:
    repo = FakeEmbeddingRepository()
    service = MemoryVectorService(client=FakeEmbeddingClient(), repository=repo, model_name="fake")
    summary = Summary(
        id=uuid4(),
        work_id=uuid4(),
        chapter_id=uuid4(),
        content="第一章摘要",
        based_on_version_id=uuid4(),
        status="fresh",
    )
    await service.index_summary(summary)
    assert repo.replacements[0]["source_type"] == "summary"
    assert repo.replacements[0]["chunks"][0][0] == "第一章摘要"

    chunks = await service.retrieve(summary.work_id, "沈砚是谁", limit=3)
    assert chunks[0].source == "summary"
    assert chunks[0].text == "旧摘要"


async def test_index_entity_contains_name_and_attributes() -> None:
    repo = FakeEmbeddingRepository()
    service = MemoryVectorService(client=FakeEmbeddingClient(), repository=repo, model_name="fake")
    entity = Entity(
        id=uuid4(),
        work_id=uuid4(),
        type="character",
        name="沈砚",
        aliases=[],
        attributes={"身份": "捕快"},
        version=1,
        first_chapter_id=None,
    )
    await service.index_entity(entity)
    content = repo.replacements[0]["chunks"][0][0]
    assert "沈砚" in content
    assert "捕快" in content


class FakeChapterEmbeddingRepository(ChapterEmbeddingRepository):
    def __init__(self) -> None:
        self.replacements: list[dict[str, Any]] = []

    async def replace_version(
        self,
        *,
        work_id: UUID,
        chapter_id: UUID,
        version_id: UUID,
        chunks: list[tuple[str, list[float], str, str]],
    ) -> None:
        self.replacements.append({"chunks": chunks})

    async def search(self, work_id: UUID, embedding: list[float], limit: int) -> list[EmbeddingHit]:
        return [EmbeddingHit("chapter", uuid4(), "正文片段", 0.3, chunk_no=1)]


async def test_index_chapter_and_hybrid_retrieve() -> None:
    memory_repo = FakeEmbeddingRepository()
    chapter_repo = FakeChapterEmbeddingRepository()
    service = MemoryVectorService(
        client=FakeEmbeddingClient(),
        repository=memory_repo,
        model_name="fake",
        chapter_repository=chapter_repo,
    )
    await service.index_chapter(uuid4(), uuid4(), uuid4(), "第一段。" * 500)
    assert chapter_repo.replacements
    chunks = await service.retrieve(uuid4(), "沈砚", limit=5)
    assert {chunk.source for chunk in chunks} == {"summary", "chapter"}
