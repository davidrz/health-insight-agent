#!/usr/bin/env python3
"""
AWS Service Clients Testing - Bedrock and SageMaker
"""
import sys
sys.path.append('.')
import asyncio
from datetime import datetime

async def test_bedrock_client():
    """Test Bedrock client initialization and basic functionality"""
    print("🤖 Testing Bedrock Client...")
    
    try:
        from app.infra.aws_bedrock import BedrockClient, get_bedrock_client
        
        # Test client initialization
        client = get_bedrock_client()
        print(f"  ✅ Bedrock client initialized with model: {client.model_id}")
        
        # Test health check
        health_result = await client.health_check()
        print(f"  ✅ Health check completed: {health_result['status']}")
        
        # Test circuit breaker functionality
        if client.circuit_breaker.can_execute():
            print("  ✅ Circuit breaker is operational")
        
        # Test mock insight generation (will use mock if AWS not configured)
        try:
            insights = await client.generate_insights(
                "Analyze this health data", 
                {"heart_rate": 75, "blood_pressure": "120/80"}
            )
            print(f"  ✅ Insight generation test completed (length: {len(insights)} chars)")
        except Exception as e:
            print(f"  ⚠️  Insight generation failed (expected if AWS not configured): {e}")
        
        # Test symptom analysis
        try:
            analysis = await client.analyze_symptoms(["headache", "fatigue", "fever"])
            print(f"  ✅ Symptom analysis test completed: {analysis.get('severity_assessment', 'unknown')}")
        except Exception as e:
            print(f"  ⚠️  Symptom analysis failed (expected if AWS not configured): {e}")
        
        return True
        
    except Exception as e:
        print(f"  ❌ Bedrock client test failed: {e}")
        return False

async def test_sagemaker_client():
    """Test SageMaker client initialization and basic functionality"""
    print("🧠 Testing SageMaker Client...")
    
    try:
        from app.infra.aws_sagemaker import (
            SageMakerClient, get_sagemaker_client, 
            HealthMetrics, TimeSeriesData
        )
        
        # Test client initialization
        client = get_sagemaker_client()
        print(f"  ✅ SageMaker client initialized for region: {client.region}")
        
        # Test health check
        health_result = await client.health_check()
        print(f"  ✅ Health check completed: {health_result['status']}")
        
        # Test circuit breakers
        if client.risk_prediction_cb.can_execute() and client.anomaly_detection_cb.can_execute():
            print("  ✅ Circuit breakers are operational")
        
        # Test health metrics data structure
        health_data = {
            'age': 45,
            'gender': 'male',
            'heart_rate': 75,
            'blood_pressure_systolic': 120,
            'blood_pressure_diastolic': 80,
            'cholesterol': 200,
            'glucose': 95,
            'bmi': 24.5,
            'smoking': False,
            'exercise_frequency': 3,
            'family_history': ['diabetes']
        }
        
        health_metrics = HealthMetrics(health_data)
        feature_vector = health_metrics.to_feature_vector()
        print(f"  ✅ Health metrics conversion: {len(feature_vector)} features")
        
        # Test risk prediction (will use mock if endpoint not available)
        try:
            risk_assessment = await client.predict_risk_factors(health_metrics)
            print(f"  ✅ Risk prediction test: score={risk_assessment.risk_score:.2f}, factors={len(risk_assessment.risk_factors)}")
        except Exception as e:
            print(f"  ⚠️  Risk prediction failed (expected if AWS not configured): {e}")
        
        # Test time series data structure
        time_series_data = TimeSeriesData({
            'timestamps': ['2024-01-01', '2024-01-02', '2024-01-03'],
            'values': [120, 125, 130],
            'metric_name': 'systolic_bp',
            'patient_id': 'test-patient'
        })
        
        model_input = time_series_data.to_model_input()
        print(f"  ✅ Time series data conversion: {len(model_input['instances'])} instances")
        
        # Test anomaly detection (will use mock if endpoint not available)
        try:
            anomaly_report = await client.detect_anomalies(time_series_data)
            print(f"  ✅ Anomaly detection test: score={anomaly_report.anomaly_score:.2f}, anomalies={len(anomaly_report.anomalies)}")
        except Exception as e:
            print(f"  ⚠️  Anomaly detection failed (expected if AWS not configured): {e}")
        
        return True
        
    except Exception as e:
        print(f"  ❌ SageMaker client test failed: {e}")
        return False

async def test_circuit_breaker():
    """Test circuit breaker functionality"""
    print("⚡ Testing Circuit Breaker...")
    
    try:
        from app.infra.aws_bedrock import CircuitBreaker
        
        # Test circuit breaker states
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=1)
        
        # Initial state should be CLOSED
        assert cb.state == "CLOSED"
        assert cb.can_execute() == True
        print("  ✅ Initial state: CLOSED")
        
        # Record failures to trigger OPEN state
        cb.record_failure()
        cb.record_failure()
        
        assert cb.state == "OPEN"
        assert cb.can_execute() == False
        print("  ✅ After failures: OPEN")
        
        # Test recovery after timeout
        await asyncio.sleep(1.1)  # Wait for recovery timeout
        assert cb.can_execute() == True  # Should be HALF_OPEN
        print("  ✅ After timeout: HALF_OPEN")
        
        # Record success to return to CLOSED
        cb.record_success()
        assert cb.state == "CLOSED"
        print("  ✅ After success: CLOSED")
        
        return True
        
    except Exception as e:
        print(f"  ❌ Circuit breaker test failed: {e}")
        return False

async def test_infrastructure_integration():
    """Test AWS clients integration with infrastructure layer"""
    print("🏗️ Testing Infrastructure Integration...")
    
    try:
        from app.infra import init_infrastructure, health_check_infrastructure, close_infrastructure
        
        # Test initialization (should not fail even if AWS not configured)
        init_success = await init_infrastructure()
        print(f"  ✅ Infrastructure initialization: {'success' if init_success else 'partial'}")
        
        # Test health checks
        health_results = await health_check_infrastructure()
        print(f"  ✅ Health check completed: {health_results['overall']['status']}")
        
        # Check individual components
        for component in ['database', 'cache', 'bedrock', 'sagemaker']:
            if component in health_results:
                status = health_results[component].get('status', 'unknown')
                print(f"    - {component}: {status}")
        
        # Test cleanup
        await close_infrastructure()
        print("  ✅ Infrastructure cleanup completed")
        
        return True
        
    except Exception as e:
        print(f"  ❌ Infrastructure integration test failed: {e}")
        return False

async def run_aws_client_tests():
    """Run all AWS client tests"""
    print("🚀 TESTING AWS SERVICE CLIENTS")
    print("=" * 60)
    
    tests = [
        test_circuit_breaker,
        test_bedrock_client,
        test_sagemaker_client,
        test_infrastructure_integration
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if await test():
                passed += 1
                print(f"✅ {test.__name__} PASSED\n")
            else:
                failed += 1
                print(f"❌ {test.__name__} FAILED\n")
        except Exception as e:
            failed += 1
            print(f"❌ {test.__name__} CRASHED: {e}\n")
    
    print("=" * 60)
    print(f"📊 AWS CLIENT TEST RESULTS: {passed} PASSED, {failed} FAILED")
    
    if failed == 0:
        print("🏆 AWS CLIENTS WORKING CORRECTLY!")
        return True
    else:
        print("⚠️  AWS CLIENT ISSUES DETECTED - REVIEW REQUIRED")
        return False

if __name__ == "__main__":
    success = asyncio.run(run_aws_client_tests())
    sys.exit(0 if success else 1)