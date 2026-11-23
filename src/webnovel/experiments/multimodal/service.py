from __future__ import annotations

from uuid import UUID

from webnovel.kernel.errors import UnavailableError
from webnovel.experiments.multimodal.contract import (
    CoverProvider,
    MultimodalStatus,
    SpeechProvider,
    TranscriptionProvider,
)
from webnovel.modules.usage.contract import UsageService, record_media_usage


class MultimodalService:
    def __init__(
        self,
        *,
        asr: TranscriptionProvider | None = None,
        tts: SpeechProvider | None = None,
        cover: CoverProvider | None = None,
        usage: UsageService | None = None,
    ) -> None:
        self._asr = asr
        self._tts = tts
        self._cover = cover
        self._usage = usage

    def status(self) -> MultimodalStatus:
        return MultimodalStatus(
            asr=self._asr is not None,
            tts=self._tts is not None,
            cover=self._cover is not None,
        )

    async def transcribe(
        self, filename: str, content_type: str, data: bytes, *, work_id: UUID | None = None
    ) -> str:
        if self._asr is None:
            raise UnavailableError("ASR is not configured", code="multimodal.asr_unavailable")
        text = await self._asr.transcribe(filename, content_type, data)
        await self._record("asr", work_id, len(data), len(text), self._asr)
        return text

    async def synthesize(
        self, text: str, voice: str | None = None, *, work_id: UUID | None = None
    ) -> bytes:
        if self._tts is None:
            raise UnavailableError("TTS is not configured", code="multimodal.tts_unavailable")
        audio = await self._tts.synthesize(text, voice)
        await self._record("tts", work_id, len(text), len(audio) // 1024, self._tts)
        return audio

    async def cover(
        self, prompt: str, size: str = "1024x1024", *, work_id: UUID | None = None
    ) -> bytes:
        if self._cover is None:
            raise UnavailableError(
                "image provider is not configured", code="multimodal.cover_unavailable"
            )
        image = await self._cover.generate(prompt, size)
        await self._record("cover", work_id, len(prompt), len(image) // 1024, self._cover)
        return image

    async def _record(
        self,
        task: str,
        work_id: UUID | None,
        prompt_units: int,
        output_units: int,
        provider: object,
    ) -> None:
        await record_media_usage(
            self._usage,
            work_id=work_id,
            task=task,
            model=str(getattr(provider, "model", "multimodal") or "multimodal"),
            prompt_units=prompt_units,
            output_units=output_units,
        )
