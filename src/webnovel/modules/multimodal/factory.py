from __future__ import annotations

from webnovel.infra.config import Settings
from webnovel.modules.multimodal.providers import (
    OpenAICompatibleASR,
    OpenAICompatibleCover,
    OpenAICompatibleTTS,
)
from webnovel.modules.multimodal.service import MultimodalService


def build_multimodal_service(settings: Settings) -> MultimodalService:
    asr = (
        OpenAICompatibleASR(
            base_url=settings.asr_base_url,
            api_key=settings.asr_api_key,
            model=settings.asr_model,
        )
        if settings.asr_base_url and settings.asr_model
        else None
    )
    tts = (
        OpenAICompatibleTTS(
            base_url=settings.tts_base_url,
            api_key=settings.tts_api_key,
            model=settings.tts_model,
            default_voice=settings.tts_voice,
        )
        if settings.tts_base_url and settings.tts_model
        else None
    )
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
