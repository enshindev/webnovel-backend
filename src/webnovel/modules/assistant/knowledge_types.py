from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class KnowledgeChunk:
    source: str
    ref: str
    text: str
    score: int
