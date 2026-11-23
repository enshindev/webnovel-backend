from __future__ import annotations

import yaml
from pydantic import ValidationError

from webnovel.infra.config import Settings
from webnovel.kernel.ports.llm import ModelClient
from webnovel.llm.gateway.client import ProviderTarget, RoutedModelClient
from webnovel.llm.gateway.providers.fake import FakeReplayClient
from webnovel.llm.gateway.providers.openai_compatible import OpenAICompatibleClient
from webnovel.llm.gateway.routing import load_routing


def _routing_variables(settings: Settings) -> dict[str, str]:
    from webnovel.llm.gateway.settings_vars import routing_variables

    return routing_variables(settings)


def _targets(settings: Settings, profile: str) -> list[ProviderTarget]:
    if not settings.routing_config_path.is_file():
        return []
    try:
        config = load_routing(settings.routing_config_path, _routing_variables(settings))
    except (OSError, yaml.YAMLError, ValidationError) as exc:
        raise RuntimeError(f"invalid routing config: {settings.routing_config_path}") from exc
    profile_config = config.profiles.get(profile)
    if profile_config is None:
        return []
    targets: list[ProviderTarget] = []
    for provider in profile_config.providers:
        if not provider.base_url.strip() or not provider.model.strip():
            continue
        targets.append(
            ProviderTarget(
                name=provider.name,
                client=OpenAICompatibleClient(
                    base_url=provider.base_url,
                    api_key=provider.api_key,
                    model=provider.model,
                    timeout_seconds=provider.timeout_seconds,
                ),
                max_retries=provider.max_retries,
                retry_backoff_seconds=provider.retry_backoff_seconds,
            )
        )
    return targets


def _single_client(settings: Settings) -> OpenAICompatibleClient:
    if not settings.llm_base_url or not settings.llm_model:
        raise RuntimeError("LLM is not configured: set LLM_BASE_URL and LLM_MODEL")
    return OpenAICompatibleClient(
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
        model=settings.llm_model,
        timeout_seconds=settings.llm_timeout_seconds,
    )


def build_model_client(settings: Settings, profile: str = "generation") -> ModelClient:
    if settings.llm_provider == "fake":
        return FakeReplayClient(["雨夜", "追出。\n"], done_text="雨夜追出。\n")
    targets = _targets(settings, profile)
    if targets:
        return RoutedModelClient(targets)
    return _single_client(settings)
