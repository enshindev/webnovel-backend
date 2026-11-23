from __future__ import annotations

import pytest

from webnovel.experiments.multimodal.contract import MultimodalStatus
from webnovel.experiments.multimodal.service import MultimodalService
from webnovel.kernel.errors import UnavailableError


class FakeASR:
    async def transcribe(self, filename: str, content_type: str, data: bytes) -> str:
        assert filename == "a.wav"
        assert data == b"audio"
        return "转写结果"


class FakeTTS:
    async def synthesize(self, text: str, voice: str | None = None) -> bytes:
        assert text == "你好"
        assert voice == "alloy"
        return b"audio-bytes"


class FakeCover:
    async def generate(self, prompt: str, size: str = "1024x1024") -> bytes:
        assert prompt == "雨夜旧巷"
        return b"\xff\xd8\xffimage"


async def test_service_delegates_to_configured_providers() -> None:
    service = MultimodalService(asr=FakeASR(), tts=FakeTTS(), cover=FakeCover())
    assert service.status() == MultimodalStatus(asr=True, tts=True, cover=True)
    assert await service.transcribe("a.wav", "audio/wav", b"audio") == "转写结果"
    assert await service.synthesize("你好", "alloy") == b"audio-bytes"
    assert await service.cover("雨夜旧巷") == b"\xff\xd8\xffimage"


async def test_unconfigured_provider_raises_service_unavailable() -> None:
    service = MultimodalService()
    assert service.status() == MultimodalStatus(asr=False, tts=False, cover=False)
    with pytest.raises(UnavailableError):
        await service.transcribe("a.wav", "audio/wav", b"audio")
