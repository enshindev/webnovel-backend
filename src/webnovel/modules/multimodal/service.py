from __future__ import annotations

from webnovel.kernel.errors import UnavailableError
from webnovel.modules.multimodal.contract import (
    CoverProvider,
    SpeechProvider,
    TranscriptionProvider,
)


class MultimodalService:
    def __init__(
        self,
        *,
        asr: TranscriptionProvider | None = None,
        tts: SpeechProvider | None = None,
        cover: CoverProvider | None = None,
    ) -> None:
        self._asr = asr
        self._tts = tts
        self._cover = cover

    def status(self) -> dict[str, bool]:
        return {
            "asr": self._asr is not None,
            "tts": self._tts is not None,
            "cover": self._cover is not None,
        }

    async def transcribe(self, filename: str, content_type: str, data: bytes) -> str:
        if self._asr is None:
            raise UnavailableError("ASR is not configured", code="multimodal.asr_unavailable")
        return await self._asr.transcribe(filename, content_type, data)

    async def synthesize(self, text: str, voice: str | None = None) -> bytes:
        if self._tts is None:
            raise UnavailableError("TTS is not configured", code="multimodal.tts_unavailable")
        return await self._tts.synthesize(text, voice)

    async def cover(self, prompt: str, size: str = "1024x1024") -> bytes:
        if self._cover is None:
            raise UnavailableError(
                "image provider is not configured", code="multimodal.cover_unavailable"
            )
        return await self._cover.generate(prompt, size)
