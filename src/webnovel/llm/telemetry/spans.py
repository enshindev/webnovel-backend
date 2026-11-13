from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from opentelemetry.trace import Span

from webnovel.infra.observability import get_tracer

_tracer = get_tracer("webnovel.llm")


@contextmanager
def ai_span(name: str, **attributes: object) -> Iterator[Span]:
    """统一的 gen_ai.* span 入口；具体属性在 S4 接 semconv。"""
    with _tracer.start_as_current_span(name) as span:
        for key, value in attributes.items():
            span.set_attribute(f"gen_ai.{key}", str(value))
        yield span
