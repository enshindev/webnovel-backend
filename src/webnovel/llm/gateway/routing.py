from __future__ import annotations

import os
import re
from collections.abc import Mapping
from pathlib import Path

import yaml
from pydantic import BaseModel, Field

_VARIABLE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")


class ProviderConfig(BaseModel):
    name: str
    base_url: str
    api_key: str = ""
    model: str
    timeout_seconds: float = Field(default=120.0, gt=0)
    max_retries: int = Field(default=2, ge=0, le=10)
    retry_backoff_seconds: float = Field(default=0.5, ge=0, le=30)


class ProfileConfig(BaseModel):
    providers: list[ProviderConfig] = Field(default_factory=list)


class RoutingConfig(BaseModel):
    profiles: dict[str, ProfileConfig] = Field(default_factory=dict)


def _expand(value: object, variables: Mapping[str, str]) -> object:
    if isinstance(value, str):
        return _VARIABLE.sub(lambda match: variables.get(match.group(1), ""), value)
    if isinstance(value, list):
        return [_expand(item, variables) for item in value]
    if isinstance(value, dict):
        return {key: _expand(item, variables) for key, item in value.items()}
    return value


def load_routing(path: Path, variables: Mapping[str, str] | None = None) -> RoutingConfig:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    env = os.environ if variables is None else variables
    return RoutingConfig.model_validate(_expand(data, env))
