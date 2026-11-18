"""Pydantic schemas for application and database health checks."""

from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Basic application status response."""

    status: str = Field(default="ok", description="Overall application health status")
    environment: str = Field(..., description="Running environment (development/production)")
    version: str = Field(..., description="Application version")
    timestamp: datetime = Field(..., description="Current UTC server timestamp")


class DatabasePoolStatus(BaseModel):
    """Connection pool operational statistics."""

    pool_size: int
    max_overflow: int
    checked_in_connections: int
    checked_out_connections: int


class DatabaseHealthResponse(BaseModel):
    """Database connectivity and diagnostic response."""

    status: str = Field(default="healthy", description="Database health status")
    database_connected: bool = Field(default=True, description="Whether active DB connection succeeded")
    latency_ms: float = Field(..., description="Database roundtrip ping latency in milliseconds")
    server_version: str = Field(..., description="PostgreSQL server engine release")
    current_database: str = Field(..., description="Active database name")
    connection_pool: DatabasePoolStatus
    timestamp: datetime = Field(..., description="Current UTC check timestamp")


class ErrorResponse(BaseModel):
    """Standardized error response body."""

    detail: str = Field(..., description="Human-readable error explanation")
    error_code: Optional[str] = Field(default=None, description="Domain-specific error code")
    timestamp: datetime = Field(..., description="Time error occurred")
