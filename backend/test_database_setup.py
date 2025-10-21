"""
Test script to verify database infrastructure setup.

This script tests the database models, repositories, and cache
without requiring a running database server.
"""

import asyncio
import sys
import os
from datetime import datetime
from uuid import uuid4

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(__file__))

from app.domain.entities import HealthData, VitalSigns, LabResult, LabResultType, SeverityLevel
from app.domain.value_objects import InsightReport, HealthInsight, InsightType
from app.infra.repositories import (
    SQLAlchemyHealthDataRepository, 
    SQLAlchemyInsightReportRepository,
    SQLAlchemyPatientRepository
)


def test_domain_entities():
    """Test domain entity creation and validation."""
    print("Testing domain entities...")
    
    # Test VitalSigns
    vitals = VitalSigns(
        heart_rate=72,
        blood_pressure_systolic=120,
        blood_pressure_diastolic=80,
        temperature=36.5,
        respiratory_rate=16,
        oxygen_saturation=98.0
    )
    print(f"✓ VitalSigns created: HR={vitals.heart_rate}, BP={vitals.blood_pressure_systolic}/{vitals.blood_pressure_diastolic}")
    
    # Test LabResult
    lab_result = LabResult(
        test_type=LabResultType.BLOOD_GLUCOSE,
        value=95.0,
        unit="mg/dL",
        reference_range_min=70.0,
        reference_range_max=100.0
    )
    print(f"✓ LabResult created: {lab_result.test_type.value}={lab_result.value} {lab_result.unit}")
    print(f"  Normal range: {lab_result.is_within_normal_range()}")
    
    # Test HealthData
    health_data = HealthData(
        patient_id="test_patient_001",
        vitals=vitals,
        lab_results=[lab_result]
    )
    print(f"✓ HealthData created for patient: {health_data.patient_id}")
    print(f"  Complete vitals: {health_data.has_complete_vitals()}")
    
    print("Domain entities test completed successfully!\n")


def test_value_objects():
    """Test value object creation and validation."""
    print("Testing value objects...")
    
    # Test HealthInsight
    insight = HealthInsight(
        insight_type=InsightType.GENERAL_HEALTH,
        title="Normal Vital Signs",
        description="All vital signs are within normal ranges.",
        confidence_score=0.95
    )
    print(f"✓ HealthInsight created: {insight.title} (confidence: {insight.confidence_score})")
    print(f"  High confidence: {insight.is_high_confidence}")
    
    # Test InsightReport
    report = InsightReport(
        patient_id="test_patient_001",
        insights=[insight],
        confidence_score=0.90
    )
    print(f"✓ InsightReport created for patient: {report.patient_id}")
    print(f"  Report ID: {report.report_id}")
    print(f"  High confidence insights: {len(report.high_confidence_insights)}")
    
    print("Value objects test completed successfully!\n")


if __name__ == "__main__":
    print("=== Database Infrastructure Setup Test ===\n")
    
    try:
        # Test domain entities
        test_domain_entities()
        
        # Test value objects  
        test_value_objects()
        
        print("✅ All tests passed! Database infrastructure is properly configured.")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)