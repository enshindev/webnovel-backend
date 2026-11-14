from __future__ import annotations

import logging

import structlog
from structlog.typing import Processor

from webnovel.infra.config import Settings

_configured = False


def configure_logging(settings: Settings) -> None:
    """配置一次 structlog；开发环境用可读格式，生产可切 JSON。"""
    global _configured
    if _configured:
        return
    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    renderer = (
        structlog.processors.JSONRenderer()
        if settings.log_json
        else structlog.dev.ConsoleRenderer()
    )
    processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
    ]
    if settings.log_json:
        processors.append(structlog.processors.format_exc_info)
    processors.append(renderer)
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
    logging.basicConfig(level=level, format="%(message)s")
    _configured = True
