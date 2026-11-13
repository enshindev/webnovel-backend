from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class ContextChunk:
    source: str
    ref: str
    text: str
    tokens: int = 0


@dataclass(frozen=True, slots=True)
class ContextSegment:
    """已由业务模块选好的一段上下文；平台只负责预算、渲染与 manifest。"""

    name: str
    source: str
    ref: str
    text: str
    priority: int = 100
    tokens: int = 0


class ContextSource(Protocol):
    async def fetch(self, work_id: str, query: str, limit: int = 12) -> Sequence[ContextChunk]: ...
