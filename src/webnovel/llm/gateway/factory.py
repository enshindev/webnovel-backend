from __future__ import annotations

from webnovel.infra.config import Settings
from webnovel.kernel.ports.llm import ModelClient
from webnovel.llm.gateway.providers.fake import FakeReplayClient
from webnovel.llm.gateway.providers.openai_compatible import OpenAICompatibleClient


def build_model_client(settings: Settings) -> ModelClient:
    if settings.llm_provider == "fake":
        return FakeReplayClient(["雨夜", "追出。\n"], done_text="雨夜追出。\n")
    if not settings.llm_base_url or not settings.llm_model:
        raise RuntimeError("LLM is not configured: set LLM_BASE_URL and LLM_MODEL")
    return OpenAICompatibleClient(
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
        model=settings.llm_model,
        timeout_seconds=settings.llm_timeout_seconds,
    )
