from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    env: str = "dev"
    database_url: str = "postgresql+asyncpg://webnovel:webnovel@localhost:5432/webnovel"
    redis_url: str = "redis://localhost:6379/0"

    llm_base_url: str = ""
    llm_api_key: str = ""
    llm_model: str = ""
    llm_provider: str = "openai-compatible"
    local_llm_base_url: str = ""
    local_llm_api_key: str = ""
    local_llm_model: str = ""
    daily_budget: float | None = None
    assistant_enabled: bool = True
    story_state_contradictions_in_quality: bool = False
    assistant_max_tool_rounds: int = 20
    assistant_tool_timeout_seconds: float = 30.0
    assistant_library_search_enabled: bool = False
    enable_experiments: bool = False
    api_token: str = ""
    rate_limit_per_minute: int = 0
    cors_origins: str = ""
    cors_allow_credentials: bool = False
    outbox_webhook_url: str = ""
    log_json: bool = False
    log_level: str = "INFO"

    embedding_base_url: str = ""
    embedding_api_key: str = ""
    embedding_model: str = ""
    embedding_dimensions: int = 1024
    rerank_base_url: str = ""
    rerank_api_key: str = ""
    rerank_model: str = ""
    llm_timeout_seconds: float = 120.0
    embedding_timeout_seconds: float = 30.0
    rerank_timeout_seconds: float = 30.0

    asr_base_url: str = ""
    asr_api_key: str = ""
    asr_model: str = ""
    tts_base_url: str = ""
    tts_api_key: str = ""
    tts_model: str = ""
    tts_voice: str = "alloy"
    image_base_url: str = ""
    image_api_key: str = ""
    image_model: str = ""

    otel_exporter_otlp_endpoint: str | None = None
    context_max_tokens: int = 16_000
    prompts_dir: Path = Path("prompts")
    evals_dir: Path = Path("evals")
    knowledge_dir: Path = Path("knowledge")
    platform_config_path: Path = Path("config/platform.yaml")
    routing_config_path: Path = Path("config/routing.yaml")
    export_dir: Path = Path("data/exports")
    library_dir: Path = Path("data/library")
    pricing_config_path: Path = Path("config/pricing.yaml")

    def model_post_init(self, __context: object) -> None:
        """把相对路径解析为绝对路径，并在启动时校验目录存在。"""
        for field in (
            "prompts_dir",
            "evals_dir",
            "knowledge_dir",
            "platform_config_path",
            "routing_config_path",
            "export_dir",
            "library_dir",
            "pricing_config_path",
        ):
            path: Path = getattr(self, field).expanduser()
            if not path.is_absolute():
                path = (Path.cwd() / path).resolve()
            object.__setattr__(self, field, path)
            if field in {"prompts_dir", "evals_dir"} and not path.is_dir():
                raise ValueError(f"{field} does not exist: {path}")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
