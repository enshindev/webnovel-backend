from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from webnovel.entrypoints.api.middleware import (
    AuthMiddleware,
    RateLimitMiddleware,
    RequestIdMiddleware,
)
from webnovel.infra.config import get_settings
from webnovel.infra.logging import configure_logging
from webnovel.infra.observability import configure_observability, instrument_app, metrics_response
from webnovel.kernel.errors import WebnovelError
from webnovel.modules.agent.http import router as agent_router
from webnovel.modules.analysis.http import router as analysis_router
from webnovel.modules.assistant.http import router as assistant_router
from webnovel.modules.audit.http import router as audit_router
from webnovel.modules.chapters_versions.http import router as chapters_router
from webnovel.modules.export.http import router as export_router
from webnovel.modules.generation.http import router as generation_router
from webnovel.modules.graphrag.http import router as graphrag_router
from webnovel.modules.library.http import router as library_router
from webnovel.modules.memory.http import router as memory_router
from webnovel.modules.multimodal.http import router as multimodal_router
from webnovel.modules.prompts.http import router as prompts_router
from webnovel.modules.quality.http import router as quality_router
from webnovel.modules.settings.http import router as settings_router
from webnovel.modules.style.http import router as style_router
from webnovel.modules.usage.http import router as usage_router
from webnovel.modules.volumes.http import router as volumes_router
from webnovel.modules.workflow.http import router as workflow_router
from webnovel.modules.works.http import router as works_router

API_PREFIX = "/api/v1"


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings)
    configure_observability()
    app = FastAPI(
        title="Webnovel Backend",
        version="0.1.0",
        description="AI 网文创作平台后端（单用户自托管）",
    )
    app.add_middleware(RequestIdMiddleware)
    if settings.api_token:
        app.add_middleware(AuthMiddleware, token=settings.api_token)
    if settings.rate_limit_per_minute > 0:
        app.add_middleware(RateLimitMiddleware, limit_per_minute=settings.rate_limit_per_minute)
    instrument_app(app)
    origins = [origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()]
    if origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_credentials=settings.cors_allow_credentials,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    @app.exception_handler(WebnovelError)
    async def handle_webnovel_error(request: Request, exc: WebnovelError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status,
            media_type="application/problem+json",
            content={
                "type": f"https://errors.local/{exc.code}",
                "title": exc.code,
                "status": exc.status,
                "code": exc.code,
                "detail": exc.detail,
                "request_id": getattr(request.state, "request_id", None),
                "retryable": exc.retryable,
            },
        )

    @app.get("/health", tags=["health"])
    async def health() -> dict[str, str]:
        return {"status": "ok", "version": "0.1.0"}

    @app.get("/metrics", include_in_schema=False)
    async def metrics() -> Response:
        return await metrics_response()

    app.include_router(works_router, prefix=API_PREFIX)
    app.include_router(agent_router, prefix=API_PREFIX)
    app.include_router(analysis_router, prefix=API_PREFIX)
    app.include_router(assistant_router, prefix=API_PREFIX)
    app.include_router(audit_router, prefix=API_PREFIX)
    app.include_router(chapters_router, prefix=API_PREFIX)
    app.include_router(generation_router, prefix=API_PREFIX)
    app.include_router(settings_router, prefix=API_PREFIX)
    app.include_router(style_router, prefix=API_PREFIX)
    app.include_router(memory_router, prefix=API_PREFIX)
    app.include_router(multimodal_router, prefix=API_PREFIX)
    app.include_router(prompts_router, prefix=API_PREFIX)
    app.include_router(quality_router, prefix=API_PREFIX)
    app.include_router(export_router, prefix=API_PREFIX)
    app.include_router(graphrag_router, prefix=API_PREFIX)
    app.include_router(library_router, prefix=API_PREFIX)
    app.include_router(usage_router, prefix=API_PREFIX)
    app.include_router(volumes_router, prefix=API_PREFIX)
    app.include_router(workflow_router, prefix=API_PREFIX)
    app.mount("/app", StaticFiles(directory="apps/web", html=True), name="web")
    return app


app = create_app()
