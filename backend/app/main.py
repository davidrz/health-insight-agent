"""
Health Insight Agent - FastAPI Application Entry Point
"""
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.logging_config import setup_logging, get_logger, audit_logger
from app.core.exceptions import SystemError
from app.api.routes import health, health_data, insights, analysis, dashboard, auth
from app.api.middleware import (
    RateLimitMiddleware, RequestValidationMiddleware, 
    SecurityHeadersMiddleware, LoggingMiddleware
)
from app.api.security_middleware import (
    SecurityAuditMiddleware, InputSanitizationMiddleware,
    DataProtectionMiddleware, ThreatDetectionMiddleware,
    HealthDataProtectionMiddleware
)
from app.api.correlation_middleware import CorrelationIdMiddleware
from app.api.error_handlers import register_error_handlers
from app.infra.cache import init_cache, close_cache

# Initialize logging first
setup_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager with comprehensive error handling."""
    # Startup
    logger.info("Starting Health Insight Agent API...")
    audit_logger.log_system_event("application_startup", "Health Insight Agent starting up")
    
    startup_errors = []
    
    # Initialize cache
    try:
        await init_cache()
        logger.info("Cache initialized successfully")
        audit_logger.log_system_event("cache_init", "Cache initialized successfully")
    except Exception as e:
        error_msg = f"Failed to initialize cache: {e}"
        logger.error(error_msg)
        startup_errors.append(error_msg)
        audit_logger.log_system_event("cache_init_failed", error_msg, success=False)
    
    # Log startup completion
    if startup_errors:
        logger.warning(f"Application started with {len(startup_errors)} errors: {startup_errors}")
        audit_logger.log_system_event(
            "application_startup_partial",
            f"Application started with errors: {len(startup_errors)}",
            success=False,
            errors=startup_errors
        )
    else:
        logger.info("Health Insight Agent API started successfully")
        audit_logger.log_system_event("application_startup_complete", "Application started successfully")
    
    yield
    
    # Shutdown
    logger.info("Shutting down Health Insight Agent API...")
    audit_logger.log_system_event("application_shutdown", "Health Insight Agent shutting down")
    
    # Close cache connections
    try:
        await close_cache()
        logger.info("Cache connections closed")
        audit_logger.log_system_event("cache_shutdown", "Cache connections closed successfully")
    except Exception as e:
        error_msg = f"Error closing cache connections: {e}"
        logger.error(error_msg)
        audit_logger.log_system_event("cache_shutdown_failed", error_msg, success=False)
    
    logger.info("Health Insight Agent API shutdown complete")
    audit_logger.log_system_event("application_shutdown_complete", "Application shutdown complete")

def create_app() -> FastAPI:
    """Create and configure FastAPI application with comprehensive error handling"""
    app = FastAPI(
        title="Health Insight Agent API",
        description="AI-powered health analysis system for personal laboratory use",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
        debug=settings.DEBUG
    )
    
    # Register error handlers first
    register_error_handlers(app)
    
    # Add middleware (order matters - first added is outermost)
    # Correlation ID middleware should be first to ensure all requests have correlation IDs
    app.add_middleware(CorrelationIdMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(HealthDataProtectionMiddleware)
    app.add_middleware(DataProtectionMiddleware)
    app.add_middleware(ThreatDetectionMiddleware)
    app.add_middleware(InputSanitizationMiddleware)
    app.add_middleware(SecurityAuditMiddleware)
    app.add_middleware(LoggingMiddleware)
    app.add_middleware(RequestValidationMiddleware)
    app.add_middleware(RateLimitMiddleware, calls_per_minute=settings.RATE_LIMIT_PER_MINUTE)
    
    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_HOSTS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Include routers
    app.include_router(health.router, prefix="/api/v1", tags=["health"])
    app.include_router(auth.router, prefix="/api/v1/auth", tags=["authentication"])
    app.include_router(health_data.router, prefix="/api/v1", tags=["health-data"])
    app.include_router(insights.router, prefix="/api/v1", tags=["insights"])
    app.include_router(analysis.router, prefix="/api/v1", tags=["analysis"])
    app.include_router(dashboard.router, prefix="/api/v1", tags=["dashboard"])
    
    return app

app = create_app()

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Health Insight Agent API", 
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs"
    }