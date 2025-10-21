"""
Global error handlers for Health Insight Agent

This module provides centralized error handling with structured logging,
correlation ID tracking, and appropriate HTTP responses.
"""
import traceback
from typing import Any, Dict

from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.exceptions import (
    BaseHealthInsightError, ValidationError, AuthenticationError,
    AuthorizationError, ExternalServiceError, DatabaseError,
    CacheError, SecurityError, RateLimitError, NotFoundError,
    ErrorSeverity
)
from app.core.logging_config import get_logger, get_correlation_id, audit_logger

logger = get_logger(__name__)


def create_error_response(
    error: Exception,
    status_code: int,
    correlation_id: str = None
) -> Dict[str, Any]:
    """
    Create standardized error response
    
    Args:
        error: The exception that occurred
        status_code: HTTP status code
        correlation_id: Request correlation ID
    
    Returns:
        Standardized error response dictionary
    """
    correlation_id = correlation_id or get_correlation_id() or "no-correlation-id"
    
    if isinstance(error, BaseHealthInsightError):
        return {
            "error": {
                "type": error.__class__.__name__,
                "message": error.message,
                "category": error.category.value,
                "severity": error.severity.value,
                "correlation_id": correlation_id,
                "context": error.context
            }
        }
    else:
        return {
            "error": {
                "type": error.__class__.__name__,
                "message": str(error),
                "category": "system",
                "severity": "medium",
                "correlation_id": correlation_id
            }
        }


async def base_health_insight_error_handler(
    request: Request,
    exc: BaseHealthInsightError
) -> JSONResponse:
    """
    Handle BaseHealthInsightError and its subclasses
    """
    correlation_id = get_correlation_id()
    
    # Determine HTTP status code based on exception type
    if isinstance(exc, ValidationError):
        status_code = status.HTTP_400_BAD_REQUEST
    elif isinstance(exc, AuthenticationError):
        status_code = status.HTTP_401_UNAUTHORIZED
    elif isinstance(exc, AuthorizationError):
        status_code = status.HTTP_403_FORBIDDEN
    elif isinstance(exc, NotFoundError):
        status_code = status.HTTP_404_NOT_FOUND
    elif isinstance(exc, RateLimitError):
        status_code = status.HTTP_429_TOO_MANY_REQUESTS
    elif isinstance(exc, ExternalServiceError):
        status_code = status.HTTP_502_BAD_GATEWAY
    elif isinstance(exc, (DatabaseError, CacheError)):
        status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    elif isinstance(exc, SecurityError):
        status_code = status.HTTP_403_FORBIDDEN
    else:
        status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    
    # Log the error with appropriate level
    if exc.severity == ErrorSeverity.CRITICAL:
        logger.critical(
            f"Critical error: {exc.message}",
            extra={
                "error_type": exc.__class__.__name__,
                "category": exc.category.value,
                "context": exc.context,
                "original_error": str(exc.original_error) if exc.original_error else None
            }
        )
    elif exc.severity == ErrorSeverity.HIGH:
        logger.error(
            f"High severity error: {exc.message}",
            extra={
                "error_type": exc.__class__.__name__,
                "category": exc.category.value,
                "context": exc.context,
                "original_error": str(exc.original_error) if exc.original_error else None
            }
        )
    elif exc.severity == ErrorSeverity.MEDIUM:
        logger.warning(
            f"Medium severity error: {exc.message}",
            extra={
                "error_type": exc.__class__.__name__,
                "category": exc.category.value,
                "context": exc.context
            }
        )
    else:  # LOW severity
        logger.info(
            f"Low severity error: {exc.message}",
            extra={
                "error_type": exc.__class__.__name__,
                "category": exc.category.value,
                "context": exc.context
            }
        )
    
    # Log security events to audit log
    if isinstance(exc, (SecurityError, AuthenticationError, AuthorizationError)):
        audit_logger.log_security_event(
            event_type=exc.__class__.__name__,
            description=exc.message,
            ip_address=request.client.host if request.client else None,
            severity=exc.severity.value
        )
    
    response_data = create_error_response(exc, status_code, correlation_id)
    return JSONResponse(
        status_code=status_code,
        content=response_data
    )


async def http_exception_handler(
    request: Request,
    exc: HTTPException
) -> JSONResponse:
    """
    Handle FastAPI HTTPException
    """
    correlation_id = get_correlation_id()
    
    logger.warning(
        f"HTTP exception: {exc.status_code} - {exc.detail}",
        extra={
            "status_code": exc.status_code,
            "detail": exc.detail,
            "path": str(request.url.path),
            "method": request.method
        }
    )
    
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "type": "HTTPException",
                "message": exc.detail,
                "category": "http",
                "severity": "medium",
                "correlation_id": correlation_id,
                "status_code": exc.status_code
            }
        }
    )


async def starlette_http_exception_handler(
    request: Request,
    exc: StarletteHTTPException
) -> JSONResponse:
    """
    Handle Starlette HTTPException
    """
    correlation_id = get_correlation_id()
    
    logger.warning(
        f"Starlette HTTP exception: {exc.status_code} - {exc.detail}",
        extra={
            "status_code": exc.status_code,
            "detail": exc.detail,
            "path": str(request.url.path),
            "method": request.method
        }
    )
    
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "type": "HTTPException",
                "message": exc.detail,
                "category": "http",
                "severity": "medium",
                "correlation_id": correlation_id,
                "status_code": exc.status_code
            }
        }
    )


async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError
) -> JSONResponse:
    """
    Handle Pydantic validation errors
    """
    correlation_id = get_correlation_id()
    
    # Extract validation error details
    errors = []
    for error in exc.errors():
        errors.append({
            "field": ".".join(str(loc) for loc in error["loc"]),
            "message": error["msg"],
            "type": error["type"]
        })
    
    logger.warning(
        f"Validation error: {len(errors)} validation failures",
        extra={
            "validation_errors": errors,
            "path": str(request.url.path),
            "method": request.method
        }
    )
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": {
                "type": "ValidationError",
                "message": "Request validation failed",
                "category": "validation",
                "severity": "low",
                "correlation_id": correlation_id,
                "validation_errors": errors
            }
        }
    )


async def general_exception_handler(
    request: Request,
    exc: Exception
) -> JSONResponse:
    """
    Handle unexpected exceptions
    """
    correlation_id = get_correlation_id()
    
    # Log the full traceback for debugging
    logger.error(
        f"Unhandled exception: {exc.__class__.__name__}: {str(exc)}",
        extra={
            "path": str(request.url.path),
            "method": request.method,
            "traceback": traceback.format_exc()
        }
    )
    
    # Log as system event in audit log
    audit_logger.log_system_event(
        "unhandled_exception",
        f"Unhandled exception: {exc.__class__.__name__}",
        success=False,
        path=str(request.url.path),
        method=request.method
    )
    
    response_data = create_error_response(exc, status.HTTP_500_INTERNAL_SERVER_ERROR, correlation_id)
    
    # Don't expose internal error details in production
    if not request.app.debug:
        response_data["error"]["message"] = "Internal server error"
        response_data["error"].pop("context", None)
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=response_data
    )


def register_error_handlers(app):
    """
    Register all error handlers with the FastAPI application
    
    Args:
        app: FastAPI application instance
    """
    app.add_exception_handler(BaseHealthInsightError, base_health_insight_error_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(StarletteHTTPException, starlette_http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, general_exception_handler)