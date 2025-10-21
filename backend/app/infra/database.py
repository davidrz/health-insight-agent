"""
Database configuration and session management for Health Insight Agent.

This module provides SQLAlchemy configuration, session management,
and database connection utilities.
"""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

from sqlalchemy import create_engine, MetaData
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import NullPool

from ..core.config import settings

logger = logging.getLogger(__name__)

# Create declarative base for SQLAlchemy models
Base = declarative_base()

# Metadata for migrations
metadata = MetaData()

# Database engines
async_engine: Optional[object] = None
sync_engine: Optional[object] = None

# Session makers
AsyncSessionLocal: Optional[async_sessionmaker] = None
SessionLocal: Optional[sessionmaker] = None


def create_database_engines():
    """Create both async and sync database engines."""
    global async_engine, sync_engine, AsyncSessionLocal, SessionLocal
    
    # Create async engine for application use
    async_engine = create_async_engine(
        settings.DATABASE_URL,
        pool_size=settings.DATABASE_POOL_SIZE,
        max_overflow=settings.DATABASE_MAX_OVERFLOW,
        echo=settings.DEBUG,
        future=True,
    )
    
    # Create sync engine for migrations
    sync_engine = create_engine(
        settings.database_url_sync,
        pool_size=settings.DATABASE_POOL_SIZE,
        max_overflow=settings.DATABASE_MAX_OVERFLOW,
        echo=settings.DEBUG,
        future=True,
    )
    
    # Create session makers
    AsyncSessionLocal = async_sessionmaker(
        bind=async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
        autocommit=False,
    )
    
    SessionLocal = sessionmaker(
        bind=sync_engine,
        autoflush=False,
        autocommit=False,
    )
    
    logger.info("Database engines and session makers created successfully")


async def init_database():
    """Initialize database connection and create tables if needed."""
    try:
        if async_engine is None:
            create_database_engines()
        
        # Test database connection
        async with async_engine.begin() as conn:
            # Import models to ensure they are registered
            from . import models  # noqa: F401
            
            # Create tables (in production, use Alembic migrations)
            if settings.DEBUG:
                await conn.run_sync(Base.metadata.create_all)
                logger.info("Database tables created successfully")
        
        logger.info("Database initialized successfully")
        
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise


async def close_database():
    """Close database connections."""
    global async_engine, sync_engine
    
    if async_engine:
        await async_engine.dispose()
        logger.info("Async database engine disposed")
    
    if sync_engine:
        sync_engine.dispose()
        logger.info("Sync database engine disposed")


@asynccontextmanager
async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Get an async database session with automatic cleanup.
    
    Yields:
        AsyncSession: Database session
        
    Raises:
        RuntimeError: If database is not initialized
    """
    if AsyncSessionLocal is None:
        raise RuntimeError("Database not initialized. Call init_database() first.")
    
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


def get_sync_session():
    """
    Get a sync database session for migrations.
    
    Returns:
        Session: Database session
        
    Raises:
        RuntimeError: If database is not initialized
    """
    if SessionLocal is None:
        raise RuntimeError("Database not initialized. Call create_database_engines() first.")
    
    return SessionLocal()


# Dependency for FastAPI
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency to get database session.
    
    Yields:
        AsyncSession: Database session
    """
    async with get_async_session() as session:
        yield session


class DatabaseHealthCheck:
    """Database health check utilities."""
    
    @staticmethod
    async def check_connection() -> bool:
        """
        Check if database connection is healthy.
        
        Returns:
            bool: True if connection is healthy, False otherwise
        """
        try:
            async with get_async_session() as session:
                await session.execute("SELECT 1")
                return True
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return False
    
    @staticmethod
    async def get_connection_info() -> dict:
        """
        Get database connection information.
        
        Returns:
            dict: Connection information
        """
        try:
            async with get_async_session() as session:
                result = await session.execute(
                    "SELECT version(), current_database(), current_user"
                )
                version, database, user = result.fetchone()
                
                return {
                    "status": "healthy",
                    "version": version,
                    "database": database,
                    "user": user,
                    "pool_size": settings.DATABASE_POOL_SIZE,
                    "max_overflow": settings.DATABASE_MAX_OVERFLOW,
                }
        except Exception as e:
            logger.error(f"Failed to get database info: {e}")
            return {
                "status": "unhealthy",
                "error": str(e)
            }