from __future__ import annotations


class WebnovelError(Exception):
    """所有领域异常的基类；HTTP 层统一映射为 RFC 9457 Problem。"""

    code: str = "internal.error"
    status: int = 500
    retryable: bool = False

    def __init__(self, detail: str = "", *, code: str | None = None) -> None:
        super().__init__(detail)
        self.detail = detail
        if code is not None:
            self.code = code


class NotFoundError(WebnovelError):
    code = "resource.not_found"
    status = 404


class ConflictError(WebnovelError):
    code = "resource.conflict"
    status = 409


class ValidationError(WebnovelError):
    code = "validation.failed"
    status = 422
