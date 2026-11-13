from __future__ import annotations

import hashlib
import json
from typing import Any
from uuid import UUID

from webnovel.kernel.ports.embeddings import EmbeddingClient
from webnovel.kernel.ports.rerank import Reranker
from webnovel.llm.retrieval.bm25 import BM25Index
from webnovel.llm.retrieval.fusion import reciprocal_rank_fusion
from webnovel.llm.usage import estimate_tokens
from webnovel.modules.memory.chapter_embedding_repository import ChapterEmbeddingRepository
from webnovel.modules.memory.chunking import chunk_text
from webnovel.modules.memory.contract import (
    Entity,
    MemoryChunk,
    MemoryIndexer,
    MemoryRetrievalService,
    Summary,
)
from webnovel.modules.memory.embedding_repository import EmbeddingRepository
from webnovel.modules.usage.contract import UsageService


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class MemoryVectorService(MemoryIndexer, MemoryRetrievalService):
    def __init__(
        self,
        *,
        client: EmbeddingClient,
        repository: EmbeddingRepository,
        model_name: str,
        chapter_repository: ChapterEmbeddingRepository | None = None,
        usage: UsageService | None = None,
        reranker: Reranker | None = None,
    ) -> None:
        self._client = client
        self._repository = repository
        self._model_name = model_name
        self._chapter_repository = chapter_repository
        self._usage = usage
        self._reranker = reranker

    async def index_summary(self, summary: Summary) -> None:
        content = summary.content.strip()
        if not content:
            return
        vector = await self._embed_one(content)
        await self._record_embedding(summary.work_id, [content])
        await self._repository.replace_source(
            work_id=summary.work_id,
            source_type="summary",
            source_id=summary.id,
            chunks=[(content, vector, _hash(content), self._model_name)],
        )

    async def index_entity(self, entity: Entity) -> None:
        attributes = json.dumps(entity.attributes, ensure_ascii=False, sort_keys=True)
        content = f"{entity.type} {entity.name}\n{attributes}"
        vector = await self._embed_one(content)
        await self._record_embedding(entity.work_id, [content])
        await self._repository.replace_source(
            work_id=entity.work_id,
            source_type="entity",
            source_id=entity.id,
            chunks=[(content, vector, _hash(content), self._model_name)],
        )

    async def index_chapter(
        self, work_id: UUID, chapter_id: UUID, version_id: UUID, text: str
    ) -> None:
        if self._chapter_repository is None:
            return
        chunks = chunk_text(text)
        if not chunks:
            return
        vectors = await self._client.embed(chunks)
        await self._record_embedding(work_id, chunks)
        if len(vectors) != len(chunks):
            raise ValueError("embedding response count mismatch")
        payload = [
            (chunk, vector, _hash(chunk), self._model_name)
            for chunk, vector in zip(chunks, vectors, strict=True)
        ]
        await self._chapter_repository.replace_version(
            work_id=work_id,
            chapter_id=chapter_id,
            version_id=version_id,
            chunks=payload,
        )

    async def retrieve(self, work_id: UUID, query: str, limit: int = 6) -> list[MemoryChunk]:
        if not query.strip():
            return []
        vector = await self._embed_one(query)
        memory_hits = await self._repository.search(work_id, vector, max(1, min(limit, 20)))
        chapter_hits = (
            await self._chapter_repository.search(work_id, vector, max(1, min(limit, 20)))
            if self._chapter_repository is not None
            else []
        )

        lookup: dict[str, MemoryChunk] = {}
        memory_refs: list[str] = []
        for hit in memory_hits:
            ref = f"{hit.source_type}:{hit.source_id}:{hit.chunk_no}"
            memory_refs.append(ref)
            lookup[ref] = MemoryChunk(
                source=hit.source_type,
                ref=ref,
                text=hit.content,
                tokens=max(1, len(hit.content)),
            )

        chapter_refs: list[str] = []
        for hit in chapter_hits:
            ref = f"{hit.source_type}:{hit.source_id}:{hit.chunk_no}"
            chapter_refs.append(ref)
            lookup[ref] = MemoryChunk(
                source=hit.source_type,
                ref=ref,
                text=hit.content,
                tokens=max(1, len(hit.content)),
            )

        bm25_refs: list[str] = []
        all_hits: list[Any] = []
        memory_list_all = getattr(self._repository, "list_all", None)
        if memory_list_all is not None:
            memory_all = await memory_list_all(work_id)
            if memory_all:
                all_hits.extend(memory_all)
        if self._chapter_repository is not None:
            chapter_list_all = getattr(self._chapter_repository, "list_all", None)
            if chapter_list_all is not None:
                chapter_all = await chapter_list_all(work_id)
                if chapter_all:
                    all_hits.extend(chapter_all)
        if all_hits:
            for hit in all_hits:
                ref = f"{hit.source_type}:{hit.source_id}:{hit.chunk_no}"
                lookup.setdefault(
                    ref,
                    MemoryChunk(
                        source=hit.source_type,
                        ref=ref,
                        text=hit.content,
                        tokens=max(1, len(hit.content)),
                    ),
                )
            bm25 = BM25Index([hit.content for hit in all_hits])
            bm25_refs = [
                f"{all_hits[index].source_type}:{all_hits[index].source_id}:{all_hits[index].chunk_no}"
                for index, _ in bm25.search(query, max(1, min(limit, 20)))
            ]

        fused = reciprocal_rank_fusion([memory_refs, chapter_refs, bm25_refs])
        candidates = [lookup[ref] for ref, _ in fused if ref in lookup][:20]
        if self._reranker is None or len(candidates) < 2:
            return candidates[:limit]
        try:
            reranked = await self._reranker.rerank(
                query, [chunk.text for chunk in candidates], top_n=limit
            )
            return [
                candidates[item.index] for item in reranked if 0 <= item.index < len(candidates)
            ]
        except Exception:
            return candidates[:limit]

    async def _record_embedding(self, work_id: UUID, texts: list[str]) -> None:
        if self._usage is None:
            return
        try:
            await self._usage.record_llm(
                work_id=work_id,
                generation_id=None,
                provider="embedding",
                model=self._model_name,
                task_type=None,
                prompt_tokens=sum(estimate_tokens(text) for text in texts),
                completion_tokens=0,
                estimated=True,
            )
        except Exception:
            return

    async def _embed_one(self, text: str) -> list[float]:
        vectors = await self._client.embed([text])
        if len(vectors) != 1:
            raise ValueError("embedding response count mismatch")
        vector = vectors[0]
        if len(vector) != self._client.dimensions:
            raise ValueError("embedding dimension mismatch")
        return vector
