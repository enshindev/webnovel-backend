from __future__ import annotations

from webnovel.infra.config import Settings
from webnovel.modules.multimodal.providers import (
    OpenAICompatibleASR,
    OpenAICompatibleCover,
    OpenAICompatibleTTS,
)
from webnovel.modules.multimodal.service import MultimodalService


def build_transcription_provider(settings: Settings) -> OpenAICompatibleASR | None:
    if not settings.asr_base_url or not settings.asr_model:
        return None
    return OpenAICompatibleASR(
        base_url=settings.asr_base_url,
        api_key=settings.asr_api_key,
        model=settings.asr_model,
    )


def build_speech_provider(settings: Settings) -> OpenAICompatibleTTS | None:
    if not settings.tts_base_url or not settings.tts_model:
        return None
    return OpenAICompatibleTTS(
        base_url=settings.tts_base_url,
        api_key=settings.tts_api_key,
        model=settings.tts_model,
        default_voice=settings.tts_voice,
    )


def build_multimodal_service(settings: Settings) -> MultimodalService:
    asr = build_transcription_provider(settings)
    tts = build_speech_provider(settings)
    cover = (
        OpenAICompatibleCover(
            base_url=settings.image_base_url,
            api_key=settings.image_api_key,
            model=settings.image_model,
        )
        if settings.image_base_url and settings.image_model
        else None
    )
    return MultimodalService(asr=asr, tts=tts, cover=cover)
