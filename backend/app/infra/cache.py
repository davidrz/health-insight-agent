"""
Redis cache configuration and management for Health Insight Agent.

This module provides Redis connection management, caching utilities,
and cache operations for frequently accessed data.
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Any, Optional, Dict, List
from contextlib import asynccontextmanager

import redis.asyncio as redis
from redis.asyncio import ConnectionPool

from ..core.config import settings

logger = logging.getLogger(__name__)

# Global Redis connection pool
redis_pool: Optional[ConnectionPool] = None
redis_client: Optional[redis.Redis] = None


def create_redis_pool():
    """Create Redis connection pool."""
    global redis_pool, redis_client
    
    try:
        redis_pool = ConnectionPool.from_url(
            settings.REDIS_URL,
            max_connections=settings.REDIS_POOL_SIZE,
            decode_responses=True,
            encoding='utf-8'
        )
        
        redis_client = redis.Redis(connection_pool=redis_pool)
        
        logger.info("Redis connection pool created successfully")
        
    except Exception as e:
        logger.error(f"Failed to create Redis pool: {e}")
        raise


async def init_cache():
    """Initialize Redis cache connection."""
    try:
        if redis_pool is None:
            create_redis_pool()
        
        # Test Redis connection
        await redis_client.ping()
        logger.info("Redis cache initialized successfully")
        
    except Exception as e:
        logger.error(f"Failed to initialize Redis cache: {e}")
        raise


async def close_cache():
    """Close Redis connections."""
    global redis_pool, redis_client
    
    if redis_client:
        await redis_client.close()
        logger.info("Redis client closed")
    
    if redis_pool:
        await redis_pool.disconnect()
        logger.info("Redis connection pool closed")


@asynccontextmanager
async def get_redis_client():
    """
    Get Redis client with automatic cleanup.
    
    Yields:
        redis.Redis: Redis client
        
    Raises:
        RuntimeError: If Redis is not initialized
    """
    if redis_client is None:
        raise RuntimeError("Redis not initialized. Call init_cache() first.")
    
    try:
        yield redis_client
    except Exception:
        # Redis operations are generally safe to retry
        logger.warning("Redis operation failed, but continuing")
        raise


class CacheManager:
    """Redis cache manager with health insight specific operations."""
    
    def __init__(self):
        self.default_ttl = settings.CACHE_TTL
        self.key_prefix = "health_insight:"
    
    def _make_key(self, key: str) -> str:
        """Create a prefixed cache key."""
        return f"{self.key_prefix}{key}"
    
    async def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache.
        
        Args:
            key: Cache key
            
        Returns:
            Cached value or None if not found
        """
        try:
            async with get_redis_client() as client:
                value = await client.get(self._make_key(key))
                if value:
                    return json.loads(value)
                return None
        except Exception as e:
            logger.warning(f"Cache get failed for key {key}: {e}")
            return None
    
    async def set(
        self, 
        key: str, 
        value: Any, 
        ttl: Optional[int] = None
    ) -> bool:
        """
        Set value in cache.
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds (uses default if None)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            async with get_redis_client() as client:
                ttl = ttl or self.default_ttl
                serialized_value = json.dumps(value, default=str)
                await client.setex(
                    self._make_key(key), 
                    ttl, 
                    serialized_value
                )
                return True
        except Exception as e:
            logger.warning(f"Cache set failed for key {key}: {e}")
            return False
    
    async def delete(self, key: str) -> bool:
        """
        Delete value from cache.
        
        Args:
            key: Cache key
            
        Returns:
            True if successful, False otherwise
        """
        try:
            async with get_redis_client() as client:
                result = await client.delete(self._make_key(key))
                return result > 0
        except Exception as e:
            logger.warning(f"Cache delete failed for key {key}: {e}")
            return False
    
    async def exists(self, key: str) -> bool:
        """
        Check if key exists in cache.
        
        Args:
            key: Cache key
            
        Returns:
            True if key exists, False otherwise
        """
        try:
            async with get_redis_client() as client:
                result = await client.exists(self._make_key(key))
                return result > 0
        except Exception as e:
            logger.warning(f"Cache exists check failed for key {key}: {e}")
            return False
    
    async def get_ttl(self, key: str) -> Optional[int]:
        """
        Get time to live for a key.
        
        Args:
            key: Cache key
            
        Returns:
            TTL in seconds or None if key doesn't exist
        """
        try:
            async with get_redis_client() as client:
                ttl = await client.ttl(self._make_key(key))
                return ttl if ttl > 0 else None
        except Exception as e:
            logger.warning(f"Cache TTL check failed for key {key}: {e}")
            return None
    
    async def increment(self, key: str, amount: int = 1) -> Optional[int]:
        """
        Increment a numeric value in cache.
        
        Args:
            key: Cache key
            amount: Amount to increment by
            
        Returns:
            New value or None if failed
        """
        try:
            async with get_redis_client() as client:
                return await client.incrby(self._make_key(key), amount)
        except Exception as e:
            logger.warning(f"Cache increment failed for key {key}: {e}")
            return None
    
    async def expire(self, key: str, ttl: int) -> bool:
        """
        Set expiration time for a key.
        
        Args:
            key: Cache key
            ttl: Time to live in seconds
            
        Returns:
            True if successful, False otherwise
        """
        try:
            async with get_redis_client() as client:
                result = await client.expire(self._make_key(key), ttl)
                return result
        except Exception as e:
            logger.warning(f"Cache expire failed for key {key}: {e}")
            return False
    
    # Health Insight specific cache operations
    
    async def cache_patient_insights(
        self, 
        patient_id: str, 
        insights: Dict[str, Any],
        ttl: int = 3600  # 1 hour default
    ) -> bool:
        """Cache patient insights."""
        key = f"insights:{patient_id}"
        return await self.set(key, insights, ttl)
    
    async def get_patient_insights(self, patient_id: str) -> Optional[Dict[str, Any]]:
        """Get cached patient insights."""
        key = f"insights:{patient_id}"
        return await self.get(key)
    
    async def cache_dashboard_data(
        self, 
        patient_id: str, 
        dashboard_data: Dict[str, Any],
        ttl: int = 900  # 15 minutes default
    ) -> bool:
        """Cache dashboard data."""
        key = f"dashboard:{patient_id}"
        return await self.set(key, dashboard_data, ttl)
    
    async def get_dashboard_data(self, patient_id: str) -> Optional[Dict[str, Any]]:
        """Get cached dashboard data."""
        key = f"dashboard:{patient_id}"
        return await self.get(key)
    
    async def cache_analysis_result(
        self, 
        request_hash: str, 
        result: Dict[str, Any],
        ttl: int = 1800  # 30 minutes default
    ) -> bool:
        """Cache analysis result."""
        key = f"analysis:{request_hash}"
        return await self.set(key, result, ttl)
    
    async def get_analysis_result(self, request_hash: str) -> Optional[Dict[str, Any]]:
        """Get cached analysis result."""
        key = f"analysis:{request_hash}"
        return await self.get(key)
    
    async def invalidate_patient_cache(self, patient_id: str) -> bool:
        """Invalidate all cache entries for a patient."""
        try:
            async with get_redis_client() as client:
                pattern = self._make_key(f"*:{patient_id}")
                keys = await client.keys(pattern)
                if keys:
                    await client.delete(*keys)
                return True
        except Exception as e:
            logger.warning(f"Cache invalidation failed for patient {patient_id}: {e}")
            return False
    
    async def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        try:
            async with get_redis_client() as client:
                info = await client.info()
                return {
                    "connected_clients": info.get("connected_clients", 0),
                    "used_memory": info.get("used_memory_human", "0B"),
                    "keyspace_hits": info.get("keyspace_hits", 0),
                    "keyspace_misses": info.get("keyspace_misses", 0),
                    "total_commands_processed": info.get("total_commands_processed", 0),
                }
        except Exception as e:
            logger.warning(f"Failed to get cache stats: {e}")
            return {"error": str(e)}


class CacheHealthCheck:
    """Redis cache health check utilities."""
    
    @staticmethod
    async def check_connection() -> bool:
        """
        Check if Redis connection is healthy.
        
        Returns:
            bool: True if connection is healthy, False otherwise
        """
        try:
            async with get_redis_client() as client:
                await client.ping()
                return True
        except Exception as e:
            logger.error(f"Redis health check failed: {e}")
            return False
    
    @staticmethod
    async def get_connection_info() -> Dict[str, Any]:
        """
        Get Redis connection information.
        
        Returns:
            dict: Connection information
        """
        try:
            async with get_redis_client() as client:
                info = await client.info()
                return {
                    "status": "healthy",
                    "redis_version": info.get("redis_version", "unknown"),
                    "connected_clients": info.get("connected_clients", 0),
                    "used_memory": info.get("used_memory_human", "0B"),
                    "uptime_in_seconds": info.get("uptime_in_seconds", 0),
                    "pool_size": settings.REDIS_POOL_SIZE,
                }
        except Exception as e:
            logger.error(f"Failed to get Redis info: {e}")
            return {
                "status": "unhealthy",
                "error": str(e)
            }


# Global cache manager instance
cache_manager = CacheManager()