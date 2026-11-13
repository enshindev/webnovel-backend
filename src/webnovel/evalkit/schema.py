from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class EvalCaseSpec(BaseModel):
    """evals/<module>/<task>/cases.jsonl 的单行 schema。"""

    model_config = ConfigDict(extra="forbid")

    id: str
    input: dict[str, Any]
    expected_facts: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    rubric: str = ""
    tags: list[str] = Field(default_factory=list)
    must_pass: bool = False

    @field_validator("id")
    @classmethod
    def id_not_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("id must not be empty")
        return value
