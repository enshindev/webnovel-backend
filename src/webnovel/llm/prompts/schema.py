from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class PromptInclude(BaseModel):
    """共享片段引用；必须锁版本，禁止 latest。"""

    model_config = ConfigDict(extra="forbid")

    id: str
    version: int = Field(ge=1)


class PromptSpec(BaseModel):
    """prompts/<module>/<task>/vNNN.yaml 的 schema。"""

    model_config = ConfigDict(extra="forbid")

    id: str
    version: int = Field(ge=1)
    template: str
    variables: list[str]
    defaults: dict[str, Any] = Field(default_factory=dict)
    includes: list[PromptInclude] = Field(default_factory=list)

    @field_validator("template")
    @classmethod
    def template_not_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("template must not be empty")
        return value

    @field_validator("variables")
    @classmethod
    def variables_unique(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("variables must be unique")
        return value
