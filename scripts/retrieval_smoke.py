from __future__ import annotations

import asyncio

from webnovel.infra.config import get_settings
from webnovel.llm.embeddings.factory import build_embedding_client
from webnovel.llm.rerank.factory import build_reranker


async def main() -> None:
    settings = get_settings()
    embedding = build_embedding_client(settings)
    if embedding is None:
        print("embedding: not configured")
        return
    vectors = await embedding.embed(["雨夜旧巷的灯", "晴天散步"])
    print("embedding:", len(vectors), "vectors,", len(vectors[0]), "dimensions")
    reranker = build_reranker(settings)
    if reranker is None:
        print("rerank: not configured")
        return
    results = await reranker.rerank("旧巷的灯", ["雨夜旧巷灯灭", "晴天散步"], top_n=2)
    print("rerank:", [(item.index, round(item.score, 4)) for item in results])


if __name__ == "__main__":
    asyncio.run(main())
