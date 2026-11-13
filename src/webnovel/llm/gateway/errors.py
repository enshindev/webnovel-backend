from __future__ import annotations

from enum import StrEnum

from webnovel.kernel.errors import WebnovelError


class ErrorClass(StrEnum):
    INVALID_REQUEST = "invalid_request"
    AUTH = "auth"
    RATE_LIMIT = "rate_limit"
    QUOTA_EXCEEDED = "quota_exceeded"
    CONTENT_FILTERED = "content_filtered"
    CONTEXT_LENGTH = "context_length"
    TIMEOUT = "timeout"
    UPSTREAM_UNAVAILABLE = "upstream_unavailable"
    CANCELLED = "cancelled"
    INTERNAL = "internal"


RETRYABLE = {
    ErrorClass.TIMEOUT,
    ErrorClass.RATE_LIMIT,
    ErrorClass.UPSTREAM_UNAVAILABLE,
}


class GatewayError(WebnovelError):
    status = 502

    def __init__(
        self, error_class: ErrorClass, message: str, *, code_raw: str | None = None
    ) -> None:
        super().__init__(message, code=f"provider.{error_class.value}")
        self.error_class = error_class
        self.code_raw = code_raw
        self.retryable = error_class in RETRYABLE
