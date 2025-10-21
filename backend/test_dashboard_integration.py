"""
Integration test for dashboard data aggregation service.

This test verifies that the dashboard service can aggregate health data,
cache results, and provide real-time updates via WebSocket.
"""

import asyncio
import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

from app.services.dashboard_service import DashboardAggregationService, DashboardMetricsTransformer
from app.services.websocket_manager import DashboardWebSocketManager
from app.services.dashboard_update_service import DashboardUpdateService
from app.domain.entities import HealthData, VitalSigns, LabResult, LabResultType, SeverityLevel
from app.domain.value_objects import InsightReport, HealthInsight, InsightType, RiskAssessment, RiskLevel


class TestDashboardIntegration:
    """Test dashboard service integration."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.health_repo = AsyncMock()
        self.insight_repo = AsyncMock()
        self.dashboard_service = DashboardAggregationService(
            self.health_repo, self.insight_repo
        )
        self.websocket_manager = DashboardWebSocketManager()
        self.update_service = DashboardUpdateService(
            self.health_repo, self.insight_repo
        )
    
    def create_sample_health_data(self, patient_id: str = "test_patient") -> HealthData:
        """Create sample health data for testing."""
        vitals = VitalSigns(
            heart_rate=75,
            blood_pressure_systolic=120,
            blood_pressure_diastolic=80,
            temperature=36.5,
            respiratory_rate=16,
            oxygen_saturation=98.0
        )
        
        lab_results = [
            LabResult(
                test_type=LabResultType.BLOOD_GLUCOSE,
                value=95.0,
                unit="mg/dL",
                reference_range_min=70.0,
                reference_range_max=100.0
            )
        ]
        
        return HealthData(
            patient_id=patient_id,
            vitals=vitals,
            lab_results=lab_results,
            timestamp=datetime.utcnow()
        )
    
    def create_sample_insight_report(self, patient_id: str = "test_patient") -> InsightReport:
        """Create sample insight report for testing."""
        insight = HealthInsight(
            insight_type=InsightType.GENERAL_HEALTH,
            title="Normal Vital Signs",
            description="All vital signs are within normal ranges",
            confidence_score=0.9
        )
        
        risk_assessment = RiskAssessment(
            overall_risk_level=RiskLevel.LOW,
            assessment_summary="Low risk profile",
            confidence_score=0.85
        )
        
        return InsightReport(
            patient_id=patient_id,
            insights=[insight],
            risk_assessment=risk_assessment,
            confidence_score=0.9
        )
    
    @pytest.mark.asyncio
    async def test_dashboard_data_aggregation(self):
        """Test dashboard data aggregation."""
        # Setup mock data
        patient_id = "test_patient"
        health_data = [self.create_sample_health_data(patient_id)]
        insight_reports = [self.create_sample_insight_report(patient_id)]
        
        # Mock repository responses
        self.health_repo.get_by_patient_id_and_date_range.return_value = health_data
        self.insight_repo.get_by_patient_id_paginated.return_value = (insight_reports, 1)
        
        # Test dashboard data generation
        dashboard_data = await self.dashboard_service._aggregate_dashboard_data(patient_id)
        
        # Verify results
        assert dashboard_data.patient_id == patient_id
        assert len(dashboard_data.health_metrics) > 0
        assert len(dashboard_data.recent_insights) > 0
        assert dashboard_data.overall_health_score is not None
        assert dashboard_data.last_analysis_date is not None
        
        # Verify health metrics
        metric_names = [metric.metric_name for metric in dashboard_data.health_metrics]
        assert "Heart Rate (BPM)" in metric_names
        assert "Systolic BP (mmHg)" in metric_names
        
        # Verify insights
        assert len(dashboard_data.recent_insights) == 1
        assert dashboard_data.recent_insights[0].title == "Normal Vital Signs"
    
    @pytest.mark.asyncio
    async def test_time_series_transformation(self):
        """Test time series data transformation."""
        # Create multiple health data points
        health_data_list = []
        base_time = datetime.utcnow()
        
        for i in range(5):
            vitals = VitalSigns(
                heart_rate=70 + i,
                blood_pressure_systolic=115 + i,
                measured_at=base_time - timedelta(days=i)
            )
            health_data = HealthData(
                patient_id="test_patient",
                vitals=vitals,
                timestamp=base_time - timedelta(days=i)
            )
            health_data_list.append(health_data)
        
        # Transform to time series
        time_series = DashboardMetricsTransformer.transform_time_series_data(
            health_data_list, "vitals", 30
        )
        
        # Verify transformation
        assert time_series["type"] == "vitals_time_series"
        assert "heart_rate" in time_series["data"]
        assert "blood_pressure_systolic" in time_series["data"]
        assert len(time_series["data"]["heart_rate"]) == 5
        
        # Verify chronological order
        heart_rate_data = time_series["data"]["heart_rate"]
        assert heart_rate_data[0]["value"] == 74  # Most recent (70 + 4)
        assert heart_rate_data[-1]["value"] == 70  # Oldest (70 + 0)
    
    @pytest.mark.asyncio
    async def test_websocket_connection_management(self):
        """Test WebSocket connection management."""
        # Mock WebSocket
        websocket = AsyncMock()
        websocket.accept = AsyncMock()
        websocket.send_text = AsyncMock()
        
        # Test connection
        client_id = "test_client"
        patient_id = "test_patient"
        
        connection = await self.websocket_manager.connect(websocket, client_id, patient_id)
        
        # Verify connection
        assert connection.client_id == client_id
        assert connection.patient_id == patient_id
        assert client_id in self.websocket_manager.connections
        assert patient_id in self.websocket_manager.patient_subscriptions
        
        # Test message broadcasting
        await self.websocket_manager.broadcast_patient_update(
            patient_id, "test_update", {"message": "test"}
        )
        
        # Verify message was sent
        websocket.send_text.assert_called()
        
        # Test disconnection
        await self.websocket_manager.disconnect(client_id)
        
        # Verify cleanup
        assert client_id not in self.websocket_manager.connections
    
    @pytest.mark.asyncio
    async def test_dashboard_update_service(self):
        """Test dashboard update service."""
        patient_id = "test_patient"
        health_data = self.create_sample_health_data(patient_id)
        
        # Mock cache manager
        from app.infra.cache import cache_manager
        cache_manager.invalidate_patient_cache = AsyncMock(return_value=True)
        
        # Mock WebSocket manager
        self.update_service.dashboard_service.get_dashboard_data = AsyncMock()
        
        # Test health data update
        await self.update_service.handle_health_data_update(
            patient_id, health_data, "health_data_created"
        )
        
        # Verify cache invalidation was called
        cache_manager.invalidate_patient_cache.assert_called_with(patient_id)
    
    def test_health_score_calculation(self):
        """Test overall health score calculation."""
        # Create health data with normal vitals
        health_data = [self.create_sample_health_data()]
        
        # Create insight report with low risk
        insight_reports = [self.create_sample_insight_report()]
        
        # Calculate health score
        score = asyncio.run(
            self.dashboard_service._calculate_overall_health_score(
                health_data, insight_reports
            )
        )
        
        # Verify score is reasonable for healthy patient
        assert score is not None
        assert 80 <= score <= 100  # Should be high for healthy patient
    
    def test_trend_calculation(self):
        """Test trend calculation from values."""
        # Test improving trend
        improving_values = [100, 95, 90, 85, 80]  # Most recent first
        trend = self.dashboard_service._calculate_trend(improving_values)
        assert trend == "improving"
        
        # Test declining trend
        declining_values = [80, 85, 90, 95, 100]  # Most recent first
        trend = self.dashboard_service._calculate_trend(declining_values)
        assert trend == "declining"
        
        # Test stable trend
        stable_values = [90, 91, 89, 90, 91]  # Most recent first
        trend = self.dashboard_service._calculate_trend(stable_values)
        assert trend == "stable"
    
    def test_significant_update_detection(self):
        """Test detection of significant health data updates."""
        # Test with complete vitals (should be significant)
        health_data_complete = self.create_sample_health_data()
        assert self.update_service._is_significant_update(health_data_complete)
        
        # Test with only partial vitals (should not be significant)
        health_data_partial = HealthData(
            patient_id="test_patient",
            vitals=VitalSigns(heart_rate=75),  # Only heart rate
            timestamp=datetime.utcnow()
        )
        assert not self.update_service._is_significant_update(health_data_partial)
        
        # Test with lab results (should be significant)
        health_data_labs = HealthData(
            patient_id="test_patient",
            lab_results=[
                LabResult(
                    test_type=LabResultType.BLOOD_GLUCOSE,
                    value=95.0,
                    unit="mg/dL"
                )
            ],
            timestamp=datetime.utcnow()
        )
        assert self.update_service._is_significant_update(health_data_labs)


if __name__ == "__main__":
    # Run basic tests
    test_instance = TestDashboardIntegration()
    test_instance.setup_method()
    
    print("Testing dashboard data aggregation...")
    asyncio.run(test_instance.test_dashboard_data_aggregation())
    print("✓ Dashboard data aggregation test passed")
    
    print("Testing time series transformation...")
    asyncio.run(test_instance.test_time_series_transformation())
    print("✓ Time series transformation test passed")
    
    print("Testing WebSocket connection management...")
    asyncio.run(test_instance.test_websocket_connection_management())
    print("✓ WebSocket connection management test passed")
    
    print("Testing trend calculation...")
    test_instance.test_trend_calculation()
    print("✓ Trend calculation test passed")
    
    print("Testing significant update detection...")
    test_instance.test_significant_update_detection()
    print("✓ Significant update detection test passed")
    
    print("\nAll dashboard integration tests passed! ✅")