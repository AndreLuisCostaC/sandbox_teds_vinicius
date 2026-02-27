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
from app.routers.carts import router as carts_router
from app.routers.inventory import router as inventory_router
from app.routers.orders import router as orders_router
from app.routers.products import router as products_router
from app.routers.search import router as search_router
from app.routers.sync import create_sync_router
from app.routers.webhooks import router as webhooks_router
from app.security import get_current_user, get_current_user_with_role
from app.services.sync_listener import ProductSyncListener
from app.services.sync_processor import ProductSyncProcessor


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
sync_listener = ProductSyncListener()
sync_processor = ProductSyncProcessor()


def _get_cors_origins() -> list[str]:
    origins = os.getenv("CORS_ORIGINS", "")
    return [origin.strip() for origin in origins.split(",") if origin.strip()]


app = FastAPI(title="Prodgrade API", version="0.1.0")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.state.api_rate_limit = {}

app.add_middleware(
    CORSMiddleware,
    allow_origins=_get_cors_origins()
    or ["http://localhost:3000", "http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

api_router = APIRouter(prefix="/api/v1")


@api_router.get("/health")
async def api_health() -> dict[str, str]:
    return {"status": "ok"}


@api_router.get("/me")
async def read_current_user(
    current_user: User = Depends(get_current_user),
) -> dict[str, object]:
    return {
        "id": current_user.id,
        "email": current_user.email,
        "full_name": current_user.full_name,
        "is_active": current_user.is_active,
        "role_id": current_user.role_id,
    }


@api_router.get("/admin/ping")
async def admin_ping(
    current_user: User = Depends(get_current_user_with_role("admin")),
) -> dict[str, str]:
    return {
        "status": "ok",
        "message": f"admin access granted for user {current_user.id}",
    }


@app.get("/health")
async def root_health() -> dict[str, str]:
    # Kept for compose healthchecks that call /health directly.
    return {"status": "ok"}


@app.middleware("http")
async def log_request_response(request: Request, call_next):
    path = request.url.path
    client_ip = request.client.host if request.client else "unknown"
    now = int(time.time())
    if path.startswith("/api/v1"):
        minute_window = now // 60
        state = app.state.api_rate_limit
        previous = state.get(client_ip)
        if previous is None or previous["window"] != minute_window:
            state[client_ip] = {"window": minute_window, "count": 1}
        else:
            previous["count"] += 1
            limit = int(os.getenv("RATE_LIMIT_PER_MINUTE", "60"))
            if previous["count"] > limit:
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Rate limit exceeded"},
                )

    if request.method in {"POST", "PATCH", "PUT", "DELETE"} and path.startswith("/api/v1"):
        exempt_paths = {
            "/api/v1/auth/login",
            "/api/v1/auth/register",
            "/api/v1/health",
        }
        if path not in exempt_paths:
            csrf_cookie = request.cookies.get("csrf_token")
            if csrf_cookie:
                csrf_header = request.headers.get("x-csrf-token")
                if not csrf_header or csrf_header != csrf_cookie:
                    return JSONResponse(
                        status_code=403,
                        content={"detail": "CSRF validation failed"},
                    )

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
            status_code=getattr(
                locals().get("response", None),
                "status_code",
                500,
            ),
            duration_ms=duration_ms,
            client_ip=client_ip,
        )

    response.headers["x-content-type-options"] = "nosniff"
    response.headers["x-frame-options"] = "DENY"
    response.headers["x-xss-protection"] = "1; mode=block"
    response.headers["referrer-policy"] = "strict-origin-when-cross-origin"
    response.headers["content-security-policy"] = (
        "default-src 'self'; frame-ancestors 'none'; base-uri 'self';"
    )
    response.headers["strict-transport-security"] = "max-age=31536000; includeSubDomains"
    response.headers["x-request-id"] = request_id
    return response


@app.exception_handler(Exception)
async def unhandled_exception_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
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


@app.on_event("startup")
async def startup_sync_listener() -> None:
    await sync_listener.start()
    await sync_processor.start()


@app.on_event("shutdown")
async def shutdown_sync_listener() -> None:
    await sync_listener.stop()
    await sync_processor.stop()


api_router.include_router(auth_router)
api_router.include_router(carts_router)
api_router.include_router(inventory_router)
api_router.include_router(orders_router)
api_router.include_router(products_router)
api_router.include_router(search_router)
api_router.include_router(create_sync_router(sync_processor))
app.include_router(api_router)
app.include_router(webhooks_router)
