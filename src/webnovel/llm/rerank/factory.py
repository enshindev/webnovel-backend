from __future__ import annotations

from webnovel.infra.config import Settings
from webnovel.kernel.ports.rerank import Reranker
from webnovel.llm.rerank.openai_compatible import OpenAICompatibleReranker


def build_reranker(settings: Settings) -> Reranker | None:
    if not settings.rerank_model:
        return None
    base_url = settings.rerank_base_url or settings.embedding_base_url or settings.llm_base_url
    api_key = settings.rerank_api_key or settings.embedding_api_key or settings.llm_api_key
    if not base_url:
        return None
    return OpenAICompatibleReranker(
        base_url=base_url,
        api_key=api_key,
        model=settings.rerank_model,
        timeout=settings.rerank_timeout_seconds,
    )
