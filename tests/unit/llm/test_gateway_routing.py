from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import httpx
import pytest

from webnovel.kernel.ports.llm import ModelEvent, ModelRequest
from webnovel.llm.gateway.client import ProviderTarget, RoutedModelClient
from webnovel.llm.gateway.errors import ErrorClass, GatewayError
from webnovel.llm.gateway.factory import build_model_client
from webnovel.llm.gateway.providers.openai_compatible import OpenAICompatibleClient
from webnovel.llm.gateway.routing import load_routing


def _request() -> ModelRequest:
    return ModelRequest(model="test", messages=[])


def _retryable() -> GatewayError:
    return GatewayError(ErrorClass.UPSTREAM_UNAVAILABLE, "upstream unavailable")


def _invalid() -> GatewayError:
    return GatewayError(ErrorClass.INVALID_REQUEST, "bad request")


class CompleteStub:
    def __init__(self, outcomes: Sequence[str | Exception]) -> None:
        self.outcomes = list(outcomes)
        self.calls = 0

    async def complete(self, request: ModelRequest) -> str:
        self.calls += 1
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    def stream(self, request: ModelRequest) -> AsyncIterator[ModelEvent]:
        raise NotImplementedError


class StreamStub:
    def __init__(self, events: Sequence[ModelEvent], error: Exception | None = None) -> None:
        self.events = list(events)
        self.error = error
        self.calls = 0

    async def complete(self, request: ModelRequest) -> str:
        raise NotImplementedError

    async def stream(self, request: ModelRequest) -> AsyncIterator[ModelEvent]:
        self.calls += 1
        for event in self.events:
            yield event
        if self.error is not None:
            raise self.error


def _target(name: str, client: Any, retries: int = 0) -> ProviderTarget:
    return ProviderTarget(name=name, client=client, max_retries=retries)


async def test_complete_retries_same_provider_before_fallback() -> None:
    primary = CompleteStub([_retryable(), _retryable(), "ok"])
    secondary = CompleteStub(["unused"])
    client = RoutedModelClient(
        [_target("primary", primary, retries=2), _target("secondary", secondary)]
    )

    assert await client.complete(_request()) == "ok"
    assert primary.calls == 3
    assert secondary.calls == 0


async def test_complete_falls_back_after_retries_are_exhausted() -> None:
    primary = CompleteStub([_retryable(), _retryable()])
    secondary = CompleteStub(["ok"])
    client = RoutedModelClient(
        [_target("primary", primary, retries=1), _target("secondary", secondary)]
    )

    assert await client.complete(_request()) == "ok"
    assert primary.calls == 2
    assert secondary.calls == 1


async def test_complete_does_not_fallback_on_non_retryable_error() -> None:
    primary = CompleteStub([_invalid()])
    secondary = CompleteStub(["unused"])
    client = RoutedModelClient([_target("primary", primary), _target("secondary", secondary)])

    with pytest.raises(GatewayError):
        await client.complete(_request())
    assert secondary.calls == 0


async def test_stream_falls_back_before_first_event() -> None:
    primary = StreamStub([], _retryable())
    secondary = StreamStub(
        [
            ModelEvent(type="delta", text="hello"),
            ModelEvent(type="done"),
        ]
    )
    client = RoutedModelClient([_target("primary", primary), _target("secondary", secondary)])

    events = [event async for event in client.stream(_request())]

    assert [event.type for event in events] == ["delta", "done"]
    assert primary.calls == 1
    assert secondary.calls == 1


async def test_stream_does_not_fallback_after_output_started() -> None:
    primary = StreamStub([ModelEvent(type="delta", text="hello")], _retryable())
    secondary = StreamStub([ModelEvent(type="done")])
    client = RoutedModelClient([_target("primary", primary), _target("secondary", secondary)])

    with pytest.raises(GatewayError):
        [event async for event in client.stream(_request())]
    assert secondary.calls == 0


def test_routing_config_expands_variables(tmp_path: Path) -> None:
    config = tmp_path / "routing.yaml"
    config.write_text(
        """
profiles:
  generation:
    providers:
      - name: primary
        base_url: ${BASE_URL}
        api_key: ${API_KEY}
        model: ${MODEL}
""",
        encoding="utf-8",
    )

    routing = load_routing(
        config,
        {"BASE_URL": "http://model", "API_KEY": "secret", "MODEL": "model-a"},
    )

    provider = routing.profiles["generation"].providers[0]
    assert provider.base_url == "http://model"
    assert provider.api_key == "secret"
    assert provider.model == "model-a"


def test_factory_uses_routing_profile(tmp_path: Path) -> None:
    config = tmp_path / "routing.yaml"
    config.write_text(
        """
profiles:
  generation:
    providers:
      - name: primary
        base_url: http://model
        model: model-a
        max_retries: 3
""",
        encoding="utf-8",
    )
    settings = SimpleNamespace(
        llm_provider="openai-compatible",
        routing_config_path=config,
        llm_base_url="",
        llm_api_key="",
        llm_model="",
    )

    client = build_model_client(settings)  # type: ignore[arg-type]

    assert isinstance(client, RoutedModelClient)


def test_factory_falls_back_to_single_provider_without_routing(tmp_path: Path) -> None:
    settings = SimpleNamespace(
        llm_provider="openai-compatible",
        routing_config_path=tmp_path / "missing.yaml",
        llm_base_url="http://model",
        llm_api_key="secret",
        llm_model="model-a",
        llm_timeout_seconds=10.0,
    )

    client = build_model_client(settings)  # type: ignore[arg-type]

    assert isinstance(client, OpenAICompatibleClient)


async def test_provider_connect_error_becomes_retryable_gateway_error(
    monkeypatch: Any,
) -> None:
    client = OpenAICompatibleClient(base_url="http://test", api_key="", model="model-a")

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    def fake_client() -> httpx.AsyncClient:
        return httpx.AsyncClient(base_url="http://test", transport=httpx.MockTransport(handler))

    monkeypatch.setattr(client, "_client", fake_client)

    with pytest.raises(GatewayError) as exc:
        await client.complete(_request())

    assert exc.value.error_class is ErrorClass.UPSTREAM_UNAVAILABLE
    assert exc.value.retryable is True


async def test_provider_stream_connect_error_becomes_retryable_gateway_error(
    monkeypatch: Any,
) -> None:
    client = OpenAICompatibleClient(base_url="http://test", api_key="", model="model-a")

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    def fake_client() -> httpx.AsyncClient:
        return httpx.AsyncClient(base_url="http://test", transport=httpx.MockTransport(handler))

    monkeypatch.setattr(client, "_client", fake_client)

    with pytest.raises(GatewayError) as exc:
        [event async for event in client.stream(_request())]

    assert exc.value.error_class is ErrorClass.UPSTREAM_UNAVAILABLE
    assert exc.value.retryable is True
