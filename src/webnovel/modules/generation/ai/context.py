from __future__ import annotations

from webnovel.llm.context.builder import ContextBuilder
from webnovel.llm.context.ports import ContextSegment, ContextSource


class GenerationContextAssembler:
    """业务组装：选择本章设定、伏笔、摘要、最近原文，交给 ContextBuilder 渲染。"""

    def __init__(self, source: ContextSource, builder: ContextBuilder) -> None:
        self._source = source
        self._builder = builder

    async def assemble(self, *, work_id: str, chapter_id: str, task: str) -> list[ContextSegment]:
        """返回已按业务优先级选好的上下文片段；预算/渲染由 ContextBuilder 负责。"""
        chunks = await self._source.fetch(work_id, f"{chapter_id}\n{task}", limit=12)
        return [
            ContextSegment(
                name=f"memory-{index}",
                source=chunk.source,
                ref=chunk.ref,
                text=chunk.text,
                priority=100 + index,
                tokens=chunk.tokens,
            )
            for index, chunk in enumerate(chunks)
        ]
