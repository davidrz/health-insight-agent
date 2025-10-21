"""
Test script for error handling and monitoring functionality
"""
import asyncio
import sys
import os

# Add the backend directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from app.core.exceptions import (
    ValidationError, AuthenticationError, DatabaseError,
    ExternalServiceError, ErrorSeverity, ErrorCategory
)
from app.core.logging_config import (
    setup_logging, get_logger, generate_correlation_id,
    set_correlation_id, audit_logger
)
from app.core.monitoring import (
    record_performance_metric, measure_time, monitor_performance,
    CircuitBreaker, metrics_collector
)


async def test_error_handling():
    """Test custom exception classes"""
    print("Testing error handling...")
    
    # Test validation error
    try:
        raise ValidationError(
            "Invalid email format",
            field="email",
            value="invalid-email",
            correlation_id="test-123"
        )
    except ValidationError as e:
        print(f"✓ ValidationError: {e.message}")
        print(f"  Category: {e.category.value}")
        print(f"  Severity: {e.severity.value}")
        print(f"  Context: {e.context}")
    
    # Test authentication error
    try:
        raise AuthenticationError(
            "Invalid credentials",
            correlation_id="test-123"
        )
    except AuthenticationError as e:
        print(f"✓ AuthenticationError: {e.message}")
        print(f"  Category: {e.category.value}")
        print(f"  Severity: {e.severity.value}")
    
    # Test external service error
    try:
        raise ExternalServiceError(
            "Service unavailable",
            service_name="AWS Bedrock",
            correlation_id="test-123"
        )
    except ExternalServiceError as e:
        print(f"✓ ExternalServiceError: {e.message}")
        print(f"  Service: {e.context.get('service_name')}")


async def test_logging():
    """Test logging configuration"""
    print("\nTesting logging...")
    
    # Setup logging
    setup_logging()
    logger = get_logger(__name__)
    
    # Set correlation ID
    correlation_id = generate_correlation_id()
    set_correlation_id(correlation_id)
    
    # Test different log levels
    logger.info("Test info message", extra={"test_field": "test_value"})
    logger.warning("Test warning message")
    logger.error("Test error message")
    
    # Test audit logging
    audit_logger.log_authentication("test_user", True, "127.0.0.1")
    audit_logger.log_data_access(
        "test_user", "patient_123", "health_data", "record_456", "read", True
    )
    audit_logger.log_security_event(
        "suspicious_activity", "Multiple failed login attempts", "test_user", "127.0.0.1"
    )
    
    print(f"✓ Logging test completed with correlation ID: {correlation_id}")


async def test_monitoring():
    """Test monitoring functionality"""
    print("\nTesting monitoring...")
    
    # Test performance metrics
    record_performance_metric("test.metric", 42.5, "ms", {"component": "test"})
    record_performance_metric("test.counter", 1, "count")
    
    # Test timing context manager
    async with measure_time("test.operation"):
        await asyncio.sleep(0.1)  # Simulate work
    
    # Test performance decorator
    @monitor_performance("test.decorated_function")
    async def test_function():
        await asyncio.sleep(0.05)
        return "success"
    
    result = await test_function()
    print(f"✓ Decorated function result: {result}")
    
    # Test circuit breaker
    circuit_breaker = CircuitBreaker("test_service", failure_threshold=2)
    
    async def failing_service():
        raise Exception("Service unavailable")
    
    # Test circuit breaker with failures
    for i in range(3):
        try:
            await circuit_breaker.call(failing_service)
        except Exception as e:
            print(f"  Circuit breaker call {i+1} failed: {e}")
    
    # Check metrics
    summary = metrics_collector.get_metric_summary("test.operation")
    print(f"✓ Test operation metrics: {summary}")
    
    print("✓ Monitoring test completed")


async def test_health_check():
    """Test health check functionality"""
    print("\nTesting health check...")
    
    try:
        from app.api.routes.health import health_checker
        
        # Perform health check
        health_response = await health_checker.perform_health_check()
        
        print(f"✓ Health check status: {health_response.status}")
        print(f"  Components checked: {health_response.checks_total}")
        print(f"  Components healthy: {health_response.checks_passed}")
        print(f"  System metrics available: {bool(health_response.metrics)}")
        
    except Exception as e:
        print(f"✗ Health check failed: {e}")


async def main():
    """Run all tests"""
    print("=== Error Handling and Monitoring Tests ===\n")
    
    await test_error_handling()
    await test_logging()
    await test_monitoring()
    await test_health_check()
    
    print("\n=== All tests completed ===")


if __name__ == "__main__":
    asyncio.run(main())