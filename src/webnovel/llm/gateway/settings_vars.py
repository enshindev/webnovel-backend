from __future__ import annotations

import os
from pathlib import Path

from dotenv import dotenv_values

from webnovel.infra.config import Settings


def routing_variables(settings: Settings) -> dict[str, str]:
    values: dict[str, str] = {}
    env_file = Path(".env")
    if env_file.is_file():
        values.update(
            {key: value for key, value in dotenv_values(env_file).items() if value is not None}
        )
    values.update(os.environ)
    values.update(
        {
            key: value
            for key, value in {
                "LLM_BASE_URL": getattr(settings, "llm_base_url", ""),
                "LLM_API_KEY": getattr(settings, "llm_api_key", ""),
                "LLM_MODEL": getattr(settings, "llm_model", ""),
                "LOCAL_LLM_BASE_URL": getattr(settings, "local_llm_base_url", ""),
                "LOCAL_LLM_API_KEY": getattr(settings, "local_llm_api_key", ""),
                "LOCAL_LLM_MODEL": getattr(settings, "local_llm_model", ""),
                "ASR_BASE_URL": getattr(settings, "asr_base_url", ""),
                "ASR_API_KEY": getattr(settings, "asr_api_key", ""),
                "ASR_MODEL": getattr(settings, "asr_model", ""),
                "TTS_BASE_URL": getattr(settings, "tts_base_url", ""),
                "TTS_API_KEY": getattr(settings, "tts_api_key", ""),
                "TTS_MODEL": getattr(settings, "tts_model", ""),
                "IMAGE_BASE_URL": getattr(settings, "image_base_url", ""),
                "IMAGE_API_KEY": getattr(settings, "image_api_key", ""),
                "IMAGE_MODEL": getattr(settings, "image_model", ""),
            }.items()
            if value
        }
    )
    return values
