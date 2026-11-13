from __future__ import annotations

from typing import Any, cast
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from webnovel.modules.memory.models import EntityModel, EntityRelationModel

ENTITY_TYPES = {"character", "faction", "location", "rule", "item"}


class EntityMaterializerImpl:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def materialize(
        self,
        work_id: UUID,
        nodes: list[dict[str, Any]],
        edges: list[dict[str, Any]],
    ) -> dict[str, UUID]:
        mapping: dict[str, UUID] = {}
        for node in nodes:
            node_id = str(node.get("id", "")).strip()
            name = str(node.get("name", "")).strip()
            entity_type = str(node.get("type", "")).strip()
            if not node_id or not name or entity_type not in ENTITY_TYPES:
                continue
            entity = EntityModel(
                work_id=work_id,
                type=entity_type,
                name=name,
                aliases=[str(item) for item in cast(list[Any], node.get("aliases", []))],
                attributes=cast(dict[str, Any], node.get("attributes", {})),
                version=1,
                first_chapter_id=None,
            )
            self._session.add(entity)
            await self._session.flush()
            mapping[node_id] = entity.id

        for edge in edges:
            source = mapping.get(str(edge.get("from", "")))
            target = mapping.get(str(edge.get("to", "")))
            relation_type = str(edge.get("type", "")).strip()
            if source is None or target is None or not relation_type:
                continue
            self._session.add(
                EntityRelationModel(
                    work_id=work_id,
                    from_entity_id=source,
                    to_entity_id=target,
                    relation_type=relation_type,
                )
            )
        await self._session.flush()
        return mapping
