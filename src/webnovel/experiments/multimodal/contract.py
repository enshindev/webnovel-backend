from __future__ import annotations

from dataclasses import dataclass

from webnovel.kernel.ports.media import CoverProvider, SpeechProvider, TranscriptionProvider

__all__ = [
    "CoverProvider",
    "MultimodalStatus",
    "SpeechProvider",
    "TranscriptionProvider",
]


@dataclass(frozen=True, slots=True)
class MultimodalStatus:
    asr: bool
    tts: bool
    cover: bool
