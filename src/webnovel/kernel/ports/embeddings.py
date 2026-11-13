from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol


class EmbeddingClient(Protocol):
    @property
    def dimensions(self) -> int: ...

    async def embed(self, texts: Sequence[str]) -> list[list[float]]: ...
