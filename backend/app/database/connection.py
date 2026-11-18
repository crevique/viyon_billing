"""Database connection and session management for VIYON Billing System."""

import app.core.dns_fallback  # noqa: F401 - Must be loaded to guarantee DNS resolution for cloud DB
import os
from typing import Generator
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

# Load environment variables from .env file
load_dotenv()


def get_database_url() -> str:
    """Retrieve and format the database URL for Psycopg 3."""
    url = os.getenv("DATABASE_URL")
    if not url:
        raise ValueError(
            "DATABASE_URL is not configured in environment variables or .env file."
        )

    # Normalize url scheme to postgresql+psycopg for Psycopg 3 driver
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+psycopg://", 1)
    elif url.startswith("postgresql://") and not url.startswith("postgresql+psycopg://"):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)

    return url


# Initialize SQLAlchemy engine with production-ready connection pool settings
# pool_pre_ping: Critical for serverless Neon PostgreSQL to detect dropped connections
# pool_recycle: Recycles connections before serverless idle timeouts
DATABASE_URL = get_database_url()

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    pool_recycle=300,
    echo=False,
)

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


def get_db() -> Generator[Session, None, None]:
    """Dependency for obtaining a scoped database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
