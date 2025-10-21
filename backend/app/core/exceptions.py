"""
Custom exception classes for Health Insight Agent

This module defines a comprehensive hierarchy of custom exceptions
for different error categories throughout the application.
"""
from typing import Any, Dict, Optional
from enum import Enum


class ErrorCategory(str, Enum):
    """Error categories for classification and monitoring"""
    VALIDATION = "validation"
    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    BUSINESS_LOGIC = "business_logic"
    EXTERNAL_SERVICE = "external_service"
    DATABASE = "database"
    CACHE = "cache"
    NETWORK = "network"
    SYSTEM = "system"
    SECURITY = "security"


class ErrorSeverity(str, Enum):
    """Error severity levels for monitoring and alerting"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class BaseHealthInsightError(Exception):
    """
    Base exception class for all Health Insight Agent errors.
    
    Provides structured error information including category, severity,
    correlation ID, and additional context for monitoring and debugging.
    """
    
    def __init__(
        self,
        message: str,
        category: ErrorCategory = ErrorCategory.SYSTEM,
        severity: ErrorSeverity = ErrorSeverity.MEDIUM,
        correlation_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        original_error: Optional[Exception] = None
    ):
        super().__init__(message)
        self.message = message
        self.category = category
        self.severity = severity
        self.correlation_id = correlation_id
        self.context = context or {}
        self.original_error = original_error
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for logging and API responses"""
        return {
            "error_type": self.__class__.__name__,
            "message": self.message,
            "category": self.category.value,
            "severity": self.severity.value,
            "correlation_id": self.correlation_id,
            "context": self.context,
            "original_error": str(self.original_error) if self.original_error else None
        }


# Validation Errors
class ValidationError(BaseHealthInsightError):
    """Raised when data validation fails"""
    
    def __init__(
        self,
        message: str,
        field: Optional[str] = None,
        value: Optional[Any] = None,
        **kwargs
    ):
        context = kwargs.get("context", {})
        if field:
            context["field"] = field
        if value is not None:
            context["invalid_value"] = str(value)
        
        super().__init__(
            message,
            category=ErrorCategory.VALIDATION,
            severity=ErrorSeverity.LOW,
            context=context,
            **kwargs
        )


class HealthDataValidationError(ValidationError):
    """Raised when health data validation fails"""
    pass


class SchemaValidationError(ValidationError):
    """Raised when API schema validation fails"""
    pass


# Authentication and Authorization Errors
class AuthenticationError(BaseHealthInsightError):
    """Raised when authentication fails"""
    
    def __init__(self, message: str = "Authentication failed", **kwargs):
        super().__init__(
            message,
            category=ErrorCategory.AUTHENTICATION,
            severity=ErrorSeverity.HIGH,
            **kwargs
        )


class AuthorizationError(BaseHealthInsightError):
    """Raised when authorization fails"""
    
    def __init__(self, message: str = "Access denied", **kwargs):
        super().__init__(
            message,
            category=ErrorCategory.AUTHORIZATION,
            severity=ErrorSeverity.HIGH,
            **kwargs
        )


class TokenError(AuthenticationError):
    """Raised when JWT token is invalid or expired"""
    pass


# Business Logic Errors
class BusinessLogicError(BaseHealthInsightError):
    """Raised when business rules are violated"""
    
    def __init__(self, message: str, **kwargs):
        super().__init__(
            message,
            category=ErrorCategory.BUSINESS_LOGIC,
            severity=ErrorSeverity.MEDIUM,
            **kwargs
        )


class AnalysisError(BusinessLogicError):
    """Raised when health analysis fails"""
    pass


class InsightGenerationError(BusinessLogicError):
    """Raised when insight generation fails"""
    pass


class PatientDataError(BusinessLogicError):
    """Raised when patient data operations fail"""
    pass


# External Service Errors
class ExternalServiceError(BaseHealthInsightError):
    """Base class for external service errors"""
    
    def __init__(
        self,
        message: str,
        service_name: Optional[str] = None,
        **kwargs
    ):
        context = kwargs.get("context", {})
        if service_name:
            context["service_name"] = service_name
        
        super().__init__(
            message,
            category=ErrorCategory.EXTERNAL_SERVICE,
            severity=ErrorSeverity.HIGH,
            context=context,
            **kwargs
        )


class AIServiceError(ExternalServiceError):
    """Base class for AI service errors"""
    pass


class BedrockServiceError(AIServiceError):
    """Raised when AWS Bedrock service fails"""
    
    def __init__(self, message: str, **kwargs):
        super().__init__(message, service_name="AWS Bedrock", **kwargs)


class SageMakerServiceError(AIServiceError):
    """Raised when AWS SageMaker service fails"""
    
    def __init__(self, message: str, **kwargs):
        super().__init__(message, service_name="AWS SageMaker", **kwargs)


class MCPServiceError(ExternalServiceError):
    """Raised when MCP server operations fail"""
    
    def __init__(self, message: str, **kwargs):
        super().__init__(message, service_name="MCP Server", **kwargs)


# Database and Cache Errors
class DatabaseError(BaseHealthInsightError):
    """Raised when database operations fail"""
    
    def __init__(self, message: str, **kwargs):
        super().__init__(
            message,
            category=ErrorCategory.DATABASE,
            severity=ErrorSeverity.HIGH,
            **kwargs
        )


class CacheError(BaseHealthInsightError):
    """Raised when cache operations fail"""
    
    def __init__(self, message: str, **kwargs):
        super().__init__(
            message,
            category=ErrorCategory.CACHE,
            severity=ErrorSeverity.MEDIUM,
            **kwargs
        )


class ConnectionError(BaseHealthInsightError):
    """Raised when connection to external resources fails"""
    
    def __init__(
        self,
        message: str,
        resource: Optional[str] = None,
        **kwargs
    ):
        context = kwargs.get("context", {})
        if resource:
            context["resource"] = resource
        
        super().__init__(
            message,
            category=ErrorCategory.NETWORK,
            severity=ErrorSeverity.HIGH,
            context=context,
            **kwargs
        )


# Security Errors
class SecurityError(BaseHealthInsightError):
    """Raised when security violations are detected"""
    
    def __init__(self, message: str, **kwargs):
        super().__init__(
            message,
            category=ErrorCategory.SECURITY,
            severity=ErrorSeverity.CRITICAL,
            **kwargs
        )


class DataProtectionError(SecurityError):
    """Raised when data protection measures fail"""
    pass


class ThreatDetectionError(SecurityError):
    """Raised when security threats are detected"""
    pass


# System Errors
class SystemError(BaseHealthInsightError):
    """Raised when system-level errors occur"""
    
    def __init__(self, message: str, **kwargs):
        super().__init__(
            message,
            category=ErrorCategory.SYSTEM,
            severity=ErrorSeverity.CRITICAL,
            **kwargs
        )


class ConfigurationError(SystemError):
    """Raised when configuration is invalid"""
    pass


class ResourceExhaustionError(SystemError):
    """Raised when system resources are exhausted"""
    pass


class TimeoutError(SystemError):
    """Raised when operations timeout"""
    pass


# Rate Limiting Errors
class RateLimitError(BaseHealthInsightError):
    """Raised when rate limits are exceeded"""
    
    def __init__(
        self,
        message: str = "Rate limit exceeded",
        limit: Optional[int] = None,
        window: Optional[str] = None,
        **kwargs
    ):
        context = kwargs.get("context", {})
        if limit:
            context["rate_limit"] = limit
        if window:
            context["time_window"] = window
        
        super().__init__(
            message,
            category=ErrorCategory.SYSTEM,
            severity=ErrorSeverity.MEDIUM,
            context=context,
            **kwargs
        )


# Not Found Errors
class NotFoundError(BaseHealthInsightError):
    """Raised when requested resources are not found"""
    
    def __init__(
        self,
        message: str,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        **kwargs
    ):
        context = kwargs.get("context", {})
        if resource_type:
            context["resource_type"] = resource_type
        if resource_id:
            context["resource_id"] = resource_id
        
        super().__init__(
            message,
            category=ErrorCategory.BUSINESS_LOGIC,
            severity=ErrorSeverity.LOW,
            context=context,
            **kwargs
        )


class PatientNotFoundError(NotFoundError):
    """Raised when patient is not found"""
    
    def __init__(self, patient_id: str, **kwargs):
        super().__init__(
            f"Patient not found: {patient_id}",
            resource_type="patient",
            resource_id=patient_id,
            **kwargs
        )


class InsightReportNotFoundError(NotFoundError):
    """Raised when insight report is not found"""
    
    def __init__(self, report_id: str, **kwargs):
        super().__init__(
            f"Insight report not found: {report_id}",
            resource_type="insight_report",
            resource_id=report_id,
            **kwargs
        )


# Duplicate Resource Errors
class DuplicateResourceError(BaseHealthInsightError):
    """Raised when attempting to create duplicate resources"""
    
    def __init__(
        self,
        message: str,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        **kwargs
    ):
        context = kwargs.get("context", {})
        if resource_type:
            context["resource_type"] = resource_type
        if resource_id:
            context["resource_id"] = resource_id
        
        super().__init__(
            message,
            category=ErrorCategory.BUSINESS_LOGIC,
            severity=ErrorSeverity.LOW,
            context=context,
            **kwargs
        )