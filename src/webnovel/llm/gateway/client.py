from __future__ import annotations

from collections.abc import AsyncIterator, Mapping

from webnovel.kernel.ports.llm import ModelClient, ModelEvent, ModelRequest


class GatewayClient:
    """按 provider 名称选择 adapter 的门面；S1 先支持单 provider。"""

    def __init__(self, providers: Mapping[str, ModelClient], default: str) -> None:
        self._providers = dict(providers)
        self._default = default

    def _pick(self, name: str | None = None) -> ModelClient:
        return self._providers[name or self._default]

    def stream(self, request: ModelRequest) -> AsyncIterator[ModelEvent]:
        return self._pick().stream(request)

    async def complete(self, request: ModelRequest) -> str:
        return await self._pick().complete(request)
