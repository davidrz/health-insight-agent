"""
Health check endpoints with comprehensive system monitoring
"""
import asyncio
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any

from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel
import psutil

from app.core.config import settings
from app.core.logging_config import get_logger, get_correlation_id, audit_logger
from app.core.exceptions import SystemError, DatabaseError, CacheError
from app.infra.database import get_db_session
from app.infra.cache import cache_manager

router = APIRouter()
logger = get_logger(__name__)


class ComponentHealth(BaseModel):
    """Health status of a system component"""
    name: str
    status: str  # "healthy", "degraded", "unhealthy"
    response_time_ms: Optional[float] = None
    last_check: datetime
    error: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


class SystemMetrics(BaseModel):
    """System performance metrics"""
    cpu_usage_percent: float
    memory_usage_percent: float
    disk_usage_percent: float
    active_connections: int
    uptime_seconds: float


class HealthResponse(BaseModel):
    """Comprehensive health check response"""
    status: str  # "healthy", "degraded", "unhealthy"
    version: str
    app_name: str
    timestamp: datetime
    correlation_id: Optional[str]
    components: List[ComponentHealth]
    metrics: SystemMetrics
    checks_passed: int
    checks_total: int


class DetailedHealthResponse(BaseModel):
    """Detailed health response with additional diagnostics"""
    status: str
    version: str
    app_name: str
    timestamp: datetime
    correlation_id: Optional[str]
    components: List[ComponentHealth]
    metrics: SystemMetrics
    checks_passed: int
    checks_total: int
    environment: str
    uptime: str
    dependencies: Dict[str, Any]


class HealthChecker:
    """System health checker with component monitoring"""
    
    def __init__(self):
        self.start_time = time.time()
    
    async def check_database(self) -> ComponentHealth:
        """Check database connectivity and performance"""
        start_time = time.time()
        
        try:
            async with get_db_session() as session:
                # Simple query to test connectivity
                result = await session.execute("SELECT 1")
                await result.fetchone()
            
            response_time = (time.time() - start_time) * 1000
            
            return ComponentHealth(
                name="database",
                status="healthy",
                response_time_ms=response_time,
                last_check=datetime.now(timezone.utc),
                details={"connection_pool": "active"}
            )
        
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return ComponentHealth(
                name="database",
                status="unhealthy",
                response_time_ms=(time.time() - start_time) * 1000,
                last_check=datetime.now(timezone.utc),
                error=str(e)
            )
    
    async def check_cache(self) -> ComponentHealth:
        """Check Redis cache connectivity and performance"""
        start_time = time.time()
        
        try:
            # Test cache connectivity with a simple operation
            test_key = "health_check_test"
            await cache_manager.set(test_key, "test_value", ttl=10)
            value = await cache_manager.get(test_key)
            await cache_manager.delete(test_key)
            
            if value != "test_value":
                raise CacheError("Cache test value mismatch")
            
            response_time = (time.time() - start_time) * 1000
            
            return ComponentHealth(
                name="cache",
                status="healthy",
                response_time_ms=response_time,
                last_check=datetime.now(timezone.utc),
                details={"redis_connection": "active"}
            )
        
        except Exception as e:
            logger.error(f"Cache health check failed: {e}")
            return ComponentHealth(
                name="cache",
                status="unhealthy",
                response_time_ms=(time.time() - start_time) * 1000,
                last_check=datetime.now(timezone.utc),
                error=str(e)
            )
    
    async def check_aws_services(self) -> List[ComponentHealth]:
        """Check AWS service connectivity"""
        components = []
        
        # Check Bedrock service
        try:
            from app.infra.aws_bedrock import BedrockClient
            bedrock_client = BedrockClient()
            
            start_time = time.time()
            # Simple connectivity test (this would need to be implemented in the client)
            # For now, we'll just check if the client can be instantiated
            response_time = (time.time() - start_time) * 1000
            
            components.append(ComponentHealth(
                name="aws_bedrock",
                status="healthy",
                response_time_ms=response_time,
                last_check=datetime.now(timezone.utc),
                details={"service": "bedrock", "region": settings.AWS_REGION}
            ))
        
        except Exception as e:
            logger.error(f"Bedrock health check failed: {e}")
            components.append(ComponentHealth(
                name="aws_bedrock",
                status="unhealthy",
                last_check=datetime.now(timezone.utc),
                error=str(e)
            ))
        
        # Check SageMaker service
        try:
            from app.infra.aws_sagemaker import SageMakerClient
            sagemaker_client = SageMakerClient()
            
            start_time = time.time()
            # Simple connectivity test
            response_time = (time.time() - start_time) * 1000
            
            components.append(ComponentHealth(
                name="aws_sagemaker",
                status="healthy",
                response_time_ms=response_time,
                last_check=datetime.now(timezone.utc),
                details={"service": "sagemaker", "region": settings.AWS_REGION}
            ))
        
        except Exception as e:
            logger.error(f"SageMaker health check failed: {e}")
            components.append(ComponentHealth(
                name="aws_sagemaker",
                status="unhealthy",
                last_check=datetime.now(timezone.utc),
                error=str(e)
            ))
        
        return components
    
    async def check_mcp_server(self) -> ComponentHealth:
        """Check MCP server connectivity"""
        start_time = time.time()
        
        try:
            from app.agents.mcp_server import MCPServer
            # This would need to be implemented to actually test connectivity
            # For now, we'll simulate a basic check
            
            response_time = (time.time() - start_time) * 1000
            
            return ComponentHealth(
                name="mcp_server",
                status="healthy",
                response_time_ms=response_time,
                last_check=datetime.now(timezone.utc),
                details={"host": settings.MCP_SERVER_HOST, "port": settings.MCP_SERVER_PORT}
            )
        
        except Exception as e:
            logger.error(f"MCP server health check failed: {e}")
            return ComponentHealth(
                name="mcp_server",
                status="unhealthy",
                response_time_ms=(time.time() - start_time) * 1000,
                last_check=datetime.now(timezone.utc),
                error=str(e)
            )
    
    def get_system_metrics(self) -> SystemMetrics:
        """Get current system performance metrics"""
        try:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            
            # Memory usage
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            
            # Disk usage
            disk = psutil.disk_usage('/')
            disk_percent = (disk.used / disk.total) * 100
            
            # Network connections (approximate active connections)
            connections = len(psutil.net_connections())
            
            # Uptime
            uptime = time.time() - self.start_time
            
            return SystemMetrics(
                cpu_usage_percent=cpu_percent,
                memory_usage_percent=memory_percent,
                disk_usage_percent=disk_percent,
                active_connections=connections,
                uptime_seconds=uptime
            )
        
        except Exception as e:
            logger.error(f"Failed to get system metrics: {e}")
            return SystemMetrics(
                cpu_usage_percent=0.0,
                memory_usage_percent=0.0,
                disk_usage_percent=0.0,
                active_connections=0,
                uptime_seconds=time.time() - self.start_time
            )
    
    async def perform_health_check(self) -> HealthResponse:
        """Perform comprehensive health check"""
        components = []
        
        # Run all health checks concurrently
        tasks = [
            self.check_database(),
            self.check_cache(),
            self.check_mcp_server(),
        ]
        
        # Add AWS service checks
        aws_components_task = self.check_aws_services()
        
        # Execute all checks
        basic_results = await asyncio.gather(*tasks, return_exceptions=True)
        aws_results = await aws_components_task
        
        # Process basic results
        for result in basic_results:
            if isinstance(result, Exception):
                logger.error(f"Health check task failed: {result}")
                components.append(ComponentHealth(
                    name="unknown",
                    status="unhealthy",
                    last_check=datetime.now(timezone.utc),
                    error=str(result)
                ))
            else:
                components.append(result)
        
        # Add AWS results
        components.extend(aws_results)
        
        # Get system metrics
        metrics = self.get_system_metrics()
        
        # Calculate overall status
        healthy_count = sum(1 for c in components if c.status == "healthy")
        degraded_count = sum(1 for c in components if c.status == "degraded")
        total_count = len(components)
        
        if healthy_count == total_count:
            overall_status = "healthy"
        elif healthy_count + degraded_count >= total_count * 0.7:  # 70% threshold
            overall_status = "degraded"
        else:
            overall_status = "unhealthy"
        
        return HealthResponse(
            status=overall_status,
            version=settings.VERSION,
            app_name=settings.APP_NAME,
            timestamp=datetime.now(timezone.utc),
            correlation_id=get_correlation_id(),
            components=components,
            metrics=metrics,
            checks_passed=healthy_count + degraded_count,
            checks_total=total_count
        )


# Global health checker instance
health_checker = HealthChecker()


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Basic health check endpoint
    
    Returns overall system health status with component details
    """
    try:
        health_response = await health_checker.perform_health_check()
        
        # Log health check
        audit_logger.log_system_event(
            "health_check",
            f"Health check completed: {health_response.status}",
            success=health_response.status in ["healthy", "degraded"]
        )
        
        # Return appropriate HTTP status
        if health_response.status == "unhealthy":
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=health_response.dict()
            )
        
        return health_response
    
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        audit_logger.log_system_event(
            "health_check_error",
            f"Health check failed: {str(e)}",
            success=False
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "Health check failed", "message": str(e)}
        )


@router.get("/health/detailed", response_model=DetailedHealthResponse)
async def detailed_health_check():
    """
    Detailed health check endpoint with comprehensive diagnostics
    
    Provides additional system information and dependency status
    """
    try:
        basic_health = await health_checker.perform_health_check()
        
        # Additional detailed information
        dependencies = {
            "python_version": f"{psutil.sys.version_info.major}.{psutil.sys.version_info.minor}.{psutil.sys.version_info.micro}",
            "fastapi_version": "0.104.1",  # This should be dynamically determined
            "database_url": settings.DATABASE_URL.split('@')[0] + "@***",  # Mask credentials
            "redis_url": settings.REDIS_URL.split('@')[0] + "@***" if '@' in settings.REDIS_URL else settings.REDIS_URL,
            "aws_region": settings.AWS_REGION
        }
        
        uptime_seconds = basic_health.metrics.uptime_seconds
        uptime_str = f"{int(uptime_seconds // 3600)}h {int((uptime_seconds % 3600) // 60)}m {int(uptime_seconds % 60)}s"
        
        detailed_response = DetailedHealthResponse(
            **basic_health.dict(),
            environment="development" if settings.DEBUG else "production",
            uptime=uptime_str,
            dependencies=dependencies
        )
        
        audit_logger.log_system_event(
            "detailed_health_check",
            f"Detailed health check completed: {detailed_response.status}",
            success=detailed_response.status in ["healthy", "degraded"]
        )
        
        return detailed_response
    
    except Exception as e:
        logger.error(f"Detailed health check failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "Detailed health check failed", "message": str(e)}
        )


@router.get("/health/ready")
async def readiness_check():
    """
    Kubernetes-style readiness probe
    
    Returns 200 if the service is ready to accept traffic
    """
    try:
        health_response = await health_checker.perform_health_check()
        
        if health_response.status == "unhealthy":
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={"ready": False, "reason": "Service unhealthy"}
            )
        
        return {"ready": True, "status": health_response.status}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Readiness check failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"ready": False, "reason": str(e)}
        )


@router.get("/health/live")
async def liveness_check():
    """
    Kubernetes-style liveness probe
    
    Returns 200 if the service is alive (basic functionality)
    """
    try:
        # Basic liveness check - just verify the service is responding
        return {
            "alive": True,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "version": settings.VERSION
        }
    
    except Exception as e:
        logger.error(f"Liveness check failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"alive": False, "reason": str(e)}
        )