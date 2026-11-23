from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID


@dataclass(frozen=True, slots=True)
class GraphNode:
    id: UUID
    type: str
    name: str
    aliases: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class GraphEdge:
    id: UUID
    from_entity_id: UUID
    to_entity_id: UUID
    relation_type: str


@dataclass(frozen=True, slots=True)
class GraphEvent:
    id: UUID
    chapter_number: int
    summary: str


@dataclass(frozen=True, slots=True)
class GraphSubgraph:
    seed_id: UUID
    depth: int
    nodes: list[GraphNode] = field(default_factory=list)
    edges: list[GraphEdge] = field(default_factory=list)
    events: list[GraphEvent] = field(default_factory=list)
