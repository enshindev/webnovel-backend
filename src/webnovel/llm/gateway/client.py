from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass

import structlog

from webnovel.kernel.ports.llm import ModelClient, ModelEvent, ModelRequest
from webnovel.llm.gateway.errors import GatewayError

logger = structlog.get_logger(__name__)


@dataclass(frozen=True, slots=True)
class ProviderTarget:
    name: str
    client: ModelClient
    max_retries: int = 2
    retry_backoff_seconds: float = 0.5


class RoutedModelClient:
    """按顺序尝试 provider；只对可重试错误降级。"""

    def __init__(self, targets: Sequence[ProviderTarget]) -> None:
        if not targets:
            raise ValueError("at least one provider is required")
        self._targets = list(targets)

    async def complete(self, request: ModelRequest) -> str:
        last_error: GatewayError | None = None
        for target in self._targets:
            for attempt in range(target.max_retries + 1):
                try:
                    return await target.client.complete(request)
                except GatewayError as exc:
                    last_error = exc
                    logger.warning(
                        "gateway.provider_error",
                        provider=target.name,
                        attempt=attempt + 1,
                        error_code=exc.code,
                        retryable=exc.retryable,
                    )
                    if not exc.retryable:
                        raise
                    if attempt >= target.max_retries:
                        break
                    if target.retry_backoff_seconds:
                        delay = min(target.retry_backoff_seconds * (2**attempt), 10.0)
                        await asyncio.sleep(delay)
        if last_error is not None:
            raise last_error
        raise RuntimeError("no provider attempted")

    async def stream(self, request: ModelRequest) -> AsyncIterator[ModelEvent]:
        last_error: GatewayError | None = None
        for target in self._targets:
            emitted = False
            for attempt in range(target.max_retries + 1):
                try:
                    async for event in target.client.stream(request):
                        emitted = True
                        yield event
                    return
                except GatewayError as exc:
                    last_error = exc
                    logger.warning(
                        "gateway.provider_error",
                        provider=target.name,
                        attempt=attempt + 1,
                        error_code=exc.code,
                        retryable=exc.retryable,
                        emitted=emitted,
                    )
                    if emitted or not exc.retryable:
                        raise
                    if attempt >= target.max_retries:
                        break
                    if target.retry_backoff_seconds:
                        delay = min(target.retry_backoff_seconds * (2**attempt), 10.0)
                        await asyncio.sleep(delay)
        if last_error is not None:
            raise last_error
        raise RuntimeError("no provider attempted")
