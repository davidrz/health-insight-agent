"""
Infrastructure layer initialization for Health Insight Agent.

This module provides initialization functions for database and cache
infrastructure components.
"""

import logging
from typing import Optional

from .database import init_database, close_database, DatabaseHealthCheck
from .cache import init_cache, close_cache, CacheHealthCheck

logger = logging.getLogger(__name__)


async def init_infrastructure() -> bool:
    """
    Initialize all infrastructure components.
    
    Returns:
        bool: True if all components initialized successfully, False otherwise
    """
    try:
        # Initialize database
        await init_database()
        logger.info("Database infrastructure initialized")
        
        # Initialize cache
        await init_cache()
        logger.info("Cache infrastructure initialized")
        
        logger.info("All infrastructure components initialized successfully")
        return True
        
    except Exception as e:
        logger.error(f"Failed to initialize infrastructure: {e}")
        return False


async def close_infrastructure() -> None:
    """Close all infrastructure connections."""
    try:
        # Close cache connections
        await close_cache()
        logger.info("Cache connections closed")
        
        # Close database connections
        await close_database()
        logger.info("Database connections closed")
        
        logger.info("All infrastructure connections closed")
        
    except Exception as e:
        logger.error(f"Error closing infrastructure: {e}")


async def health_check_infrastructure() -> dict:
    """
    Perform health checks on all infrastructure components.
    
    Returns:
        dict: Health check results for all components
    """
    results = {
        "database": {"status": "unknown"},
        "cache": {"status": "unknown"},
        "overall": {"status": "unknown"}
    }
    
    try:
        # Check database health
        db_healthy = await DatabaseHealthCheck.check_connection()
        if db_healthy:
            results["database"] = await DatabaseHealthCheck.get_connection_info()
        else:
            results["database"] = {"status": "unhealthy", "error": "Connection failed"}
        
        # Check cache health
        cache_healthy = await CacheHealthCheck.check_connection()
        if cache_healthy:
            results["cache"] = await CacheHealthCheck.get_connection_info()
        else:
            results["cache"] = {"status": "unhealthy", "error": "Connection failed"}
        
        # Determine overall health
        overall_healthy = db_healthy and cache_healthy
        results["overall"] = {
            "status": "healthy" if overall_healthy else "unhealthy",
            "components_healthy": {
                "database": db_healthy,
                "cache": cache_healthy
            }
        }
        
    except Exception as e:
        logger.error(f"Error during infrastructure health check: {e}")
        results["overall"] = {
            "status": "error",
            "error": str(e)
        }
    
    return results


# Export key components for easy importing
__all__ = [
    "init_infrastructure",
    "close_infrastructure", 
    "health_check_infrastructure",
    "DatabaseHealthCheck",
    "CacheHealthCheck"
]