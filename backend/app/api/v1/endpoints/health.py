"""Health check and telemetry endpoints."""

import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database.connection import get_db
from app.schemas.health import HealthResponse, DatabaseHealthResponse
from app.services.health_service import HealthService

logger = logging.getLogger("viyon_billing.api.health")

router = APIRouter()


@router.get(
    "",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Application Health Status",
    description="Returns the running status, environment, version, and server timestamp of the API.",
)
def get_application_health() -> HealthResponse:
    """Check if the FastAPI application is alive and responding."""
    return HealthService.get_application_health()


@router.get(
    "/database",
    response_model=DatabaseHealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Neon PostgreSQL Database Health Check",
    description="Tests the connection to Neon PostgreSQL, measures query roundtrip latency, and inspects pool status.",
    responses={
        503: {
            "description": "Database connectivity failed or pool exhausted",
        }
    },
)
def get_database_health(db: Session = Depends(get_db)) -> DatabaseHealthResponse:
    """Check connectivity and latency to the Neon PostgreSQL database."""
    try:
        return HealthService.check_database_health(db)
    except Exception as exc:
        logger.error(f"Database health check failed: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection failure. The Neon database is currently unreachable.",
        )
