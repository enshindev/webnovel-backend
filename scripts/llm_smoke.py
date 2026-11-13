from __future__ import annotations

import asyncio

from webnovel.infra.config import get_settings
from webnovel.kernel.ports.llm import ChatMessage, ModelRequest
from webnovel.llm.embeddings.factory import build_embedding_client
from webnovel.llm.gateway.factory import build_model_client


async def main() -> None:
    settings = get_settings()
    client = build_model_client(settings)
    response = await client.complete(
        ModelRequest(
            model=settings.llm_model,
            messages=[ChatMessage(role="user", content="用一句中文回答：你好。")],
            max_tokens=200,
        )
    )
    print("chat:", response)
    embedding = build_embedding_client(settings)
    if embedding is None:
        print("embedding: not configured")
        return
    vectors = await embedding.embed(["测试向量"])
    print("embedding:", len(vectors), "vectors,", len(vectors[0]), "dimensions")


if __name__ == "__main__":
    asyncio.run(main())
