"""
Logging configuration for Health Insight Agent

This module provides structured logging with correlation IDs,
audit trails, and comprehensive error tracking.
"""
import json
import logging
import logging.config
import sys
import uuid
from contextvars import ContextVar
from datetime import datetime
from typing import Any, Dict, Optional
from pathlib import Path

from app.core.config import settings


# Context variable for correlation ID
correlation_id_var: ContextVar[Optional[str]] = ContextVar('correlation_id', default=None)


class CorrelationIdFilter(logging.Filter):
    """Logging filter that adds correlation ID to log records"""
    
    def filter(self, record: logging.LogRecord) -> bool:
        correlation_id = correlation_id_var.get()
        record.correlation_id = correlation_id or "no-correlation-id"
        return True


class StructuredFormatter(logging.Formatter):
    """
    Custom formatter that outputs structured JSON logs
    with correlation IDs and additional context
    """
    
    def format(self, record: logging.LogRecord) -> str:
        # Create base log entry
        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "correlation_id": getattr(record, 'correlation_id', 'no-correlation-id'),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "process_id": record.process,
            "thread_id": record.thread
        }
        
        # Add exception information if present
        if record.exc_info:
            log_entry["exception"] = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else None,
                "message": str(record.exc_info[1]) if record.exc_info[1] else None,
                "traceback": self.formatException(record.exc_info)
            }
        
        # Add extra fields from the log record
        extra_fields = {}
        for key, value in record.__dict__.items():
            if key not in {
                'name', 'msg', 'args', 'levelname', 'levelno', 'pathname',
                'filename', 'module', 'lineno', 'funcName', 'created',
                'msecs', 'relativeCreated', 'thread', 'threadName',
                'processName', 'process', 'getMessage', 'exc_info',
                'exc_text', 'stack_info', 'correlation_id'
            }:
                extra_fields[key] = value
        
        if extra_fields:
            log_entry["extra"] = extra_fields
        
        return json.dumps(log_entry, default=str, ensure_ascii=False)


class AuditFormatter(StructuredFormatter):
    """
    Specialized formatter for audit logs with additional
    security and compliance information
    """
    
    def format(self, record: logging.LogRecord) -> str:
        log_entry = json.loads(super().format(record))
        
        # Add audit-specific fields
        log_entry["audit"] = True
        log_entry["event_type"] = getattr(record, 'event_type', 'unknown')
        log_entry["user_id"] = getattr(record, 'user_id', None)
        log_entry["patient_id"] = getattr(record, 'patient_id', None)
        log_entry["resource_type"] = getattr(record, 'resource_type', None)
        log_entry["resource_id"] = getattr(record, 'resource_id', None)
        log_entry["action"] = getattr(record, 'action', None)
        log_entry["ip_address"] = getattr(record, 'ip_address', None)
        log_entry["user_agent"] = getattr(record, 'user_agent', None)
        log_entry["success"] = getattr(record, 'success', None)
        
        return json.dumps(log_entry, default=str, ensure_ascii=False)


def get_logging_config() -> Dict[str, Any]:
    """
    Get logging configuration dictionary
    """
    # Ensure log directory exists
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "structured": {
                "()": StructuredFormatter,
            },
            "audit": {
                "()": AuditFormatter,
            },
            "console": {
                "format": "%(asctime)s - %(name)s - %(levelname)s - [%(correlation_id)s] - %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S"
            }
        },
        "filters": {
            "correlation_id": {
                "()": CorrelationIdFilter,
            }
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "level": settings.LOG_LEVEL,
                "formatter": "console",
                "filters": ["correlation_id"],
                "stream": sys.stdout
            },
            "file": {
                "class": "logging.handlers.RotatingFileHandler",
                "level": "INFO",
                "formatter": "structured",
                "filters": ["correlation_id"],
                "filename": "logs/health_insight_agent.log",
                "maxBytes": 10485760,  # 10MB
                "backupCount": 5,
                "encoding": "utf8"
            },
            "error_file": {
                "class": "logging.handlers.RotatingFileHandler",
                "level": "ERROR",
                "formatter": "structured",
                "filters": ["correlation_id"],
                "filename": "logs/errors.log",
                "maxBytes": 10485760,  # 10MB
                "backupCount": 10,
                "encoding": "utf8"
            },
            "audit_file": {
                "class": "logging.handlers.RotatingFileHandler",
                "level": "INFO",
                "formatter": "audit",
                "filters": ["correlation_id"],
                "filename": "logs/audit.log",
                "maxBytes": 10485760,  # 10MB
                "backupCount": 20,
                "encoding": "utf8"
            }
        },
        "loggers": {
            "app": {
                "level": settings.LOG_LEVEL,
                "handlers": ["console", "file", "error_file"],
                "propagate": False
            },
            "app.audit": {
                "level": "INFO",
                "handlers": ["audit_file"],
                "propagate": False
            },
            "uvicorn": {
                "level": "INFO",
                "handlers": ["console", "file"],
                "propagate": False
            },
            "uvicorn.error": {
                "level": "INFO",
                "handlers": ["console", "file", "error_file"],
                "propagate": False
            },
            "uvicorn.access": {
                "level": "INFO",
                "handlers": ["file"],
                "propagate": False
            }
        },
        "root": {
            "level": settings.LOG_LEVEL,
            "handlers": ["console", "file"]
        }
    }
    
    return config


def setup_logging():
    """Initialize logging configuration"""
    config = get_logging_config()
    logging.config.dictConfig(config)


def generate_correlation_id() -> str:
    """Generate a new correlation ID"""
    return str(uuid.uuid4())


def set_correlation_id(correlation_id: str) -> None:
    """Set correlation ID for current context"""
    correlation_id_var.set(correlation_id)


def get_correlation_id() -> Optional[str]:
    """Get current correlation ID"""
    return correlation_id_var.get()


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger with the specified name
    
    Args:
        name: Logger name (typically __name__)
    
    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)


def get_audit_logger() -> logging.Logger:
    """
    Get the audit logger for security and compliance logging
    
    Returns:
        Audit logger instance
    """
    return logging.getLogger("app.audit")


class AuditLogger:
    """
    Specialized logger for audit events with structured logging
    """
    
    def __init__(self):
        self.logger = get_audit_logger()
    
    def log_authentication(
        self,
        user_id: Optional[str],
        success: bool,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        reason: Optional[str] = None
    ):
        """Log authentication events"""
        self.logger.info(
            f"Authentication {'successful' if success else 'failed'} for user {user_id or 'unknown'}",
            extra={
                "event_type": "authentication",
                "user_id": user_id,
                "success": success,
                "ip_address": ip_address,
                "user_agent": user_agent,
                "action": "login",
                "reason": reason
            }
        )
    
    def log_data_access(
        self,
        user_id: Optional[str],
        patient_id: Optional[str],
        resource_type: str,
        resource_id: Optional[str],
        action: str,
        success: bool,
        ip_address: Optional[str] = None
    ):
        """Log data access events"""
        self.logger.info(
            f"Data access: {action} {resource_type} {resource_id or 'unknown'} by user {user_id or 'unknown'}",
            extra={
                "event_type": "data_access",
                "user_id": user_id,
                "patient_id": patient_id,
                "resource_type": resource_type,
                "resource_id": resource_id,
                "action": action,
                "success": success,
                "ip_address": ip_address
            }
        )
    
    def log_security_event(
        self,
        event_type: str,
        description: str,
        user_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        severity: str = "medium"
    ):
        """Log security events"""
        self.logger.warning(
            f"Security event: {event_type} - {description}",
            extra={
                "event_type": "security",
                "user_id": user_id,
                "ip_address": ip_address,
                "action": event_type,
                "severity": severity,
                "success": False
            }
        )
    
    def log_system_event(
        self,
        event_type: str,
        description: str,
        success: bool = True,
        **kwargs
    ):
        """Log system events"""
        self.logger.info(
            f"System event: {event_type} - {description}",
            extra={
                "event_type": "system",
                "action": event_type,
                "success": success,
                **kwargs
            }
        )


# Global audit logger instance
audit_logger = AuditLogger()