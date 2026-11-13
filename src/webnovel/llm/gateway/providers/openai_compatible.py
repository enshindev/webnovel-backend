from __future__ import annotations

import json
import time
from collections.abc import AsyncIterator, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import httpx

from webnovel.infra.observability import observe_model_call
from webnovel.kernel.ports.llm import (
    ChatMessage,
    ModelEvent,
    ModelRequest,
    ModelResponse,
    ModelUsage,
    ToolCall,
)
from webnovel.llm.gateway.errors import ErrorClass, GatewayError
from webnovel.llm.telemetry.spans import ai_span


def _payload(request: ModelRequest, *, stream: bool) -> dict[str, Any]:
    messages: list[dict[str, Any]] = []
    for message in request.messages:
        item: dict[str, Any] = {"role": message.role, "content": message.content}
        if message.tool_call_id is not None:
            item["tool_call_id"] = message.tool_call_id
        if message.tool_calls:
            item["tool_calls"] = [
                {
                    "id": call.id,
                    "type": "function",
                    "function": {"name": call.name, "arguments": call.arguments},
                }
                for call in message.tool_calls
            ]
        messages.append(item)
    payload: dict[str, Any] = {
        "model": request.model,
        "messages": messages,
        "temperature": request.temperature,
        "stream": stream,
    }
    if request.max_tokens is not None:
        payload["max_tokens"] = request.max_tokens
    if request.response_format is not None:
        payload["response_format"] = dict(request.response_format)
    if request.tools is not None:
        payload["tools"] = [dict(tool) for tool in request.tools]
    return payload


def _usage(data: Mapping[str, Any]) -> ModelUsage:
    usage = data.get("usage") or {}
    return ModelUsage(
        prompt_tokens=int(usage.get("prompt_tokens", 0)),
        completion_tokens=int(usage.get("completion_tokens", 0)),
        cached_tokens=int((usage.get("prompt_tokens_details") or {}).get("cached_tokens", 0)),
    )


@dataclass
class OpenAICompatibleClient:
    base_url: str
    api_key: str
    model: str
    timeout_seconds: float = 120.0

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=self.base_url.rstrip("/"),
            headers={"Authorization": f"Bearer {self.api_key}"},
            timeout=self.timeout_seconds,
        )

    async def complete_response(self, request: ModelRequest) -> ModelResponse:
        started = time.monotonic()
        status = "error"
        with ai_span("chat.completions", model=request.model, operation="chat"):
            try:
                async with self._client() as client:
                    response = await client.post(
                        "/chat/completions", json=_payload(request, stream=False)
                    )
                    if response.status_code >= 400:
                        raise GatewayError(
                            ErrorClass.UPSTREAM_UNAVAILABLE
                            if response.status_code >= 500
                            else ErrorClass.INVALID_REQUEST,
                            response.text,
                            code_raw=str(response.status_code),
                        )
                    data = response.json()
                status = "success"
            finally:
                observe_model_call("chat", request.model, status, time.monotonic() - started)
        message = data["choices"][0]["message"]
        calls = [
            ToolCall(
                id=str(item["id"]),
                name=str(item["function"]["name"]),
                arguments=str(item["function"]["arguments"]),
            )
            for item in message.get("tool_calls", [])
        ]
        return ModelResponse(
            text=str(message.get("content") or ""),
            tool_calls=calls,
            usage=_usage(data),
        )

    async def complete(self, request: ModelRequest) -> str:
        return (await self.complete_response(request)).text

    async def stream(self, request: ModelRequest) -> AsyncIterator[ModelEvent]:
        started = time.monotonic()
        status = "error"
        try:
            async for event in self._stream(request):
                if event.type == "done":
                    status = "success"
                yield event
        finally:
            observe_model_call("chat", request.model, status, time.monotonic() - started)

    async def _stream(self, request: ModelRequest) -> AsyncIterator[ModelEvent]:
        async with (
            self._client() as client,
            client.stream(
                "POST", "/chat/completions", json=_payload(request, stream=True)
            ) as response,
        ):
            if response.status_code >= 400:
                body = await response.aread()
                raise GatewayError(
                    ErrorClass.UPSTREAM_UNAVAILABLE
                    if response.status_code >= 500
                    else ErrorClass.INVALID_REQUEST,
                    body.decode("utf-8", errors="replace"),
                    code_raw=str(response.status_code),
                )
            final_usage = ModelUsage()
            tool_calls: dict[int, dict[str, str]] = {}
            async for line in response.aiter_lines():
                if not line.startswith("data:"):
                    continue
                raw = line.removeprefix("data:").strip()
                if raw == "[DONE]":
                    break
                chunk = json.loads(raw)
                if chunk.get("usage"):
                    final_usage = _usage(chunk)
                    yield ModelEvent(type="usage", usage=final_usage)
                delta = (chunk.get("choices") or [{}])[0].get("delta") or {}
                for call in delta.get("tool_calls") or []:
                    index = int(call.get("index", 0))
                    current = tool_calls.setdefault(index, {"id": "", "name": "", "arguments": ""})
                    if call.get("id"):
                        current["id"] = str(call["id"])
                    function = call.get("function") or {}
                    if function.get("name"):
                        current["name"] = str(function["name"])
                    if function.get("arguments"):
                        current["arguments"] += str(function["arguments"])
                text = delta.get("content")
                if text:
                    yield ModelEvent(type="delta", text=text)
        if tool_calls:
            yield ModelEvent(
                type="tool_calls",
                tool_calls=[
                    ToolCall(
                        id=item["id"] or f"call-{index}",
                        name=item["name"],
                        arguments=item["arguments"] or "{}",
                    )
                    for index, item in sorted(tool_calls.items())
                ],
            )
        yield ModelEvent(type="done", usage=final_usage)


def client_from_config(config: Any) -> OpenAICompatibleClient:
    return OpenAICompatibleClient(
        base_url=str(config.base_url),
        api_key=str(config.api_key),
        model=str(config.model),
        timeout_seconds=float(config.timeout_seconds),
    )


def as_messages(messages: Sequence[ChatMessage]) -> list[ChatMessage]:
    return list(messages)
