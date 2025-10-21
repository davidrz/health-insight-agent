#!/usr/bin/env python3
"""
Domain Layer Validation Tests - Task 2 Rigor Testing
"""
import sys
sys.path.append('.')

from datetime import datetime
from app.domain.entities import (
    HealthData, VitalSigns, LabResult, Symptom, MedicalHistory,
    LabResultType, SeverityLevel, VitalType
)
from app.domain.value_objects import (
    HealthInsight, RiskAssessment, Recommendation, InsightReport,
    InsightType, RecommendationType, RecommendationPriority, RiskLevel
)
from app.domain.services import (
    HealthDataValidationService, VitalSignsAnalysisService, RiskAssessmentService
)

def test_vital_signs_validation():
    """Test VitalSigns validation rules"""
    print("🧪 Testing VitalSigns validation...")
    
    # Valid vital signs
    try:
        vitals = VitalSigns(
            heart_rate=75,
            blood_pressure_systolic=120,
            blood_pressure_diastolic=80,
            temperature=36.5,
            respiratory_rate=16,
            oxygen_saturation=98.0
        )
        print("  ✅ Valid vital signs created successfully")
    except Exception as e:
        print(f"  ❌ Valid vital signs failed: {e}")
        return False
    
    # Test invalid heart rate
    try:
        VitalSigns(heart_rate=300)  # Invalid
        print("  ❌ Invalid heart rate validation failed")
        return False
    except ValueError:
        print("  ✅ Invalid heart rate properly rejected")
    
    # Test invalid blood pressure
    try:
        VitalSigns(blood_pressure_systolic=50)  # Too low
        print("  ❌ Invalid blood pressure validation failed")
        return False
    except ValueError:
        print("  ✅ Invalid blood pressure properly rejected")
    
    return True

def test_lab_result_validation():
    """Test LabResult validation and business logic"""
    print("🧪 Testing LabResult validation...")
    
    # Valid lab result
    try:
        lab_result = LabResult(
            test_type=LabResultType.BLOOD_GLUCOSE,
            value=95.0,
            unit="mg/dL",
            reference_range_min=70.0,
            reference_range_max=100.0
        )
        
        # Test normal range check
        if lab_result.is_within_normal_range() is True:
            print("  ✅ Normal range detection working")
        else:
            print("  ❌ Normal range detection failed")
            return False
            
    except Exception as e:
        print(f"  ❌ Lab result creation failed: {e}")
        return False
    
    # Test abnormal result
    abnormal_result = LabResult(
        test_type=LabResultType.BLOOD_GLUCOSE,
        value=150.0,  # High
        unit="mg/dL",
        reference_range_min=70.0,
        reference_range_max=100.0
    )
    
    if abnormal_result.is_within_normal_range() is False:
        print("  ✅ Abnormal range detection working")
    else:
        print("  ❌ Abnormal range detection failed")
        return False
    
    return True

def test_health_data_completeness():
    """Test HealthData business logic"""
    print("🧪 Testing HealthData completeness logic...")
    
    # Create complete health data
    vitals = VitalSigns(
        heart_rate=75,
        blood_pressure_systolic=120,
        blood_pressure_diastolic=80
    )
    
    lab_results = [
        LabResult(
            test_type=LabResultType.BLOOD_GLUCOSE,
            value=95.0,
            unit="mg/dL"
        )
    ]
    
    health_data = HealthData(
        patient_id="test-patient-123",
        vitals=vitals,
        lab_results=lab_results
    )
    
    # Test completeness check
    if health_data.has_complete_vitals():
        print("  ✅ Complete vitals detection working")
    else:
        print("  ❌ Complete vitals detection failed")
        return False
    
    # Test abnormal lab results
    abnormal_labs = health_data.get_abnormal_lab_results()
    if isinstance(abnormal_labs, list):
        print("  ✅ Abnormal lab results method working")
    else:
        print("  ❌ Abnormal lab results method failed")
        return False
    
    return True

def test_domain_services():
    """Test domain services functionality"""
    print("🧪 Testing Domain Services...")
    
    # Create test data
    vitals = VitalSigns(
        heart_rate=75,
        blood_pressure_systolic=120,
        blood_pressure_diastolic=80,
        temperature=36.5
    )
    
    health_data = HealthData(
        patient_id="test-patient-123",
        vitals=vitals
    )
    
    # Test validation service
    try:
        completeness = HealthDataValidationService.validate_health_data_completeness(health_data)
        if isinstance(completeness, dict) and 'has_vitals' in completeness:
            print("  ✅ HealthDataValidationService working")
        else:
            print("  ❌ HealthDataValidationService failed")
            return False
    except Exception as e:
        print(f"  ❌ HealthDataValidationService error: {e}")
        return False
    
    # Test vital signs analysis
    try:
        analysis = VitalSignsAnalysisService.analyze_vital_signs(vitals)
        if isinstance(analysis, dict) and 'abnormalities' in analysis:
            print("  ✅ VitalSignsAnalysisService working")
        else:
            print("  ❌ VitalSignsAnalysisService failed")
            return False
    except Exception as e:
        print(f"  ❌ VitalSignsAnalysisService error: {e}")
        return False
    
    # Test risk assessment
    try:
        cv_risk = RiskAssessmentService.assess_cardiovascular_risk(health_data)
        if hasattr(cv_risk, 'risk_level') and hasattr(cv_risk, 'probability'):
            print("  ✅ RiskAssessmentService working")
        else:
            print("  ❌ RiskAssessmentService failed")
            return False
    except Exception as e:
        print(f"  ❌ RiskAssessmentService error: {e}")
        return False
    
    return True

def test_value_objects():
    """Test value objects immutability and validation"""
    print("🧪 Testing Value Objects...")
    
    # Test HealthInsight
    try:
        insight = HealthInsight(
            insight_type=InsightType.GENERAL_HEALTH,
            title="Test Insight",
            description="Test description",
            confidence_score=0.85
        )
        
        if insight.is_high_confidence:
            print("  ✅ HealthInsight high confidence detection working")
        else:
            print("  ❌ HealthInsight high confidence detection failed")
            return False
            
    except Exception as e:
        print(f"  ❌ HealthInsight creation failed: {e}")
        return False
    
    # Test InsightReport
    try:
        report = InsightReport(patient_id="test-123")
        report.add_insight(insight)
        
        if len(report.insights) == 1:
            print("  ✅ InsightReport insight management working")
        else:
            print("  ❌ InsightReport insight management failed")
            return False
            
    except Exception as e:
        print(f"  ❌ InsightReport creation failed: {e}")
        return False
    
    return True

def test_repository_interfaces():
    """Test repository interfaces are properly defined"""
    print("🧪 Testing Repository Interfaces...")
    
    from app.domain.repositories import (
        HealthDataRepository, InsightReportRepository, PatientRepository
    )
    from abc import ABC
    
    # Check if repositories are abstract
    if issubclass(HealthDataRepository, ABC):
        print("  ✅ HealthDataRepository is properly abstract")
    else:
        print("  ❌ HealthDataRepository should be abstract")
        return False
    
    # Check required methods exist
    required_methods = ['save', 'get_by_id', 'get_by_patient_id', 'update', 'delete']
    for method in required_methods:
        if hasattr(HealthDataRepository, method):
            print(f"  ✅ HealthDataRepository.{method} exists")
        else:
            print(f"  ❌ HealthDataRepository.{method} missing")
            return False
    
    return True

def run_all_tests():
    """Run all domain validation tests"""
    print("🚀 STARTING DOMAIN LAYER RIGOR TESTING")
    print("=" * 60)
    
    tests = [
        test_vital_signs_validation,
        test_lab_result_validation,
        test_health_data_completeness,
        test_domain_services,
        test_value_objects,
        test_repository_interfaces
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
                print(f"✅ {test.__name__} PASSED\n")
            else:
                failed += 1
                print(f"❌ {test.__name__} FAILED\n")
        except Exception as e:
            failed += 1
            print(f"❌ {test.__name__} CRASHED: {e}\n")
    
    print("=" * 60)
    print(f"📊 TEST RESULTS: {passed} PASSED, {failed} FAILED")
    
    if failed == 0:
        print("🎉 ALL TESTS PASSED - DOMAIN LAYER IS SOLID!")
        return True
    else:
        print("⚠️  SOME TESTS FAILED - REVIEW REQUIRED")
        return False

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)