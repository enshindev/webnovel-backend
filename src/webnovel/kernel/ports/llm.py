from __future__ import annotations

from collections.abc import AsyncIterator, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

Role = Literal["system", "user", "assistant", "tool"]


@dataclass(frozen=True, slots=True)
class ToolCall:
    id: str
    name: str
    arguments: str


@dataclass(frozen=True, slots=True)
class ChatMessage:
    role: Role
    content: str
    tool_call_id: str | None = None
    tool_calls: Sequence[ToolCall] | None = None


@dataclass(frozen=True, slots=True)
class ModelRequest:
    model: str
    messages: Sequence[ChatMessage]
    temperature: float = 0.8
    max_tokens: int | None = None
    response_format: Mapping[str, Any] | None = None
    tools: Sequence[Mapping[str, Any]] | None = None
    timeout_seconds: float = 120.0


@dataclass(frozen=True, slots=True)
class ModelUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cached_tokens: int = 0
    estimated: bool = False


@dataclass(frozen=True, slots=True)
class ModelEvent:
    type: Literal["delta", "usage", "done", "error", "tool_calls"]
    text: str = ""
    usage: ModelUsage | None = None
    tool_calls: Sequence[ToolCall] | None = None
    error_class: str | None = None
    error_code_raw: str | None = None


@dataclass(frozen=True, slots=True)
class ModelResponse:
    text: str
    tool_calls: Sequence[ToolCall] = ()
    usage: ModelUsage = field(default_factory=ModelUsage)


class ModelClient(Protocol):
    def stream(self, request: ModelRequest) -> AsyncIterator[ModelEvent]: ...

    async def complete(self, request: ModelRequest) -> str: ...


class EmbeddingClient(Protocol):
    async def embed(self, texts: Sequence[str]) -> list[list[float]]: ...


@dataclass(frozen=True, slots=True)
class ModelCallRecord:
    provider: str
    model: str
    usage: ModelUsage = field(default_factory=ModelUsage)
