from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from webnovel.modules.library.contract import LibraryService
from webnovel.modules.memory.contract import (
    Entity,
    EntityLookup,
    MemoryChunk,
    MemoryRetrievalService,
    MemoryService,
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
        story_state: MemoryService | None = None,
        library: LibraryService | None = None,
    ) -> None:
        self._retrieval = retrieval
        self._memory_repository = memory_repository
        self._story_state = story_state
        self._library = library

    async def search_chapters(self, work_id: UUID, query: str, limit: int = 5) -> list[MemoryChunk]:
        if self._retrieval is None:
            return []
        return await self._retrieval.retrieve(work_id, query, limit=limit)

    def schemas(self) -> list[dict[str, object]]:
        schemas: list[dict[str, object]] = [
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
            {
                "type": "function",
                "function": {
                    "name": "who_knows",
                    "description": "查某个事实在某一章之前被哪些角色知道或怀疑",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "fact_key": {"type": "string"},
                            "at_chapter": {"type": "integer", "minimum": 1},
                        },
                        "required": ["fact_key"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_story_events",
                    "description": "按章节区间查故事事件",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "from_chapter": {"type": "integer", "minimum": 1},
                            "to_chapter": {"type": "integer", "minimum": 1},
                        },
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_relations",
                    "description": "查某个角色或实体的关系，一跳",
                    "parameters": {
                        "type": "object",
                        "properties": {"name": {"type": "string"}},
                        "required": ["name"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_timeline",
                    "description": "查作品时间线事件",
                    "parameters": {
                        "type": "object",
                        "properties": {"limit": {"type": "integer", "minimum": 1, "maximum": 50}},
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_summary",
                    "description": "按章节 ID 查章节摘要",
                    "parameters": {
                        "type": "object",
                        "properties": {"chapter_id": {"type": "string"}},
                        "required": ["chapter_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "list_foreshadows",
                    "description": "列出作品的伏笔",
                    "parameters": {"type": "object", "properties": {}},
                },
            },
        ]
        if self._library is not None:
            schemas.append(
                {
                    "type": "function",
                    "function": {
                        "name": "search_library",
                        "description": "检索作者资料库",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "query": {"type": "string"},
                                "limit": {"type": "integer", "minimum": 1, "maximum": 10},
                            },
                            "required": ["query"],
                        },
                    },
                }
            )
        return schemas

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
        if name == "who_knows":
            if self._story_state is None:
                return ToolExecution(text="故事状态暂不可用。")
            fact_key = str(args.get("fact_key", "")).strip()
            at_chapter = args.get("at_chapter")
            states = await self._story_state.who_knows(
                work_id,
                fact_key,
                at_chapter=int(at_chapter) if at_chapter is not None else None,
            )
            if not states:
                return ToolExecution(text="没有找到知道该事实的角色。")
            text = "\n".join(
                f"{state.character_name}：{state.state}（第 {state.chapter_number} 章）"
                for state in states
            )
            return ToolExecution(
                text=text,
                citations=[
                    {
                        "source": "knowledge",
                        "ref": f"knowledge:{state.id}",
                        "quote": f"{state.character_name} {state.state} {state.fact_key}",
                    }
                    for state in states
                ],
            )
        if name == "get_relations":
            if self._story_state is None:
                return ToolExecution(text="故事状态暂不可用。")
            entity = await self.get_entity(work_id, str(args.get("name", "")))
            if entity is None:
                return ToolExecution(text="没有找到该实体。")
            relations = await self._story_state.list_relations(work_id, entity.id)
            if not relations:
                return ToolExecution(text="没有找到该实体的关系。")
            entities = await self._memory_repository.list_entities(work_id)
            names = {item.id: item.name for item in entities}
            lines = [
                f"{names.get(relation.from_entity_id, relation.from_entity_id)} -> "
                f"{names.get(relation.to_entity_id, relation.to_entity_id)}"
                f"（{relation.relation_type}）"
                for relation in relations
            ]
            return ToolExecution(
                text="\n".join(lines),
                citations=[
                    {
                        "source": "entity_relation",
                        "ref": f"entity_relation:{relation.id}",
                        "quote": relation.relation_type,
                    }
                    for relation in relations
                ],
            )
        if name == "search_library":
            if self._library is None:
                return ToolExecution(text="资料库暂不可用。")
            query = str(args.get("query", "")).strip()
            if not query:
                return ToolExecution(text="请提供检索词。")
            limit = max(1, min(int(args.get("limit", 5)), 10))
            hits = await self._library.search(query, limit=limit, work_id=work_id)
            if not hits:
                return ToolExecution(text="资料库没有匹配内容。")
            return ToolExecution(
                text="\n\n".join(str(hit.get("text", "")) for hit in hits),
                citations=[
                    {
                        "source": "library",
                        "ref": f"library:{hit.get('document_id')}:{hit.get('chunk_index')}",
                        "quote": str(hit.get("text", ""))[:200],
                    }
                    for hit in hits
                ],
            )
        if name == "get_timeline":
            if self._story_state is None:
                return ToolExecution(text="故事状态暂不可用。")
            limit = max(1, min(int(args.get("limit", 20)), 50))
            timeline = (await self._story_state.list_timeline(work_id))[:limit]
            if not timeline:
                return ToolExecution(text="没有时间线事件。")
            return ToolExecution(
                text="\n".join(
                    f"{event.event_time or '未知时间'}：{event.description}" for event in timeline
                ),
                citations=[
                    {
                        "source": "timeline",
                        "ref": f"timeline:{event.id}",
                        "quote": event.description[:200],
                    }
                    for event in timeline
                ],
            )
        if name == "get_summary":
            if self._story_state is None:
                return ToolExecution(text="故事状态暂不可用。")
            chapter_id = str(args.get("chapter_id", "")).strip()
            try:
                summary = await self._story_state.get_summary(UUID(chapter_id))
            except Exception as exc:
                return ToolExecution(text=f"没有找到摘要：{exc}")
            return ToolExecution(
                text=summary.content,
                citations=[
                    {
                        "source": "summary",
                        "ref": f"summary:{summary.id}",
                        "quote": summary.content[:200],
                    }
                ],
            )
        if name == "list_foreshadows":
            if self._story_state is None:
                return ToolExecution(text="故事状态暂不可用。")
            items = await self._story_state.list_foreshadows(work_id)
            if not items:
                return ToolExecution(text="没有记录伏笔。")
            return ToolExecution(
                text="\n".join(f"{item.status}：{item.description}" for item in items),
                citations=[
                    {
                        "source": "foreshadow",
                        "ref": f"foreshadow:{item.id}",
                        "quote": item.description[:200],
                    }
                    for item in items
                ],
            )
        if name == "get_story_events":
            if self._story_state is None:
                return ToolExecution(text="故事状态暂不可用。")
            from_chapter = args.get("from_chapter")
            to_chapter = args.get("to_chapter")
            events = await self._story_state.list_story_events(
                work_id,
                from_chapter=int(from_chapter) if from_chapter is not None else None,
                to_chapter=int(to_chapter) if to_chapter is not None else None,
            )
            events = events[:20]
            if not events:
                return ToolExecution(text="该区间没有故事事件。")
            text = "\n".join(f"第 {event.chapter_number} 章：{event.summary}" for event in events)
            return ToolExecution(
                text=text,
                citations=[
                    {
                        "source": "story_event",
                        "ref": f"story_event:{event.id}",
                        "quote": event.summary[:200],
                    }
                    for event in events
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
