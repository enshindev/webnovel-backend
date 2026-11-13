from __future__ import annotations

import time
from collections.abc import Sequence

import httpx

from webnovel.infra.observability import observe_model_call
from webnovel.kernel.ports.rerank import Reranker, RerankResult
from webnovel.llm.telemetry.spans import ai_span


class OpenAICompatibleReranker(Reranker):
    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        timeout: float = 30.0,
    ) -> None:
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=timeout,
        )
        self._model = model

    async def rerank(self, query: str, documents: Sequence[str], top_n: int) -> list[RerankResult]:
        if not documents:
            return []
        started = time.monotonic()
        status = "error"
        with ai_span("rerank", model=self._model, operation="rerank"):
            try:
                response = await self._client.post(
                    "/rerank",
                    json={
                        "model": self._model,
                        "query": query,
                        "documents": list(documents),
                        "top_n": max(1, min(top_n, len(documents))),
                    },
                )
                response.raise_for_status()
                status = "success"
                return [
                    RerankResult(index=int(item["index"]), score=float(item["relevance_score"]))
                    for item in response.json().get("results", [])
                ]
            finally:
                observe_model_call("rerank", self._model, status, time.monotonic() - started)

    async def aclose(self) -> None:
        await self._client.aclose()
