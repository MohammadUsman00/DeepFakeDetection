from __future__ import annotations

import time
import uuid
import os
from typing import Callable

from pathlib import Path

from alembic import command
from alembic.config import Config
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

import socketio

from .config import settings
from .utils.errors import AppError, ErrorCode
from .utils.logging import configure_logging, get_logger
from .db.init_db import init_db
from .api.routes.artifacts import router as artifacts_router
from .api.routes.analyze import router as analyze_router
from .api.routes.auth import router as auth_router
from .api.routes.health import router as health_router
from .api.routes.jobs import router as jobs_router
from .api.routes.results import router as results_router
from .ml.inference.model_loader import warmup_model


def create_app() -> FastAPI:
    configure_logging()
    log = get_logger("app")

    # Initialize Socket.io with Redis manager for Celery-to-API communication
    mgr = socketio.AsyncRedisManager(os.getenv("CELERY_BROKER_URL", "redis://redis:6379/0"))
    sio = socketio.AsyncServer(
        async_mode="asgi",
        cors_allowed_origins=list(settings.cors_allowed_origins),
        client_manager=mgr,
    )
    
    app = FastAPI(
        title="DeepShield AI Backend",
        version="1.0.0",
        description="REST endpoints are mounted under /api (e.g. /api/docs for OpenAPI).",
    )
    
    # Use standard path internal to the backend; Nginx will proxy /api/socket.io/ here.
    app_with_sio = socketio.ASGIApp(sio, app, socketio_path="/socket.io")
    app.state.sio = sio

    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_allowed_origins),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["x-request-id"],
    )
    
    # Prefix routers for consistency with Nginx configuration
    app.include_router(results_router, prefix="/api")
    app.include_router(analyze_router, prefix="/api")
    app.include_router(artifacts_router, prefix="/api")
    app.include_router(health_router, prefix="/api")
    app.include_router(auth_router, prefix="/api")
    app.include_router(jobs_router, prefix="/api")

    if os.getenv("ENABLE_PROMETHEUS_METRICS", "true").lower() in ("1", "true", "yes"):
        Instrumentator().instrument(app).expose(app, endpoint="/api/metrics", include_in_schema=False)

    @app.on_event("startup")
    async def _startup() -> None:
        if os.getenv("RUN_DB_MIGRATIONS_ON_STARTUP", "").lower() in ("1", "true", "yes"):
            backend_root = Path(__file__).resolve().parent.parent
            alembic_ini = backend_root / "alembic.ini"
            command.upgrade(Config(str(alembic_ini)), "head")
        else:
            init_db()
        # Warmup is now part of the worker process to keep API server light
        log.info("startup", extra={"stage": "api_boot"})

    @sio.event
    async def connect(sid, environ):
        log.info("socket_connect", extra={"sid": sid})

    @sio.event
    async def disconnect(sid):
        log.info("socket_disconnect", extra={"sid": sid})

    @app.middleware("http")
    async def request_context_middleware(request: Request, call_next: Callable):
        request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
        request.state.request_id = request_id
        start = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        response.headers["x-request-id"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        get_logger("request", request_id=request_id).info(
            "request",
            extra={
                "method": request.method,
                "path": str(request.url.path),
                "status_code": response.status_code,
                "elapsed_ms": elapsed_ms,
            },
        )
        return response

    # Lightweight, optional in-memory rate limiting.
    # Env: RATE_LIMIT_RPS (0 disables), RATE_LIMIT_BURST (default 30)
    rate_rps = float(os.getenv("RATE_LIMIT_RPS", "0") or "0")
    burst = int(os.getenv("RATE_LIMIT_BURST", "30") or "30")
    if rate_rps > 0:
        app.state._rl = {"events": {}}  # type: ignore[attr-defined]

        @app.middleware("http")
        async def rate_limit_middleware(request: Request, call_next: Callable):
            # Middleware order isn't guaranteed; ensure a request_id exists.
            request_id = getattr(request.state, "request_id", None) or request.headers.get("x-request-id") or str(uuid.uuid4())
            request.state.request_id = request_id
            ip = request.client.host if request.client else "unknown"
            now = time.time()
            window = 1.0
            events = app.state._rl["events"]  # type: ignore[index]
            q = events.get(ip, [])
            q = [t for t in q if now - t < window]
            limit = max(1, int(rate_rps * window) + burst)
            if len(q) >= limit:
                get_logger("rate_limit", request_id=request_id).warning("rate_limited", extra={"ip": ip})
                return JSONResponse(status_code=429, content={"request_id": request_id, "error": {"error_code": "RATE_LIMITED", "message": "Too many requests"}})
            q.append(now)
            events[ip] = q
            return await call_next(request)

    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        request_id = getattr(request.state, "request_id", "-")
        log_err = get_logger(
            "app.error",
            request_id=request_id,
            job_id=exc.job_id or "-",
            stage=(exc.stage.value if exc.stage is not None else "-"),
            state="-",
        )
        log_err.warning("app_error", extra={"error_code": exc.code.value})
        return JSONResponse(
            status_code=exc.http_status,
            content={
                "request_id": request_id,
                "error": exc.to_payload(),
            },
            headers={"X-Content-Type-Options": "nosniff"},
        )

    @app.exception_handler(Exception)
    async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
        request_id = getattr(request.state, "request_id", "-")
        log_err = get_logger("app.error", request_id=request_id)
        log_err.exception("unhandled_exception")
        # Avoid leaking internal details in responses.
        generic = AppError(code=ErrorCode.INTERNAL_ERROR, message="Internal server error")
        return JSONResponse(
            status_code=500,
            content={
                "request_id": request_id,
                "error": generic.to_payload(),
            },
            headers={"X-Content-Type-Options": "nosniff"},
        )

    return app_with_sio


app = create_app()

