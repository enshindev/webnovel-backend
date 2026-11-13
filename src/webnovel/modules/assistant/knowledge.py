from __future__ import annotations

import math
import re
from pathlib import Path

from webnovel.kernel.ports.embeddings import EmbeddingClient
from webnovel.modules.assistant.knowledge_repository import KnowledgeRepository
from webnovel.modules.assistant.knowledge_types import KnowledgeChunk


class KnowledgeRetriever:
    def __init__(self, root: Path, embedding_client: EmbeddingClient | None = None) -> None:
        self._chunks: list[tuple[str, str, str]] = []
        self._embedding_client = embedding_client
        self._vectors: list[list[float]] | None = None
        if root.is_dir():
            for path in sorted(root.rglob("*.md")):
                if path.name == "README.md":
                    continue
                text = path.read_text(encoding="utf-8", errors="ignore")
                for index, paragraph in enumerate(re.split(r"\n\s*\n", text)):
                    paragraph = paragraph.strip()
                    if len(paragraph) < 10:
                        continue
                    self._chunks.append(
                        (
                            path.relative_to(root).as_posix(),
                            f"{path.stem}:{index}",
                            paragraph,
                        )
                    )

    async def asearch(self, query: str, limit: int = 3) -> list[KnowledgeChunk]:
        if self._embedding_client is None or not self._chunks:
            return self.search(query, limit)
        try:
            if self._vectors is None:
                self._vectors = await self._embedding_client.embed(
                    [text for _, _, text in self._chunks]
                )
            query_vector = (await self._embedding_client.embed([query]))[0]
            ranked = sorted(
                (
                    (
                        _cosine(query_vector, vector),
                        source,
                        ref,
                        text,
                    )
                    for vector, (source, ref, text) in zip(self._vectors, self._chunks, strict=True)
                ),
                key=lambda item: item[0],
                reverse=True,
            )
            return [
                KnowledgeChunk(source=source, ref=ref, text=text, score=int(score * 100))
                for score, source, ref, text in ranked[:limit]
                if score > 0
            ]
        except Exception:
            return self.search(query, limit)

    @property
    def chunks(self) -> list[tuple[str, str, str]]:
        return list(self._chunks)

    def search(self, query: str, limit: int = 3) -> list[KnowledgeChunk]:
        terms = {query[index : index + 2].casefold() for index in range(max(0, len(query) - 1))}
        if not terms:
            return []
        scored: list[KnowledgeChunk] = []
        for source, ref, text in self._chunks:
            folded = text.casefold()
            score = sum(1 for term in terms if term in folded)
            if score:
                scored.append(KnowledgeChunk(source=source, ref=ref, text=text, score=score))
        scored.sort(key=lambda chunk: (-chunk.score, chunk.ref))
        return scored[:limit]


def _cosine(left: list[float], right: list[float]) -> float:
    dot = sum(a * b for a, b in zip(left, right, strict=True))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return dot / (left_norm * right_norm)


class KnowledgeSearchService:
    def __init__(self, client: EmbeddingClient, repository: KnowledgeRepository) -> None:
        self._client = client
        self._repository = repository

    async def search(self, query: str, limit: int = 3) -> list[KnowledgeChunk]:
        vectors = await self._client.embed([query])
        if not vectors:
            return []
        return await self._repository.search(vectors[0], limit)


class KnowledgeIndexer:
    def __init__(self, client: EmbeddingClient, repository: KnowledgeRepository) -> None:
        self._client = client
        self._repository = repository

    async def index(self, retriever: KnowledgeRetriever) -> int:
        chunks = retriever.chunks
        if not chunks:
            return 0
        vectors = await self._client.embed([text for _, _, text in chunks])
        rows = [
            (source, ref, text, vector, "", "embedding")
            for (source, ref, text), vector in zip(chunks, vectors, strict=True)
        ]
        await self._repository.replace_all(rows)
        return len(rows)
