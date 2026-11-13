from __future__ import annotations

import time
from collections.abc import Sequence

import httpx

from webnovel.infra.observability import observe_model_call
from webnovel.kernel.ports.embeddings import EmbeddingClient
from webnovel.llm.telemetry.spans import ai_span


class OpenAICompatibleEmbeddingClient(EmbeddingClient):
    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        dimensions: int = 1024,
        timeout: float = 30.0,
    ) -> None:
        self._model = model
        self._dimensions = dimensions
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=timeout,
        )

    @property
    def dimensions(self) -> int:
        return self._dimensions

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            return []
        started = time.monotonic()
        status = "error"
        with ai_span("embeddings", model=self._model, operation="embedding"):
            try:
                response = await self._client.post(
                    "/embeddings",
                    json={
                        "model": self._model,
                        "input": list(texts),
                        "dimensions": self._dimensions,
                    },
                )
                response.raise_for_status()
                payload = response.json()
                data = sorted(payload.get("data", []), key=lambda item: item.get("index", 0))
                vectors = [list(item["embedding"]) for item in data]
                if len(vectors) != len(texts):
                    raise ValueError("embedding response count mismatch")
                for vector in vectors:
                    if len(vector) != self._dimensions:
                        raise ValueError(
                            f"embedding dimension mismatch: expected {self._dimensions}, "
                            f"got {len(vector)}"
                        )
                status = "success"
                return vectors
            finally:
                observe_model_call("embedding", self._model, status, time.monotonic() - started)

    async def aclose(self) -> None:
        await self._client.aclose()
