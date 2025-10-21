"""
Monitoring utilities for Health Insight Agent

This module provides performance monitoring, metrics collection,
and alerting capabilities for system observability.
"""
import time
import asyncio
from typing import Dict, Any, Optional, Callable, List
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from contextlib import asynccontextmanager
from functools import wraps

from app.core.logging_config import get_logger, audit_logger
from app.core.exceptions import SystemError, ErrorSeverity

logger = get_logger(__name__)


@dataclass
class PerformanceMetric:
    """Performance metric data structure"""
    name: str
    value: float
    unit: str
    timestamp: datetime
    tags: Dict[str, str] = field(default_factory=dict)


@dataclass
class AlertRule:
    """Alert rule configuration"""
    name: str
    metric_name: str
    threshold: float
    operator: str  # "gt", "lt", "eq", "gte", "lte"
    severity: ErrorSeverity
    enabled: bool = True
    cooldown_minutes: int = 5


class MetricsCollector:
    """
    Collects and stores performance metrics
    """
    
    def __init__(self):
        self.metrics: Dict[str, List[PerformanceMetric]] = {}
        self.alert_rules: List[AlertRule] = []
        self.last_alerts: Dict[str, datetime] = {}
    
    def record_metric(
        self,
        name: str,
        value: float,
        unit: str = "count",
        tags: Optional[Dict[str, str]] = None
    ):
        """Record a performance metric"""
        metric = PerformanceMetric(
            name=name,
            value=value,
            unit=unit,
            timestamp=datetime.utcnow(),
            tags=tags or {}
        )
        
        if name not in self.metrics:
            self.metrics[name] = []
        
        self.metrics[name].append(metric)
        
        # Keep only last 1000 metrics per name to prevent memory issues
        if len(self.metrics[name]) > 1000:
            self.metrics[name] = self.metrics[name][-1000:]
        
        # Check alert rules
        self._check_alerts(metric)
    
    def get_metrics(
        self,
        name: str,
        since: Optional[datetime] = None
    ) -> List[PerformanceMetric]:
        """Get metrics by name, optionally filtered by time"""
        if name not in self.metrics:
            return []
        
        metrics = self.metrics[name]
        
        if since:
            metrics = [m for m in metrics if m.timestamp >= since]
        
        return metrics
    
    def get_metric_summary(
        self,
        name: str,
        since: Optional[datetime] = None
    ) -> Dict[str, float]:
        """Get summary statistics for a metric"""
        metrics = self.get_metrics(name, since)
        
        if not metrics:
            return {}
        
        values = [m.value for m in metrics]
        
        return {
            "count": len(values),
            "min": min(values),
            "max": max(values),
            "avg": sum(values) / len(values),
            "latest": values[-1]
        }
    
    def add_alert_rule(self, rule: AlertRule):
        """Add an alert rule"""
        self.alert_rules.append(rule)
        logger.info(f"Added alert rule: {rule.name}")
    
    def _check_alerts(self, metric: PerformanceMetric):
        """Check if metric triggers any alerts"""
        for rule in self.alert_rules:
            if not rule.enabled or rule.metric_name != metric.name:
                continue
            
            # Check cooldown
            if rule.name in self.last_alerts:
                cooldown_end = self.last_alerts[rule.name] + timedelta(minutes=rule.cooldown_minutes)
                if datetime.utcnow() < cooldown_end:
                    continue
            
            # Check threshold
            triggered = False
            if rule.operator == "gt" and metric.value > rule.threshold:
                triggered = True
            elif rule.operator == "lt" and metric.value < rule.threshold:
                triggered = True
            elif rule.operator == "gte" and metric.value >= rule.threshold:
                triggered = True
            elif rule.operator == "lte" and metric.value <= rule.threshold:
                triggered = True
            elif rule.operator == "eq" and metric.value == rule.threshold:
                triggered = True
            
            if triggered:
                self._trigger_alert(rule, metric)
    
    def _trigger_alert(self, rule: AlertRule, metric: PerformanceMetric):
        """Trigger an alert"""
        self.last_alerts[rule.name] = datetime.utcnow()
        
        alert_message = (
            f"Alert: {rule.name} - {metric.name} = {metric.value} {metric.unit} "
            f"({rule.operator} {rule.threshold})"
        )
        
        if rule.severity == ErrorSeverity.CRITICAL:
            logger.critical(alert_message)
        elif rule.severity == ErrorSeverity.HIGH:
            logger.error(alert_message)
        elif rule.severity == ErrorSeverity.MEDIUM:
            logger.warning(alert_message)
        else:
            logger.info(alert_message)
        
        # Log to audit trail
        audit_logger.log_system_event(
            "alert_triggered",
            alert_message,
            success=False,
            alert_rule=rule.name,
            metric_name=metric.name,
            metric_value=metric.value,
            threshold=rule.threshold,
            severity=rule.severity.value
        )


# Global metrics collector
metrics_collector = MetricsCollector()


def record_performance_metric(
    name: str,
    value: float,
    unit: str = "count",
    tags: Optional[Dict[str, str]] = None
):
    """
    Record a performance metric
    
    Args:
        name: Metric name
        value: Metric value
        unit: Unit of measurement
        tags: Additional tags for the metric
    """
    metrics_collector.record_metric(name, value, unit, tags)


@asynccontextmanager
async def measure_time(metric_name: str, tags: Optional[Dict[str, str]] = None):
    """
    Context manager to measure execution time
    
    Args:
        metric_name: Name of the timing metric
        tags: Additional tags for the metric
    """
    start_time = time.time()
    try:
        yield
    finally:
        duration = (time.time() - start_time) * 1000  # Convert to milliseconds
        record_performance_metric(metric_name, duration, "ms", tags)


def monitor_performance(metric_name: Optional[str] = None, tags: Optional[Dict[str, str]] = None):
    """
    Decorator to monitor function performance
    
    Args:
        metric_name: Custom metric name (defaults to function name)
        tags: Additional tags for the metric
    """
    def decorator(func: Callable):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            name = metric_name or f"{func.__module__}.{func.__name__}"
            async with measure_time(name, tags):
                return await func(*args, **kwargs)
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            name = metric_name or f"{func.__module__}.{func.__name__}"
            start_time = time.time()
            try:
                return func(*args, **kwargs)
            finally:
                duration = (time.time() - start_time) * 1000
                record_performance_metric(name, duration, "ms", tags)
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    
    return decorator


def monitor_error_rate(func: Callable):
    """
    Decorator to monitor function error rates
    """
    @wraps(func)
    async def async_wrapper(*args, **kwargs):
        metric_name = f"{func.__module__}.{func.__name__}.calls"
        error_metric_name = f"{func.__module__}.{func.__name__}.errors"
        
        record_performance_metric(metric_name, 1)
        
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            record_performance_metric(error_metric_name, 1)
            raise
    
    @wraps(func)
    def sync_wrapper(*args, **kwargs):
        metric_name = f"{func.__module__}.{func.__name__}.calls"
        error_metric_name = f"{func.__module__}.{func.__name__}.errors"
        
        record_performance_metric(metric_name, 1)
        
        try:
            return func(*args, **kwargs)
        except Exception as e:
            record_performance_metric(error_metric_name, 1)
            raise
    
    return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper


class CircuitBreaker:
    """
    Circuit breaker pattern implementation for external service calls
    """
    
    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        expected_exception: type = Exception
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        
        self.failure_count = 0
        self.last_failure_time = None
        self.state = "closed"  # closed, open, half-open
    
    async def call(self, func: Callable, *args, **kwargs):
        """
        Execute function with circuit breaker protection
        """
        if self.state == "open":
            if self._should_attempt_reset():
                self.state = "half-open"
                logger.info(f"Circuit breaker {self.name} attempting reset")
            else:
                raise SystemError(
                    f"Circuit breaker {self.name} is open",
                    context={"circuit_breaker": self.name, "state": self.state}
                )
        
        try:
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
            
            # Success - reset failure count
            if self.state == "half-open":
                self.state = "closed"
                logger.info(f"Circuit breaker {self.name} reset to closed")
            
            self.failure_count = 0
            record_performance_metric(f"circuit_breaker.{self.name}.success", 1)
            
            return result
        
        except self.expected_exception as e:
            self._record_failure()
            record_performance_metric(f"circuit_breaker.{self.name}.failure", 1)
            raise
    
    def _record_failure(self):
        """Record a failure and update circuit breaker state"""
        self.failure_count += 1
        self.last_failure_time = datetime.utcnow()
        
        if self.failure_count >= self.failure_threshold:
            self.state = "open"
            logger.warning(
                f"Circuit breaker {self.name} opened after {self.failure_count} failures"
            )
            
            audit_logger.log_system_event(
                "circuit_breaker_opened",
                f"Circuit breaker {self.name} opened",
                success=False,
                circuit_breaker=self.name,
                failure_count=self.failure_count
            )
    
    def _should_attempt_reset(self) -> bool:
        """Check if circuit breaker should attempt reset"""
        if not self.last_failure_time:
            return True
        
        return (
            datetime.utcnow() - self.last_failure_time
        ).total_seconds() >= self.recovery_timeout


def setup_default_alerts():
    """Setup default alert rules for system monitoring"""
    
    # Response time alerts
    metrics_collector.add_alert_rule(AlertRule(
        name="high_response_time",
        metric_name="api.response_time",
        threshold=5000,  # 5 seconds
        operator="gt",
        severity=ErrorSeverity.HIGH
    ))
    
    # Error rate alerts
    metrics_collector.add_alert_rule(AlertRule(
        name="high_error_rate",
        metric_name="api.errors",
        threshold=10,  # 10 errors per minute
        operator="gt",
        severity=ErrorSeverity.HIGH
    ))
    
    # Database connection alerts
    metrics_collector.add_alert_rule(AlertRule(
        name="database_slow_response",
        metric_name="database.response_time",
        threshold=1000,  # 1 second
        operator="gt",
        severity=ErrorSeverity.MEDIUM
    ))
    
    # Cache performance alerts
    metrics_collector.add_alert_rule(AlertRule(
        name="cache_slow_response",
        metric_name="cache.response_time",
        threshold=100,  # 100ms
        operator="gt",
        severity=ErrorSeverity.MEDIUM
    ))
    
    logger.info("Default monitoring alerts configured")


# Initialize default alerts
setup_default_alerts()