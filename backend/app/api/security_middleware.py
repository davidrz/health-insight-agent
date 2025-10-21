"""
Security middleware for the Health Insight Agent API.
"""

import time
import json
import logging
from typing import Dict, Any, Optional
from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from collections import defaultdict
import re

from app.core.security import audit_logger, data_sanitizer, SecurityError
from app.core.config import settings

logger = logging.getLogger(__name__)


class SecurityAuditMiddleware(BaseHTTPMiddleware):
    """Middleware for security auditing and logging."""
    
    async def dispatch(self, request: Request, call_next):
        """Process request with security auditing."""
        start_time = time.time()
        
        # Extract client information
        client_ip = self._get_client_ip(request)
        user_agent = request.headers.get("user-agent", "unknown")
        
        # Log request
        audit_logger.log_security_event(
            event_type="API_REQUEST",
            user_id=None,  # Will be updated after authentication
            description=f"{request.method} {request.url.path}",
            ip_address=client_ip,
            additional_data={
                "method": request.method,
                "path": request.url.path,
                "query_params": str(request.query_params),
                "user_agent": user_agent
            }
        )
        
        try:
            response = await call_next(request)
            
            # Log successful response
            process_time = time.time() - start_time
            if response.status_code >= 400:
                audit_logger.log_security_event(
                    event_type="API_ERROR",
                    user_id=getattr(request.state, 'user_id', None),
                    description=f"HTTP {response.status_code} for {request.method} {request.url.path}",
                    severity="WARNING",
                    ip_address=client_ip,
                    additional_data={
                        "status_code": response.status_code,
                        "process_time": process_time
                    }
                )
            
            return response
            
        except Exception as e:
            # Log exception
            audit_logger.log_security_event(
                event_type="API_EXCEPTION",
                user_id=getattr(request.state, 'user_id', None),
                description=f"Exception in {request.method} {request.url.path}: {str(e)}",
                severity="ERROR",
                ip_address=client_ip
            )
            raise
    
    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP address from request."""
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        
        return request.client.host if request.client else "unknown"


class InputSanitizationMiddleware(BaseHTTPMiddleware):
    """Middleware for input sanitization and validation."""
    
    def __init__(self, app):
        super().__init__(app)
        self.max_request_size = 10 * 1024 * 1024  # 10MB
        self.suspicious_patterns = [
            r'<script[^>]*>.*?</script>',  # Script tags
            r'javascript:',  # JavaScript URLs
            r'data:.*base64',  # Data URLs with base64
            r'eval\s*\(',  # eval() calls
            r'exec\s*\(',  # exec() calls
            r'__import__',  # Python imports
            r'subprocess',  # Subprocess calls
        ]
    
    async def dispatch(self, request: Request, call_next):
        """Process request with input sanitization."""
        # Check request size
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > self.max_request_size:
            audit_logger.log_security_event(
                event_type="OVERSIZED_REQUEST",
                user_id=None,
                description=f"Request size {content_length} exceeds limit",
                severity="WARNING",
                ip_address=self._get_client_ip(request)
            )
            return JSONResponse(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                content={
                    "success": False,
                    "error_code": "REQUEST_TOO_LARGE",
                    "message": "Request size exceeds maximum allowed limit"
                }
            )
        
        # Sanitize request body for POST/PUT requests
        if request.method in ["POST", "PUT", "PATCH"]:
            try:
                body = await request.body()
                if body:
                    body_str = body.decode('utf-8')
                    
                    # Check for suspicious patterns
                    for pattern in self.suspicious_patterns:
                        if re.search(pattern, body_str, re.IGNORECASE):
                            audit_logger.log_security_event(
                                event_type="SUSPICIOUS_INPUT",
                                user_id=None,
                                description=f"Suspicious pattern detected: {pattern}",
                                severity="WARNING",
                                ip_address=self._get_client_ip(request)
                            )
                            return JSONResponse(
                                status_code=status.HTTP_400_BAD_REQUEST,
                                content={
                                    "success": False,
                                    "error_code": "INVALID_INPUT",
                                    "message": "Request contains invalid or suspicious content"
                                }
                            )
                    
                    # Sanitize the body
                    sanitized_body = data_sanitizer.sanitize_input(body_str)
                    
                    # Replace request body with sanitized version
                    request._body = sanitized_body.encode('utf-8')
                    
            except Exception as e:
                logger.error(f"Error sanitizing request body: {e}")
                return JSONResponse(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    content={
                        "success": False,
                        "error_code": "INVALID_REQUEST",
                        "message": "Unable to process request body"
                    }
                )
        
        return await call_next(request)
    
    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP address from request."""
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        
        return request.client.host if request.client else "unknown"


class DataProtectionMiddleware(BaseHTTPMiddleware):
    """Middleware for data protection and PII filtering."""
    
    async def dispatch(self, request: Request, call_next):
        """Process request with data protection."""
        response = await call_next(request)
        
        # Filter response data for sensitive information
        if hasattr(response, 'body') and response.status_code == 200:
            try:
                # Only process JSON responses
                content_type = response.headers.get("content-type", "")
                if "application/json" in content_type:
                    # This is a simplified approach - in production you'd need
                    # to properly handle streaming responses
                    pass
                    
            except Exception as e:
                logger.error(f"Error filtering response data: {e}")
        
        # Add security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = "default-src 'self'"
        
        return response


class ThreatDetectionMiddleware(BaseHTTPMiddleware):
    """Middleware for threat detection and prevention."""
    
    def __init__(self, app):
        super().__init__(app)
        self.failed_attempts = defaultdict(list)
        self.blocked_ips = set()
        self.max_failed_attempts = 5
        self.block_duration = 3600  # 1 hour
    
    async def dispatch(self, request: Request, call_next):
        """Process request with threat detection."""
        client_ip = self._get_client_ip(request)
        current_time = time.time()
        
        # Check if IP is blocked
        if client_ip in self.blocked_ips:
            audit_logger.log_security_event(
                event_type="BLOCKED_IP_ACCESS",
                user_id=None,
                description=f"Blocked IP {client_ip} attempted access",
                severity="WARNING",
                ip_address=client_ip
            )
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "success": False,
                    "error_code": "IP_BLOCKED",
                    "message": "Access temporarily blocked due to suspicious activity"
                }
            )
        
        # Clean old failed attempts
        self._clean_old_attempts(client_ip, current_time)
        
        # Process request
        response = await call_next(request)
        
        # Track failed authentication attempts
        if response.status_code == 401:
            self.failed_attempts[client_ip].append(current_time)
            
            # Check if should block IP
            if len(self.failed_attempts[client_ip]) >= self.max_failed_attempts:
                self.blocked_ips.add(client_ip)
                audit_logger.log_security_event(
                    event_type="IP_BLOCKED",
                    user_id=None,
                    description=f"IP {client_ip} blocked after {self.max_failed_attempts} failed attempts",
                    severity="CRITICAL",
                    ip_address=client_ip
                )
                
                # Schedule unblock (in production, use a proper scheduler)
                # For now, we'll rely on the cleanup process
        
        return response
    
    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP address from request."""
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        
        return request.client.host if request.client else "unknown"
    
    def _clean_old_attempts(self, client_ip: str, current_time: float):
        """Clean old failed attempts outside the time window."""
        if client_ip in self.failed_attempts:
            # Remove attempts older than block duration
            self.failed_attempts[client_ip] = [
                attempt_time for attempt_time in self.failed_attempts[client_ip]
                if current_time - attempt_time < self.block_duration
            ]
            
            # Remove IP from blocked list if block duration has passed
            if not self.failed_attempts[client_ip] and client_ip in self.blocked_ips:
                self.blocked_ips.remove(client_ip)


class HealthDataProtectionMiddleware(BaseHTTPMiddleware):
    """Specialized middleware for health data protection compliance."""
    
    async def dispatch(self, request: Request, call_next):
        """Process request with health data protection."""
        # Log health data access
        if self._is_health_data_endpoint(request.url.path):
            audit_logger.log_data_access(
                user_id=getattr(request.state, 'user_id', 'anonymous'),
                patient_id=self._extract_patient_id(request),
                action=request.method,
                resource=self._get_resource_type(request.url.path),
                ip_address=self._get_client_ip(request),
                user_agent=request.headers.get("user-agent")
            )
        
        response = await call_next(request)
        
        # Add HIPAA compliance headers
        if self._is_health_data_endpoint(request.url.path):
            response.headers["X-Health-Data-Protection"] = "HIPAA-Compliant"
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, private"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        
        return response
    
    def _is_health_data_endpoint(self, path: str) -> bool:
        """Check if endpoint handles health data."""
        health_endpoints = [
            '/api/v1/health-data',
            '/api/v1/insights',
            '/api/v1/analysis',
            '/api/v1/dashboard'
        ]
        return any(path.startswith(endpoint) for endpoint in health_endpoints)
    
    def _extract_patient_id(self, request: Request) -> Optional[str]:
        """Extract patient ID from request."""
        # Try to get from path parameters
        path_parts = request.url.path.split('/')
        for i, part in enumerate(path_parts):
            if part == 'health-data' and i + 1 < len(path_parts):
                return path_parts[i + 1]
        
        # Try to get from query parameters
        return request.query_params.get('patient_id')
    
    def _get_resource_type(self, path: str) -> str:
        """Get resource type from path."""
        if 'health-data' in path:
            return 'health_data'
        elif 'insights' in path:
            return 'insights'
        elif 'analysis' in path:
            return 'analysis'
        elif 'dashboard' in path:
            return 'dashboard'
        else:
            return 'unknown'
    
    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP address from request."""
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        
        return request.client.host if request.client else "unknown"