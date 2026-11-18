from __future__ import annotations

from webnovel.infra.config import Settings
from webnovel.llm.gateway.media import MediaGateway, build_media_gateway
from webnovel.modules.multimodal.service import MultimodalService
from webnovel.modules.usage.contract import UsageService


def build_transcription_provider(settings: Settings) -> MediaGateway | None:
    return build_media_gateway(settings, "asr")


def build_speech_provider(settings: Settings) -> MediaGateway | None:
    return build_media_gateway(settings, "tts")


def build_cover_provider(settings: Settings) -> MediaGateway | None:
    return build_media_gateway(settings, "image")


def build_multimodal_service(
    settings: Settings, usage: UsageService | None = None
) -> MultimodalService:
    return MultimodalService(
        asr=build_transcription_provider(settings),
        tts=build_speech_provider(settings),
        cover=build_cover_provider(settings),
        usage=usage,
    )
