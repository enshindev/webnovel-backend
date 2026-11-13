from __future__ import annotations

import os
from pathlib import Path

import yaml
from pydantic import BaseModel, Field


class ProviderConfig(BaseModel):
    name: str
    base_url: str
    api_key: str
    model: str
    timeout_seconds: float = 120.0
    max_retries: int = 2


class ProfileConfig(BaseModel):
    providers: list[ProviderConfig] = Field(default_factory=list)


class RoutingConfig(BaseModel):
    profiles: dict[str, ProfileConfig] = Field(default_factory=dict)


def _expand(value: object) -> object:
    if isinstance(value, str):
        return os.path.expandvars(value)
    if isinstance(value, list):
        return [_expand(item) for item in value]
    if isinstance(value, dict):
        return {key: _expand(item) for key, item in value.items()}
    return value


def load_routing(path: Path) -> RoutingConfig:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return RoutingConfig.model_validate(_expand(data))
