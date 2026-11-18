"""Service layer for health checks and database diagnostic monitoring."""

import time
from datetime import datetime, timezone
from sqlalchemy import text
from sqlalchemy.orm import Session
from sqlalchemy.pool import QueuePool
from app.database.connection import engine
from app.schemas.health import (
    HealthResponse,
    DatabaseHealthResponse,
    DatabasePoolStatus,
)
from app.core.config import settings


class HealthService:
    """Service providing runtime and database health diagnostics."""

    @staticmethod
    def get_application_health() -> HealthResponse:
        """Return general application health and build metadata."""
        return HealthResponse(
            status="ok",
            environment=settings.ENVIRONMENT,
            version=settings.VERSION,
            timestamp=datetime.now(timezone.utc),
        )

    @staticmethod
    def check_database_health(db: Session) -> DatabaseHealthResponse:
        """Execute a round-trip database ping and collect pool telemetry."""
        start_time = time.perf_counter()

        # Run query to test engine and roundtrip latency
        result = db.execute(text("SELECT version(), current_database();")).fetchone()
        latency_ms = round((time.perf_counter() - start_time) * 1000, 2)

        server_version = result[0] if result else "Unknown"
        db_name = result[1] if result else "Unknown"

        # Pool metrics from connection engine
        pool = engine.pool
        if isinstance(pool, QueuePool):
            pool_size = pool.size()
            max_overflow = getattr(pool, "_max_overflow", 20)
            checked_in = pool.checkedin()
            checked_out = pool.checkedout()
        else:
            pool_size = getattr(pool, "size", lambda: 0)()
            max_overflow = getattr(pool, "_max_overflow", 0)
            checked_in = getattr(pool, "checkedin", lambda: 0)()
            checked_out = getattr(pool, "checkedout", lambda: 0)()

        pool_status = DatabasePoolStatus(
            pool_size=pool_size,
            max_overflow=max_overflow,
            checked_in_connections=checked_in,
            checked_out_connections=checked_out,
        )

        return DatabaseHealthResponse(
            status="healthy",
            database_connected=True,
            latency_ms=latency_ms,
            server_version=server_version,
            current_database=db_name,
            connection_pool=pool_status,
            timestamp=datetime.now(timezone.utc),
        )
