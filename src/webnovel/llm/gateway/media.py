from __future__ import annotations

import base64
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import httpx
import yaml
from dotenv import dotenv_values
from pydantic import ValidationError

from webnovel.infra.config import Settings
from webnovel.llm.gateway.errors import ErrorClass, GatewayError
from webnovel.llm.gateway.routing import load_routing


def _raise_gateway_error(exc: httpx.HTTPError) -> None:
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        error_class = (
            ErrorClass.UPSTREAM_UNAVAILABLE if status >= 500 else ErrorClass.INVALID_REQUEST
        )
        raise GatewayError(error_class, str(exc), code_raw=str(status)) from exc
    if isinstance(exc, httpx.TimeoutException):
        raise GatewayError(ErrorClass.TIMEOUT, str(exc)) from exc
    raise GatewayError(ErrorClass.UPSTREAM_UNAVAILABLE, str(exc)) from exc


def _variables(settings: Settings) -> dict[str, str]:
    values: dict[str, str] = {}
    env_file = Path(".env")
    if env_file.is_file():
        values.update(
            {key: value for key, value in dotenv_values(env_file).items() if value is not None}
        )
    values.update(os.environ)
    values.update(
        {
            "ASR_BASE_URL": settings.asr_base_url,
            "ASR_API_KEY": settings.asr_api_key,
            "ASR_MODEL": settings.asr_model,
            "TTS_BASE_URL": settings.tts_base_url,
            "TTS_API_KEY": settings.tts_api_key,
            "TTS_MODEL": settings.tts_model,
            "IMAGE_BASE_URL": settings.image_base_url,
            "IMAGE_API_KEY": settings.image_api_key,
            "IMAGE_MODEL": settings.image_model,
        }
    )
    return {key: value for key, value in values.items() if value}


@dataclass(frozen=True, slots=True)
class MediaTarget:
    name: str
    base_url: str
    api_key: str
    model: str
    timeout: float
    max_retries: int = 1


def _targets(settings: Settings, profile: str) -> list[MediaTarget]:
    if not settings.routing_config_path.is_file():
        return []
    try:
        config = load_routing(settings.routing_config_path, _variables(settings))
    except (OSError, yaml.YAMLError, ValidationError) as exc:
        raise RuntimeError(f"invalid routing config: {settings.routing_config_path}") from exc
    profile_config = config.profiles.get(profile)
    if profile_config is None:
        return []
    return [
        MediaTarget(
            name=provider.name,
            base_url=provider.base_url,
            api_key=provider.api_key,
            model=provider.model,
            timeout=provider.timeout_seconds,
            max_retries=provider.max_retries,
        )
        for provider in profile_config.providers
        if provider.base_url.strip() and provider.model.strip()
    ]


class OpenAICompatibleASR:
    def __init__(self, *, base_url: str, api_key: str, model: str, timeout: float = 120.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._model = model
        self._timeout = timeout

    async def transcribe(self, filename: str, content_type: str, data: bytes) -> str:
        headers = {"Authorization": f"Bearer {self._api_key}"} if self._api_key else {}
        try:
            async with httpx.AsyncClient(base_url=self._base_url, headers=headers) as client:
                response = await client.post(
                    "/audio/transcriptions",
                    data={"model": self._model},
                    files={"file": (filename, data, content_type or "application/octet-stream")},
                    timeout=self._timeout,
                )
                response.raise_for_status()
                return str(response.json().get("text", "")).strip()
        except httpx.HTTPError as exc:
            _raise_gateway_error(exc)
            raise


class OpenAICompatibleTTS:
    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        default_voice: str = "alloy",
        timeout: float = 120.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._model = model
        self._default_voice = default_voice
        self._timeout = timeout

    async def synthesize(self, text: str, voice: str | None = None) -> bytes:
        headers = {"Authorization": f"Bearer {self._api_key}"} if self._api_key else {}
        try:
            async with httpx.AsyncClient(base_url=self._base_url, headers=headers) as client:
                response = await client.post(
                    "/audio/speech",
                    json={
                        "model": self._model,
                        "input": text,
                        "voice": voice or self._default_voice,
                    },
                    timeout=self._timeout,
                )
                response.raise_for_status()
                return response.content
        except httpx.HTTPError as exc:
            _raise_gateway_error(exc)
            raise


class OpenAICompatibleCover:
    def __init__(self, *, base_url: str, api_key: str, model: str, timeout: float = 120.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._model = model
        self._timeout = timeout

    async def generate(self, prompt: str, size: str = "1024x1024") -> bytes:
        headers = {"Authorization": f"Bearer {self._api_key}"} if self._api_key else {}
        try:
            async with httpx.AsyncClient(base_url=self._base_url, headers=headers) as client:
                response = await client.post(
                    "/images/generations",
                    json={"model": self._model, "prompt": prompt, "n": 1, "size": size},
                    timeout=self._timeout,
                )
                response.raise_for_status()
                item = (response.json().get("data") or [{}])[0]
                if item.get("b64_json"):
                    return base64.b64decode(item["b64_json"])
                if item.get("url"):
                    image = await client.get(str(item["url"]), timeout=self._timeout)
                    image.raise_for_status()
                    return image.content
        except httpx.HTTPError as exc:
            _raise_gateway_error(exc)
            raise
        raise ValueError("image provider returned no data")


class MediaGateway:
    """ASR/TTS/图像调用的统一网关：routing.yaml profile + fallback。"""

    def __init__(self, targets: list[MediaTarget], profile: str) -> None:
        self._targets = targets
        self._profile = profile
        self.model = targets[0].model if targets else ""
        self.provider_name = targets[0].name if targets else ""

    @property
    def available(self) -> bool:
        return bool(self._targets)

    async def transcribe(self, filename: str, content_type: str, data: bytes) -> str:
        return cast(str, await self._call("transcribe", filename, content_type, data))

    async def synthesize(self, text: str, voice: str | None = None) -> bytes:
        return cast(bytes, await self._call("synthesize", text, voice))

    async def generate(self, prompt: str, size: str = "1024x1024") -> bytes:
        return cast(bytes, await self._call("generate", prompt, size))

    async def _call(self, method: str, *args: Any) -> Any:
        last_error: GatewayError | None = None
        for target in self._targets:
            provider: Any
            if method == "transcribe":
                provider = OpenAICompatibleASR(
                    base_url=target.base_url,
                    api_key=target.api_key,
                    model=target.model,
                    timeout=target.timeout,
                )
            elif method == "synthesize":
                provider = OpenAICompatibleTTS(
                    base_url=target.base_url,
                    api_key=target.api_key,
                    model=target.model,
                    timeout=target.timeout,
                )
            else:
                provider = OpenAICompatibleCover(
                    base_url=target.base_url,
                    api_key=target.api_key,
                    model=target.model,
                    timeout=target.timeout,
                )
            try:
                return await getattr(provider, method)(*args)
            except GatewayError as exc:
                last_error = exc
                continue
        if last_error is not None:
            raise last_error
        raise GatewayError(ErrorClass.INVALID_REQUEST, f"{self._profile} is not configured")


def build_media_gateway(settings: Settings, profile: str) -> MediaGateway | None:
    targets = _targets(settings, profile)
    return MediaGateway(targets, profile) if targets else None
