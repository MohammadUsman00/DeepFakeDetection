from __future__ import annotations

import time
import uuid
import os
from typing import Callable

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .utils.errors import AppError, ErrorCode
from .utils.logging import configure_logging, get_logger
from .db.init_db import init_db
from .api.routes.artifacts import router as artifacts_router
from .api.routes.analyze import router as analyze_router
from .api.routes.health import router as health_router
from .api.routes.results import router as results_router
from .ml.inference.model_loader import warmup_model


def create_app() -> FastAPI:
    configure_logging()
    log = get_logger("app")

    app = FastAPI(title="Deepfake Detection Backend", version="0.0.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["x-request-id"],
    )
    app.include_router(health_router)
    app.include_router(artifacts_router)
    app.include_router(analyze_router)
    app.include_router(results_router)

    @app.on_event("startup")
    async def _startup() -> None:
        init_db()
        warmup_model()
        log.info(
            "startup",
            extra={
                "stage": "startup",
                "model_id": settings.inference.model_id,
                "batch_size": settings.inference.batch_size,
                "max_frames": settings.video.max_frames,
                "effective_max_frames": settings.effective_max_frames,
                "config": settings.summary(),
            },
        )

    @app.middleware("http")
    async def request_context_middleware(request: Request, call_next: Callable):
        request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
        request.state.request_id = request_id
        start = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        response.headers["x-request-id"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
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

    return app


app = create_app()

