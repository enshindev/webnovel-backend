from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Query
from pydantic import BaseModel, ConfigDict

from webnovel.entrypoints.api.deps import GraphRagServiceDep

router = APIRouter(prefix="/experiments/graphrag", tags=["graphrag"])


class GraphNodeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    type: str
    name: str
    aliases: list[str]


class GraphEdgeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    from_entity_id: UUID
    to_entity_id: UUID
    relation_type: str


class GraphEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    chapter_number: int
    summary: str


class GraphSubgraphOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    seed_id: UUID
    depth: int
    nodes: list[GraphNodeOut]
    edges: list[GraphEdgeOut]
    events: list[GraphEventOut]


@router.get("/{work_id}/subgraph", response_model=GraphSubgraphOut)
async def get_subgraph(
    work_id: UUID,
    service: GraphRagServiceDep,
    entity_id: UUID | None = None,
    name: str | None = None,
    depth: int = Query(default=1, ge=1, le=2),
) -> GraphSubgraphOut:
    return GraphSubgraphOut.model_validate(
        await service.subgraph(work_id, entity_id=entity_id, name=name, depth=depth)
    )
