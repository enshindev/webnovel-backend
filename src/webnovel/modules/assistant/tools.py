from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from webnovel.modules.memory.contract import (
    Entity,
    EntityLookup,
    MemoryChunk,
    MemoryRetrievalService,
)


@dataclass(frozen=True, slots=True)
class ToolResult:
    chunks: list[MemoryChunk] = field(default_factory=list)
    entities: list[Entity] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class ToolExecution:
    text: str
    citations: list[dict[str, Any]] = field(default_factory=list)


class AssistantTools:
    """只读工具：检索章节/摘要/实体，不写正文或设定。"""

    def __init__(
        self,
        *,
        retrieval: MemoryRetrievalService | None,
        memory_repository: EntityLookup,
    ) -> None:
        self._retrieval = retrieval
        self._memory_repository = memory_repository

    async def search_chapters(self, work_id: UUID, query: str, limit: int = 5) -> list[MemoryChunk]:
        if self._retrieval is None:
            return []
        return await self._retrieval.retrieve(work_id, query, limit=limit)

    @staticmethod
    def schemas() -> list[dict[str, object]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "search_chapters",
                    "description": "检索作品章节、摘要和记忆片段",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string"},
                            "limit": {"type": "integer", "minimum": 1, "maximum": 10},
                        },
                        "required": ["query"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_entity",
                    "description": "按名称或别名查设定实体",
                    "parameters": {
                        "type": "object",
                        "properties": {"name": {"type": "string"}},
                        "required": ["name"],
                    },
                },
            },
        ]

    async def execute(self, name: str, work_id: UUID, arguments: str) -> ToolExecution:
        try:
            args = json.loads(arguments or "{}")
        except json.JSONDecodeError:
            args = {}
        if name == "search_chapters":
            query = str(args.get("query", ""))
            limit = max(1, min(int(args.get("limit", 5)), 10))
            chunks = await self.search_chapters(work_id, query, limit)
            text = "\n".join(f"[{chunk.source}:{chunk.ref}] {chunk.text[:800]}" for chunk in chunks)
            citations = [
                {"source": chunk.source, "ref": chunk.ref, "quote": chunk.text[:200]}
                for chunk in chunks
            ]
            return ToolExecution(text=text or "没有找到相关章节。", citations=citations)
        if name == "get_entity":
            entity = await self.get_entity(work_id, str(args.get("name", "")))
            if entity is None:
                return ToolExecution(text="没有找到该设定实体。")
            text = f"{entity.type}: {entity.name} {entity.attributes}"
            return ToolExecution(
                text=text,
                citations=[
                    {
                        "source": "entity",
                        "ref": f"entity:{entity.id}",
                        "quote": text[:200],
                    }
                ],
            )
        return ToolExecution(text=f"未知工具：{name}")

    async def gather(self, work_id: UUID, query: str, limit: int = 5) -> ToolResult:
        chunks = await self.search_chapters(work_id, query, limit=limit)
        entities = await self._memory_repository.list_entities(work_id)
        query_folded = query.casefold()
        matched = [
            entity
            for entity in entities
            if entity.name.casefold() in query_folded
            or any(alias.casefold() in query_folded for alias in entity.aliases)
        ][:limit]
        return ToolResult(chunks=chunks, entities=matched)

    async def get_entity(self, work_id: UUID, name: str) -> Entity | None:
        entities = await self._memory_repository.list_entities(work_id)
        wanted = name.casefold()
        for entity in entities:
            names = {entity.name.casefold(), *(alias.casefold() for alias in entity.aliases)}
            if wanted in names:
                return entity
        return None
