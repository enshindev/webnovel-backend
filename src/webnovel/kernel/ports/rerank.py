from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class RerankResult:
    index: int
    score: float


class Reranker(Protocol):
    async def rerank(
        self, query: str, documents: Sequence[str], top_n: int
    ) -> list[RerankResult]: ...
