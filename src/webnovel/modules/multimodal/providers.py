from __future__ import annotations

import base64

import httpx


class OpenAICompatibleASR:
    def __init__(self, *, base_url: str, api_key: str, model: str, timeout: float = 120.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._model = model
        self._timeout = timeout

    async def transcribe(self, filename: str, content_type: str, data: bytes) -> str:
        headers = {"Authorization": f"Bearer {self._api_key}"} if self._api_key else {}
        async with httpx.AsyncClient(base_url=self._base_url, headers=headers) as client:
            response = await client.post(
                "/audio/transcriptions",
                data={"model": self._model},
                files={"file": (filename, data, content_type or "application/octet-stream")},
                timeout=self._timeout,
            )
            response.raise_for_status()
            return str(response.json().get("text", "")).strip()


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


class OpenAICompatibleCover:
    def __init__(self, *, base_url: str, api_key: str, model: str, timeout: float = 120.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._model = model
        self._timeout = timeout

    async def generate(self, prompt: str, size: str = "1024x1024") -> bytes:
        headers = {"Authorization": f"Bearer {self._api_key}"} if self._api_key else {}
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
        raise ValueError("image provider returned no data")
