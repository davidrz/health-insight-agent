"""
Infrastructure layer initialization for Health Insight Agent.

This module provides initialization functions for database, cache,
and AWS service infrastructure components.
"""

import logging
from typing import Optional

from .database import init_database, close_database, DatabaseHealthCheck
from .cache import init_cache, close_cache, CacheHealthCheck
from .aws_bedrock import init_bedrock, close_bedrock, get_bedrock_client
from .aws_sagemaker import init_sagemaker, close_sagemaker, get_sagemaker_client

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
        
        # Initialize AWS Bedrock
        bedrock_success = await init_bedrock()
        if bedrock_success:
            logger.info("Bedrock infrastructure initialized")
        else:
            logger.warning("Bedrock initialization failed - continuing without Bedrock")
        
        # Initialize AWS SageMaker
        sagemaker_success = await init_sagemaker()
        if sagemaker_success:
            logger.info("SageMaker infrastructure initialized")
        else:
            logger.warning("SageMaker initialization failed - continuing without SageMaker")
        
        logger.info("All infrastructure components initialized successfully")
        return True
        
    except Exception as e:
        logger.error(f"Failed to initialize infrastructure: {e}")
        return False


async def close_infrastructure() -> None:
    """Close all infrastructure connections."""
    try:
        # Close AWS service connections
        await close_bedrock()
        logger.info("Bedrock connections closed")
        
        await close_sagemaker()
        logger.info("SageMaker connections closed")
        
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
        "bedrock": {"status": "unknown"},
        "sagemaker": {"status": "unknown"},
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
        
        # Check Bedrock health
        try:
            bedrock_client = get_bedrock_client()
            results["bedrock"] = await bedrock_client.health_check()
            bedrock_healthy = results["bedrock"]["status"] == "healthy"
        except Exception as e:
            results["bedrock"] = {"status": "unhealthy", "error": str(e)}
            bedrock_healthy = False
        
        # Check SageMaker health
        try:
            sagemaker_client = get_sagemaker_client()
            results["sagemaker"] = await sagemaker_client.health_check()
            sagemaker_healthy = results["sagemaker"]["status"] == "healthy"
        except Exception as e:
            results["sagemaker"] = {"status": "unhealthy", "error": str(e)}
            sagemaker_healthy = False
        
        # Determine overall health (core services: database and cache must be healthy)
        core_healthy = db_healthy and cache_healthy
        results["overall"] = {
            "status": "healthy" if core_healthy else "unhealthy",
            "components_healthy": {
                "database": db_healthy,
                "cache": cache_healthy,
                "bedrock": bedrock_healthy,
                "sagemaker": sagemaker_healthy
            },
            "note": "AWS services are optional - system can operate with degraded functionality"
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
    "CacheHealthCheck",
    "get_bedrock_client",
    "get_sagemaker_client"
]