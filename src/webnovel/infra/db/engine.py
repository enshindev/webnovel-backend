from __future__ import annotations

from typing import Any

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from webnovel.infra.config import get_settings
from webnovel.infra.observability import get_tracer

_tracer = get_tracer("webnovel.db")


def _attach_tracing(engine: AsyncEngine) -> None:
    @event.listens_for(engine.sync_engine, "before_cursor_execute")
    def before_cursor_execute(
        conn: Any,
        cursor: Any,
        statement: str,
        parameters: Any,
        context: Any,
        executemany: bool,
    ) -> None:
        _ = (conn, cursor, parameters, executemany)
        span = _tracer.start_span("db.query")
        span.set_attribute("db.statement", statement[:500])
        context._webnovel_span = span

    @event.listens_for(engine.sync_engine, "after_cursor_execute")
    def after_cursor_execute(
        conn: Any,
        cursor: Any,
        statement: str,
        parameters: Any,
        context: Any,
        executemany: bool,
    ) -> None:
        _ = (conn, cursor, statement, parameters, executemany)
        span = getattr(context, "_webnovel_span", None)
        if span is not None:
            span.end()

    @event.listens_for(engine.sync_engine, "handle_error")
    def handle_error(exception_context: Any) -> None:
        span = getattr(exception_context.execution_context, "_webnovel_span", None)
        if span is not None:
            span.record_exception(exception_context.original_exception)
            span.end()


def create_engine() -> AsyncEngine:
    settings = get_settings()
    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    _attach_tracing(engine)
    return engine
