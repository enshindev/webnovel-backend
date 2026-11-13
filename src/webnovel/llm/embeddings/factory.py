from __future__ import annotations

from webnovel.infra.config import Settings
from webnovel.kernel.ports.embeddings import EmbeddingClient
from webnovel.llm.embeddings.openai_compatible import OpenAICompatibleEmbeddingClient


def build_embedding_client(settings: Settings) -> EmbeddingClient | None:
    if not settings.embedding_model:
        return None
    base_url = settings.embedding_base_url or settings.llm_base_url
    api_key = settings.embedding_api_key or settings.llm_api_key
    if not base_url:
        return None
    return OpenAICompatibleEmbeddingClient(
        base_url=base_url,
        api_key=api_key,
        model=settings.embedding_model,
        dimensions=settings.embedding_dimensions,
        timeout=settings.embedding_timeout_seconds,
    )
