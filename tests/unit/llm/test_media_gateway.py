from __future__ import annotations

from pathlib import Path

from webnovel.infra.config import Settings
from webnovel.llm.gateway.media import build_media_gateway


def test_build_media_gateway_from_routing_profile() -> None:
    settings = Settings(
        routing_config_path=Path("config/routing.yaml"),
        asr_base_url="http://asr.local/v1",
        asr_model="whisper-test",
    )
    gateway = build_media_gateway(settings, "asr")
    assert gateway is not None
    assert gateway.available is True
    assert gateway.model == "whisper-test"


def test_media_gateway_is_none_when_profile_unconfigured() -> None:
    settings = Settings(
        routing_config_path=Path("config/routing.yaml"),
        asr_base_url="",
        asr_model="",
    )
    assert build_media_gateway(settings, "asr") is None
