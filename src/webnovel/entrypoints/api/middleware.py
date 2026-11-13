from __future__ import annotations

import time
from collections import defaultdict, deque
from collections.abc import Awaitable, Callable
from uuid import uuid4

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request_id = request.headers.get("X-Request-ID") or uuid4().hex
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


class AuthMiddleware(BaseHTTPMiddleware):
    """单用户可选 Bearer Token；默认空 token 时不启用。"""

    def __init__(self, app: object, token: str = "") -> None:
        super().__init__(app)  # type: ignore[arg-type]
        self._token = token

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        token = self._token
        if not token or request.url.path in {"/health", "/docs", "/openapi.json"}:
            return await call_next(request)
        if not request.url.path.startswith("/api/"):
            return await call_next(request)
        if request.headers.get("Authorization") != f"Bearer {token}":
            return JSONResponse(
                status_code=401,
                content={"detail": "invalid or missing API token", "code": "auth.invalid"},
                headers={"WWW-Authenticate": "Bearer"},
            )
        return await call_next(request)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """单进程滑动窗口限流；单用户自托管足够，集群部署应换 Redis 实现。"""

    def __init__(self, app: object, limit_per_minute: int) -> None:
        super().__init__(app)  # type: ignore[arg-type]
        self._limit = limit_per_minute
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        if self._limit <= 0 or not request.url.path.startswith("/api/"):
            return await call_next(request)
        key = request.headers.get("X-API-Client") or (
            request.client.host if request.client else "unknown"
        )
        now = time.monotonic()
        hits = self._hits[key]
        while hits and now - hits[0] > 60:
            hits.popleft()
        if len(hits) >= self._limit:
            return JSONResponse(
                status_code=429,
                content={"detail": "rate limit exceeded", "code": "rate_limit.exceeded"},
                headers={"Retry-After": "60"},
            )
        hits.append(now)
        return await call_next(request)
