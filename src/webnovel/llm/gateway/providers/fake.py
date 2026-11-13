from __future__ import annotations

from collections.abc import AsyncIterator, Sequence

from webnovel.kernel.ports.llm import ModelEvent, ModelRequest, ModelUsage


class FakeReplayClient:
    """测试/回放用：按固定 chunks 产出事件，不访问网络。"""

    def __init__(self, chunks: Sequence[str], *, done_text: str | None = None) -> None:
        self._chunks = list(chunks)
        self._done_text = done_text

    async def complete(self, request: ModelRequest) -> str:
        return self._done_text if self._done_text is not None else "".join(self._chunks)

    async def stream(self, request: ModelRequest) -> AsyncIterator[ModelEvent]:
        for chunk in self._chunks:
            yield ModelEvent(type="delta", text=chunk)
        yield ModelEvent(
            type="done",
            usage=ModelUsage(prompt_tokens=0, completion_tokens=len(self._chunks), estimated=True),
        )
