"""
Correlation ID middleware for request tracking

This middleware ensures every request has a unique correlation ID
for distributed tracing and log correlation.
"""
import uuid
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.logging_config import set_correlation_id, get_logger

logger = get_logger(__name__)


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """
    Middleware to add correlation IDs to all requests
    
    This middleware:
    1. Extracts correlation ID from X-Correlation-ID header if present
    2. Generates a new correlation ID if not provided
    3. Sets the correlation ID in the context for logging
    4. Adds the correlation ID to the response headers
    """
    
    def __init__(self, app, header_name: str = "X-Correlation-ID"):
        super().__init__(app)
        self.header_name = header_name
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Extract or generate correlation ID
        correlation_id = request.headers.get(self.header_name)
        
        if not correlation_id:
            correlation_id = str(uuid.uuid4())
        
        # Set correlation ID in context for logging
        set_correlation_id(correlation_id)
        
        # Add correlation ID to request state for access in route handlers
        request.state.correlation_id = correlation_id
        
        # Process the request
        response = await call_next(request)
        
        # Add correlation ID to response headers
        response.headers[self.header_name] = correlation_id
        
        return response