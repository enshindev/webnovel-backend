from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class TranscriptionProvider(Protocol):
    async def transcribe(self, filename: str, content_type: str, data: bytes) -> str: ...


class SpeechProvider(Protocol):
    async def synthesize(self, text: str, voice: str | None = None) -> bytes: ...


class CoverProvider(Protocol):
    async def generate(self, prompt: str, size: str = "1024x1024") -> bytes: ...


@dataclass(frozen=True, slots=True)
class MultimodalStatus:
    asr: bool
    tts: bool
    cover: bool
