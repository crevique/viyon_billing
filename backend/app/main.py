"""Main FastAPI application entry point for VIYON Billing System."""

import app.core.dns_fallback  # noqa: F401 - Must be first to ensure DB hostname resolution works reliably
import logging
import sys
import time
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.v1.router import api_router
from app.core.config import settings

# ------------------------------------------------------------------------------
# Structured Logging Setup
# ------------------------------------------------------------------------------
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("viyon_billing")


# ------------------------------------------------------------------------------
# Application Lifespan Events
# ------------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Execute startup and shutdown tasks."""
    logger.info("=" * 60)
    logger.info(f"Starting {settings.PROJECT_NAME} v{settings.VERSION}")
    logger.info(f"Environment: {settings.ENVIRONMENT} | Debug: {settings.DEBUG}")
    logger.info(f"API Docs available at: {settings.DOCS_URL}")
    logger.info("=" * 60)
    yield
    logger.info("Shutting down VIYON Billing System backend cleanly.")


# ------------------------------------------------------------------------------
# FastAPI App Factory
# ------------------------------------------------------------------------------
app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description=settings.DESCRIPTION,
    docs_url=settings.DOCS_URL,
    redoc_url=settings.REDOC_URL,
    openapi_url=settings.OPENAPI_URL,
    lifespan=lifespan,
)


# ------------------------------------------------------------------------------
# Middleware Configuration
# ------------------------------------------------------------------------------
# 1. Internal HTTP middleware (timing, logging, safety catch)
@app.middleware("http")
async def add_process_time_and_log_middleware(request: Request, call_next):
    """Log incoming request timing without logging sensitive body payloads."""
    start_time = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception as exc:
        process_time = round((time.perf_counter() - start_time) * 1000, 2)
        logger.critical(
            f"Unhandled exception during {request.method} {request.url.path}: {exc}",
            exc_info=True,
        )
        response = JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "detail": "An internal server error occurred. Please contact the administrator.",
                "status_code": 500,
                "path": request.url.path,
            },
        )
        response.headers["X-Process-Time-Ms"] = str(process_time)
        return response

    process_time = round((time.perf_counter() - start_time) * 1000, 2)
    response.headers["X-Process-Time-Ms"] = str(process_time)
    logger.info(
        f"{request.method} {request.url.path} completed with {response.status_code} in {process_time}ms"
    )
    return response


# 2. Cross-Origin Resource Sharing (CORS) - Outermost middleware
# Allowed origins for frontend clients (development and production)
_allowed_origins = [
    "http://localhost:5174",
    "http://127.0.0.1:5174",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

# Merge any additional origins from settings.CORS_ORIGINS without duplicates
if isinstance(settings.CORS_ORIGINS, list):
    for _orig in settings.CORS_ORIGINS:
        _cleaned = str(_orig).strip().rstrip("/")
        if _cleaned and _cleaned not in _allowed_origins:
            _allowed_origins.append(_cleaned)
elif isinstance(settings.CORS_ORIGINS, str):
    for _orig in settings.CORS_ORIGINS.split(","):
        _cleaned = _orig.strip().rstrip("/")
        if _cleaned and _cleaned not in _allowed_origins:
            _allowed_origins.append(_cleaned)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"],
    allow_headers=[
        "Authorization",
        "Content-Type",
        "Accept",
        "Origin",
        "User-Agent",
        "DNT",
        "Cache-Control",
        "X-Mx-ReqToken",
        "Keep-Alive",
        "X-Requested-With",
        "If-Modified-Since",
        "X-Setup-Token",
        "Access-Control-Request-Method",
        "Access-Control-Request-Headers",
        "*",
    ],
    expose_headers=["Content-Length", "X-Process-Time-Ms"],
    max_age=600,
)


# ------------------------------------------------------------------------------
# Global Exception Handlers
# ------------------------------------------------------------------------------
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """Handle standard HTTP exceptions with structured JSON."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "detail": exc.detail,
            "status_code": exc.status_code,
            "path": request.url.path,
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle Pydantic request validation errors."""
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "detail": "Request validation failed.",
            "errors": jsonable_encoder(exc.errors()),
            "path": request.url.path,
        },
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Catch-all unhandled exception handler to protect secrets from leaking."""
    logger.critical(f"Unhandled exception during {request.method} {request.url.path}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": "An internal server error occurred. Please contact the administrator.",
            "status_code": 500,
            "path": request.url.path,
        },
    )


# ------------------------------------------------------------------------------
# Root & API Routers
# ------------------------------------------------------------------------------
@app.get(
    "/",
    tags=["Root"],
    summary="Store Service Root",
    description="Welcome endpoint providing API identification and Swagger documentation link.",
)
def root():
    """Root endpoint welcoming clients to VIYON Billing API."""
    return {
        "store": "VIYON",
        "tagline": "MEN'S COLLECTIONS",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "docs_url": settings.DOCS_URL,
        "health_check": f"{settings.API_V1_STR}/health",
    }


# Mount API Version 1
app.include_router(api_router, prefix=settings.API_V1_STR)
