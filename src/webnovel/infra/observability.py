from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from typing import cast

from fastapi import FastAPI
from opentelemetry import metrics, trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.prometheus import PrometheusMetricReader
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace import SpanKind, Status, StatusCode
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from webnovel.infra.config import get_settings

_configured = False
_REQUEST_COUNT = Counter(
    "webnovel_http_requests_total", "HTTP requests", ["method", "path", "status"]
)
_REQUEST_LATENCY = Histogram(
    "webnovel_http_request_duration_seconds", "HTTP request duration", ["method", "path"]
)
_MODEL_CALLS = Counter(
    "webnovel_model_calls_total", "Model calls", ["operation", "model", "status"]
)
_MODEL_LATENCY = Histogram(
    "webnovel_model_call_duration_seconds", "Model call duration", ["operation", "model"]
)
_QUEUE_BACKLOG = Gauge("webnovel_queue_backlog", "Queued jobs", ["queue"])


def get_tracer(name: str = "webnovel") -> trace.Tracer:
    return trace.get_tracer(name)


def get_meter(name: str = "webnovel") -> metrics.Meter:
    return metrics.get_meter(name)


def configure_observability() -> None:
    global _configured
    if _configured:
        return
    settings = get_settings()
    resource = Resource.create(
        {"service.name": "webnovel-backend", "deployment.environment": settings.env}
    )
    provider = TracerProvider(resource=resource)
    if settings.otel_exporter_otlp_endpoint:
        provider.add_span_processor(
            BatchSpanProcessor(OTLPSpanExporter(endpoint=settings.otel_exporter_otlp_endpoint))
        )
    trace.set_tracer_provider(provider)
    metrics.set_meter_provider(
        MeterProvider(resource=resource, metric_readers=[PrometheusMetricReader()])
    )
    _configured = True


class HttpMetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        started = time.monotonic()
        response = await call_next(request)
        path = request.url.path
        _REQUEST_COUNT.labels(request.method, path, str(response.status_code)).inc()
        _REQUEST_LATENCY.labels(request.method, path).observe(time.monotonic() - started)
        return response


class TracingMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        tracer = get_tracer("webnovel.http")
        with tracer.start_as_current_span(
            f"{request.method} {request.url.path}", kind=SpanKind.SERVER
        ) as span:
            span.set_attribute("http.method", request.method)
            span.set_attribute("http.target", request.url.path)
            try:
                response = await call_next(request)
            except Exception as exc:
                span.record_exception(exc)
                span.set_status(Status(StatusCode.ERROR))
                raise
            span.set_attribute("http.status_code", response.status_code)
            if response.status_code >= 500:
                span.set_status(Status(StatusCode.ERROR))
            return response


def observe_model_call(operation: str, model: str, status: str, seconds: float) -> None:
    _MODEL_CALLS.labels(operation, model, status).inc()
    _MODEL_LATENCY.labels(operation, model).observe(seconds)


def instrument_app(app: FastAPI) -> None:
    app.add_middleware(HttpMetricsMiddleware)
    app.add_middleware(TracingMiddleware)


async def refresh_queue_backlog() -> None:
    from webnovel.infra.redis import create_redis

    client = create_redis()
    try:
        length = await asyncio.wait_for(cast(Awaitable[int], client.llen("arq:queue")), timeout=0.5)
        _QUEUE_BACKLOG.labels("arq").set(int(length))
    except Exception:
        return
    finally:
        await client.aclose()


async def metrics_response() -> Response:
    configure_observability()
    await refresh_queue_backlog()
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
