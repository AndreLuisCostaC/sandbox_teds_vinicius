from __future__ import annotations

import logging
import os
import time
import uuid

import structlog
from fastapi import APIRouter, Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.models.user import User
from app.ratelimit import limiter
from app.routers.auth import router as auth_router
from app.routers.products import router as products_router
from app.security import get_current_user, get_current_user_with_role


def _configure_logging() -> structlog.stdlib.BoundLogger:
    timestamper = structlog.processors.TimeStamper(fmt="iso", utc=True)

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_log_level,
            timestamper,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    return structlog.get_logger("app")


logger = _configure_logging()


def _get_cors_origins() -> list[str]:
    origins = os.getenv("CORS_ORIGINS", "")
    return [origin.strip() for origin in origins.split(",") if origin.strip()]


app = FastAPI(title="Prodgrade API", version="0.1.0")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_get_cors_origins() or ["http://localhost:3000", "http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

api_router = APIRouter(prefix="/api/v1")


@api_router.get("/health")
async def api_health() -> dict[str, str]:
    return {"status": "ok"}


@api_router.get("/me")
async def read_current_user(current_user: User = Depends(get_current_user)) -> dict[str, object]:
    return {
        "id": current_user.id,
        "email": current_user.email,
        "full_name": current_user.full_name,
        "is_active": current_user.is_active,
        "role_id": current_user.role_id,
    }


@api_router.get("/admin/ping")
async def admin_ping(current_user: User = Depends(get_current_user_with_role("admin"))) -> dict[str, str]:
    return {"status": "ok", "message": f"admin access granted for user {current_user.id}"}


@app.get("/health")
async def root_health() -> dict[str, str]:
    # Kept for compose healthchecks that call /health directly.
    return {"status": "ok"}


@app.middleware("http")
async def log_request_response(request: Request, call_next):
    request_id = request.headers.get("x-request-id", str(uuid.uuid4()))
    start = time.perf_counter()

    try:
        response = await call_next(request)
    finally:
        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        logger.info(
            "http_request",
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            query=str(request.url.query),
            status_code=getattr(locals().get("response", None), "status_code", 500),
            duration_ms=duration_ms,
            client_ip=request.client.host if request.client else None,
        )

    response.headers["x-request-id"] = request_id
    return response


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    request_id = str(uuid.uuid4())
    logger.exception(
        "unhandled_exception",
        request_id=request_id,
        method=request.method,
        path=request.url.path,
    )

    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
            "request_id": request_id,
        },
    )


api_router.include_router(auth_router)
api_router.include_router(products_router)
app.include_router(api_router)

